"""Generate outreach comments via Concentrate API."""

from __future__ import annotations

import json

from concentrate_client import call_concentrate, env
from config import DEFAULT_COMMENT_PROMPT
from outreach_templates import template_for_angle
from scraper import RedditPost


def generate_comment(
    post: RedditPost,
    *,
    suggested_angle: str = "",
    comment_prompt_template: str | None = None,
) -> str:
    template = comment_prompt_template or DEFAULT_COMMENT_PROMPT
    if not env("CONCENTRATE_API_KEY"):
        return template_for_angle(suggested_angle or "general")

    prompt = template.format(
        subreddit=post.subreddit,
        author=post.author,
        title=post.title,
        body=post.selftext[:2000] or "(no body)",
        suggested_angle=suggested_angle or "general",
    )

    content = call_concentrate(prompt, json_object=True)
    if content:
        try:
            data = json.loads(content)
            if isinstance(data, dict) and data.get("comment"):
                return str(data["comment"]).strip()
        except json.JSONDecodeError:
            return content.strip()

    return template_for_angle(suggested_angle or "general")
