"""Orchestrate scrape, grade, store, and export."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from comment_generator import generate_comment
from export import export_xlsx
from grader import grade_post, grade_posts
from outreach_templates import template_for_angle
from scraper import RedditPost, fetch_latest_posts_detailed
from store import all_posts_for_export, get_setting, get_subreddits, upsert_post


def _post_to_row(post: RedditPost, grade: Any) -> dict[str, Any]:
    suggested_reply = template_for_angle(grade.suggested_angle)
    return {
        "post_id": post.post_id,
        "subreddit": post.subreddit,
        "title": post.title,
        "author": post.author,
        "selftext": post.selftext,
        "permalink": post.permalink,
        "url": post.url,
        "created_utc": post.created_utc.isoformat(),
        "scraped_at": post.scraped_at.isoformat(),
        "score_reddit": post.score,
        "num_comments": post.num_comments,
        "alignment_score": grade.alignment_score,
        "outreach_priority": grade.outreach_priority,
        "suggested_angle": grade.suggested_angle,
        "suggested_reply": suggested_reply,
        "edited_reply": None,
        "matched_signals": grade.matched_signals,
        "rationale": grade.rationale,
        "llm_graded": int(grade.llm_used),
        "reddit_posted": 0,
        "reddit_comment_id": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def run_scraper(*, limit_per_sub: int | None = None) -> dict[str, Any]:
    subs = get_subreddits()
    limit = limit_per_sub or int(get_setting("posts_per_subreddit", "25"))
    scrape = fetch_latest_posts_detailed(subs, limit_per_sub=limit)
    posts = scrape.posts
    for post in posts:
        upsert_post({
            "post_id": post.post_id,
            "subreddit": post.subreddit,
            "title": post.title,
            "author": post.author,
            "selftext": post.selftext,
            "permalink": post.permalink,
            "url": post.url,
            "created_utc": post.created_utc.isoformat(),
            "scraped_at": post.scraped_at.isoformat(),
            "score_reddit": post.score,
            "num_comments": post.num_comments,
            "alignment_score": 0,
            "outreach_priority": "low",
            "suggested_angle": "",
            "suggested_reply": "",
            "edited_reply": None,
            "matched_signals": "",
            "rationale": "Not graded yet",
            "llm_graded": 0,
            "reddit_posted": 0,
            "reddit_comment_id": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    export_excel()
    return {
        "scraped": len(posts),
        "subreddits": subs,
        "auth_mode": scrape.auth_mode,
        "errors": scrape.errors[:5],
    }


def run_grader(
    post_ids: list[str] | None = None,
    *,
    grading_prompt: str | None = None,
    regenerate_comments: bool = True,
) -> dict[str, Any]:
    from store import get_posts_by_ids, list_posts

    prompt = grading_prompt or get_setting("grading_prompt")
    comment_prompt = get_setting("comment_prompt")

    if post_ids:
        stored = get_posts_by_ids(post_ids)
    else:
        stored = list_posts(sort="time")

    graded_count = 0
    for row in stored:
        post = RedditPost(
            post_id=row["post_id"],
            subreddit=row["subreddit"],
            title=row["title"],
            selftext=row.get("selftext") or "",
            author=row["author"],
            permalink=row["permalink"],
            url=row.get("url") or "",
            created_utc=datetime.fromisoformat(row["created_utc"]),
            score=int(row.get("score_reddit") or 0),
            num_comments=int(row.get("num_comments") or 0),
            link_flair="",
            scraped_at=datetime.fromisoformat(row.get("scraped_at") or row["created_utc"]),
        )
        grade = grade_post(post, grading_prompt_template=prompt)
        suggested_reply = row.get("edited_reply") or row.get("suggested_reply")
        if regenerate_comments or not suggested_reply:
            suggested_reply = generate_comment(
                post,
                suggested_angle=grade.suggested_angle,
                comment_prompt_template=comment_prompt,
            )
        upsert_post(_post_to_row(post, grade) | {
            "suggested_reply": suggested_reply,
            "edited_reply": row.get("edited_reply"),
        })
        graded_count += 1

    export_excel()
    return {"graded": graded_count}


def export_excel() -> str:
    rows = all_posts_for_export()
    xlsx_path = os.getenv("OUTPUT_XLSX", "./output/reddit_leads.xlsx")
    export_xlsx(rows, xlsx_path)
    return xlsx_path
