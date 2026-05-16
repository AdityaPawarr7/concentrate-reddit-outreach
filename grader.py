"""Score Reddit posts for alignment with Concentrate.ai outreach."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from config import CONCENTRATE_PROFILE, OUTREACH_THRESHOLD, SIGNAL_GROUPS
from scraper import RedditPost

USE_LLM = os.getenv("USE_LLM_GRADING", "false").lower() in ("1", "true", "yes")


@dataclass
class GradeResult:
    alignment_score: int  # 0–100
    outreach_priority: str  # high | medium | low
    matched_signals: str
    rationale: str
    suggested_angle: str
    llm_used: bool


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _keyword_score(text: str) -> tuple[int, list[str]]:
    """Rule-based score from weighted keyword groups."""
    normalized = _normalize(text)
    total_weight = sum(g["weight"] for g in SIGNAL_GROUPS.values())
    earned = 0.0
    hits: list[str] = []

    for group_name, group in SIGNAL_GROUPS.items():
        group_hits = [kw for kw in group["keywords"] if kw in normalized]
        if not group_hits:
            continue
        # Diminishing returns: cap contribution per group
        coverage = min(1.0, len(group_hits) / 3)
        earned += group["weight"] * coverage
        hits.extend(f"{group_name}:{kw}" for kw in group_hits[:5])

    base = int(round(100 * earned / total_weight))

    # Boost questions and active threads slightly
    if "?" in text:
        base = min(100, base + 5)
    return base, hits


def _priority_label(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= OUTREACH_THRESHOLD:
        return "medium"
    return "low"


def _suggested_angle(text: str, hits: list[str]) -> str:
    normalized = _normalize(text)
    hit_str = " ".join(hits)

    if any(k in hit_str or k in normalized for k in ("cost", "pricing", "expensive", "billing")):
        return "Cost savings — unified billing, routing, token credits (~20% off)"
    if any(k in hit_str or k in normalized for k in ("cursor", "claude code", "opencode")):
        return "IDE fit — use any model in Cursor / Claude Code via one API"
    if any(k in hit_str or k in normalized for k in ("guardrail", "pii", "compliance", "rbac", "audit")):
        return "Governance — redaction, RBAC, audit logs, centralized keys"
    if any(k in hit_str or k in normalized for k in ("outage", "failover", "unreliable", "down")):
        return "Reliability — multi-provider failover and redundancy"
    if any(k in hit_str or k in normalized for k in ("openrouter", "litellm", "portkey", "gateway")):
        return "Competitive — one API, orchestration, analytics, no lock-in"
    return "General — unified LLM access, observability, team governance"


def _llm_grade(post: RedditPost, rule_score: int) -> tuple[int, str] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not USE_LLM or not api_key:
        return None

    try:
        import requests
    except ImportError:
        return None

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    prompt = f"""You grade Reddit posts for B2B outreach fit for Concentrate.ai.

{CONCENTRATE_PROFILE}

Post from r/{post.subreddit}:
Title: {post.title}
Body: {post.selftext[:2000] or "(no body)"}

Rule-based pre-score: {rule_score}/100.

Return JSON only:
{{"alignment_score": <0-100>, "rationale": "<1-2 sentences>", "outreach_worthy": <true|false>}}
Score high if the poster has a problem Concentrate solves (multi-provider API, cost, governance, Cursor/Claude Code model access).
Score low for memes, show-offs, job posts, or unrelated chatter."""

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    return int(data.get("alignment_score", rule_score)), data.get("rationale", "")


def grade_post(post: RedditPost) -> GradeResult:
    text = post.full_text
    rule_score, hits = _keyword_score(text)

    # Engagement boost from Reddit metrics (capped)
    engagement_boost = min(10, post.num_comments // 5 + post.score // 20)
    rule_score = min(100, rule_score + engagement_boost)

    rationale = f"Keyword match score {rule_score}; {len(hits)} signals."
    llm_used = False
    final_score = rule_score

    llm_result = _llm_grade(post, rule_score)
    if llm_result:
        llm_score, llm_rationale = llm_result
        final_score = int(round(0.4 * rule_score + 0.6 * llm_score))
        rationale = llm_rationale
        llm_used = True

    return GradeResult(
        alignment_score=final_score,
        outreach_priority=_priority_label(final_score),
        matched_signals="; ".join(hits[:12]),
        rationale=rationale,
        suggested_angle=_suggested_angle(text, hits),
        llm_used=llm_used,
    )


def grade_posts(posts: list[RedditPost]) -> list[tuple[RedditPost, GradeResult]]:
    return [(p, grade_post(p)) for p in posts]
