"""Score Reddit posts for alignment with Concentrate.ai outreach."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from config import (
    CONCENTRATE_PROFILE,
    DEFAULT_GRADING_PROMPT,
    OUTREACH_THRESHOLD,
    SIGNAL_GROUPS,
)
from concentrate_client import call_concentrate
from scraper import RedditPost

USE_LLM = os.getenv("USE_LLM_GRADING", "true").lower() in ("1", "true", "yes")
_llm_warned = False


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


_GRADE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "alignment_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "rationale": {"type": "string"},
        "outreach_worthy": {"type": "boolean"},
    },
    "required": ["alignment_score", "rationale", "outreach_worthy"],
    "additionalProperties": False,
}


def _parse_grade_json(content: str, rule_score: int) -> tuple[int, str] | None:
    if not content:
        return None
    data = json.loads(content)
    return int(data.get("alignment_score", rule_score)), data.get("rationale", "")


def _env(name: str, default: str = "") -> str:
    """Strip whitespace/CRLF — common when .env was edited on Windows."""
    return (os.getenv(name) or default).strip()


def _llm_grade(
    post: RedditPost,
    rule_score: int,
    *,
    grading_prompt_template: str | None = None,
    concentrate_profile: str | None = None,
) -> tuple[int, str] | None:
    api_key = _env("CONCENTRATE_API_KEY")
    if not USE_LLM or not api_key:
        return None

    profile = concentrate_profile or CONCENTRATE_PROFILE
    template = grading_prompt_template or DEFAULT_GRADING_PROMPT
    prompt = template.format(
        concentrate_profile=profile,
        subreddit=post.subreddit,
        title=post.title,
        body=post.selftext[:2000] or "(no body)",
        rule_score=rule_score,
    )

    global _llm_warned
    content = ""
    last_error: str | None = None

    try:
        content = call_concentrate(prompt, json_schema=_GRADE_JSON_SCHEMA)
    except Exception as exc:
        last_error = str(exc)

    if not content:
        if not _llm_warned and last_error:
            print(f"[grader] Concentrate LLM grading failed, using keywords only. {last_error}")
            _llm_warned = True
        return None

    try:
        return _parse_grade_json(content, rule_score)
    except (json.JSONDecodeError, TypeError, ValueError):
        if not _llm_warned:
            print("[grader] Invalid JSON from Concentrate, using keywords only.")
            _llm_warned = True
        return None


def grade_post(
    post: RedditPost,
    *,
    grading_prompt_template: str | None = None,
    concentrate_profile: str | None = None,
) -> GradeResult:
    text = post.full_text
    rule_score, hits = _keyword_score(text)

    # Engagement boost from Reddit metrics (capped)
    engagement_boost = min(10, post.num_comments // 5 + post.score // 20)
    rule_score = min(100, rule_score + engagement_boost)

    rationale = f"Keyword match score {rule_score}; {len(hits)} signals."
    llm_used = False
    final_score = rule_score

    llm_result = _llm_grade(
        post,
        rule_score,
        grading_prompt_template=grading_prompt_template,
        concentrate_profile=concentrate_profile,
    )
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


def grade_posts(
    posts: list[RedditPost],
    *,
    grading_prompt_template: str | None = None,
    concentrate_profile: str | None = None,
) -> list[tuple[RedditPost, GradeResult]]:
    return [
        (
            p,
            grade_post(
                p,
                grading_prompt_template=grading_prompt_template,
                concentrate_profile=concentrate_profile,
            ),
        )
        for p in posts
    ]
