"""Fetch latest posts from target subreddits via Reddit's public JSON or OAuth API."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from config import SUBREDDITS

USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT",
    "ConcentrateOutreach/1.0 (https://concentrate.ai; contact outreach@concentrate.ai)",
)
REQUEST_TIMEOUT = 30


@dataclass
class RedditPost:
    post_id: str
    subreddit: str
    title: str
    selftext: str
    author: str
    permalink: str
    url: str
    created_utc: datetime
    score: int
    num_comments: int
    link_flair: str
    scraped_at: datetime

    @property
    def full_text(self) -> str:
        parts = [self.title]
        if self.selftext:
            parts.append(self.selftext)
        return "\n\n".join(parts)


def _headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _oauth_token() -> str | None:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("access_token")


def _fetch_subreddit(
    subreddit: str,
    limit: int,
    token: str | None,
) -> list[dict[str, Any]]:
    if token:
        url = f"https://oauth.reddit.com/r/{subreddit}/new"
        headers = {**_headers(), "Authorization": f"bearer {token}"}
    else:
        url = f"https://www.reddit.com/r/{subreddit}/new.json"
        headers = _headers()

    params = {"limit": min(limit, 100), "raw_json": 1}
    resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("data", {}).get("children", [])


def _parse_child(child: dict[str, Any], subreddit: str) -> RedditPost | None:
    data = child.get("data", {})
    if data.get("stickied") or data.get("over_18"):
        return None

    created = datetime.fromtimestamp(data.get("created_utc", 0), tz=timezone.utc)
    return RedditPost(
        post_id=data.get("id", ""),
        subreddit=subreddit,
        title=(data.get("title") or "").strip(),
        selftext=(data.get("selftext") or "").strip(),
        author=data.get("author") or "[deleted]",
        permalink=f"https://www.reddit.com{data.get('permalink', '')}",
        url=data.get("url") or "",
        created_utc=created,
        score=int(data.get("score") or 0),
        num_comments=int(data.get("num_comments") or 0),
        link_flair=(data.get("link_flair_text") or ""),
        scraped_at=datetime.now(timezone.utc),
    )


def fetch_latest_posts(
    subreddits: list[str] | None = None,
    limit_per_sub: int = 25,
) -> list[RedditPost]:
    """Scrape /new from each subreddit. Respects ~1 req/sec to avoid rate limits."""
    targets = subreddits or SUBREDDITS
    token = _oauth_token()
    posts: list[RedditPost] = []
    seen_ids: set[str] = set()

    for sub in targets:
        try:
            children = _fetch_subreddit(sub, limit_per_sub, token)
        except requests.RequestException as exc:
            print(f"[scraper] r/{sub} failed: {exc}")
            time.sleep(2)
            continue

        for child in children:
            post = _parse_child(child, sub)
            if post and post.post_id not in seen_ids:
                seen_ids.add(post.post_id)
                posts.append(post)

        time.sleep(1.2)

    posts.sort(key=lambda p: p.created_utc, reverse=True)
    return posts
