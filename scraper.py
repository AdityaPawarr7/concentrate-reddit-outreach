"""Fetch latest posts from target subreddits."""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import requests

from config import SUBREDDITS

REQUEST_TIMEOUT = 30
_token_cache: Optional[str] = None


@dataclass
class ScrapeResult:
    posts: list["RedditPost"] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    auth_mode: str = "none"


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


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _user_agent() -> str:
    ua = _env(
        "REDDIT_USER_AGENT",
        "ConcentrateOutreach/1.0 (https://concentrate.ai; contact outreach@concentrate.ai)",
    )
    return ua


def _headers(token: Optional[str] = None) -> dict[str, str]:
    h = {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
    }
    if token:
        h["Authorization"] = f"bearer {token}"
    return h


def _oauth_token(force: bool = False) -> Optional[str]:
    global _token_cache
    if _token_cache and not force:
        return _token_cache

    client_id = _env("REDDIT_CLIENT_ID")
    client_secret = _env("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": _user_agent()},
        timeout=REQUEST_TIMEOUT,
    )
    if not resp.ok:
        return None
    _token_cache = resp.json().get("access_token")
    return _token_cache


def fetch_post_by_id(post_id: str) -> Optional[RedditPost]:
    token = _oauth_token()
    if token:
        url = f"https://oauth.reddit.com/comments/{post_id}.json"
        headers = _headers(token)
    else:
        url = f"https://www.reddit.com/comments/{post_id}.json"
        headers = _headers()

    resp = requests.get(url, headers=headers, params={"raw_json": 1}, timeout=REQUEST_TIMEOUT)
    if resp.status_code == 403 and not token:
        token = _oauth_token(force=True)
        if token:
            url = f"https://oauth.reddit.com/comments/{post_id}.json"
            resp = requests.get(url, headers=_headers(token), params={"raw_json": 1}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    if not payload or not payload[0].get("data", {}).get("children"):
        return None
    data = payload[0]["data"]["children"][0]["data"]
    created = datetime.fromtimestamp(data.get("created_utc", 0), tz=timezone.utc)
    return RedditPost(
        post_id=data.get("id", post_id),
        subreddit=data.get("subreddit") or "",
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


def _fetch_subreddit_json(subreddit: str, limit: int, token: Optional[str], *, use_old: bool = False) -> list[dict[str, Any]]:
    host = "oauth.reddit.com" if token else ("old.reddit.com" if use_old else "www.reddit.com")
    path = f"/r/{subreddit}/new" if token else f"/r/{subreddit}/new.json"
    url = f"https://{host}{path}"
    params = {"limit": min(limit, 100), "raw_json": 1}
    resp = requests.get(url, headers=_headers(token), params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("data", {}).get("children", [])


def _fetch_subreddit_rss(subreddit: str, limit: int) -> list[RedditPost]:
    url = f"https://www.reddit.com/r/{subreddit}/new.rss"
    resp = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    posts: list[RedditPost] = []
    for entry in root.findall("atom:entry", ns)[:limit]:
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        link_el = entry.find("atom:link", ns)
        href = link_el.attrib.get("href", "") if link_el is not None else ""
        author = (entry.findtext("atom:author/atom:name", default="", namespaces=ns) or "[deleted]").strip()
        author = re.sub(r"^\/?u\/", "", author)
        updated = entry.findtext("atom:updated", default="", namespaces=ns)
        content = entry.findtext("atom:content", default="", namespaces=ns) or ""
        try:
            created = parsedate_to_datetime(updated) if updated else datetime.now(timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            created = datetime.now(timezone.utc)
        post_id = ""
        if "/comments/" in href:
            post_id = href.split("/comments/")[1].split("/")[0]
        posts.append(
            RedditPost(
                post_id=post_id or href,
                subreddit=subreddit,
                title=title,
                selftext=content.strip(),
                author=author,
                permalink=href.split("?")[0] if href else "",
                url=href,
                created_utc=created,
                score=0,
                num_comments=0,
                link_flair="",
                scraped_at=datetime.now(timezone.utc),
            )
        )
    return posts


def _parse_child(child: dict[str, Any], subreddit: str) -> Optional[RedditPost]:
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


def _fetch_one_subreddit(subreddit: str, limit: int, token: Optional[str]) -> tuple[list[RedditPost], Optional[str]]:
    errors: list[str] = []
    # 1) OAuth JSON
    if token:
        try:
            children = _fetch_subreddit_json(subreddit, limit, token)
            posts = [p for c in children if (p := _parse_child(c, subreddit))]
            if posts:
                return posts, None
        except requests.RequestException as exc:
            errors.append(f"oauth: {exc}")

    # 2) Public JSON
    try:
        children = _fetch_subreddit_json(subreddit, limit, None)
        posts = [p for c in children if (p := _parse_child(c, subreddit))]
        if posts:
            return posts, None
    except requests.RequestException as exc:
        errors.append(f"public json: {exc}")

    # 3) old.reddit JSON
    try:
        children = _fetch_subreddit_json(subreddit, limit, None, use_old=True)
        posts = [p for c in children if (p := _parse_child(c, subreddit))]
        if posts:
            return posts, None
    except requests.RequestException as exc:
        errors.append(f"old reddit: {exc}")

    # 4) RSS fallback
    try:
        posts = _fetch_subreddit_rss(subreddit, limit)
        if posts:
            return posts, None
    except requests.RequestException as exc:
        errors.append(f"rss: {exc}")

    return [], f"r/{subreddit}: " + "; ".join(errors[-2:])


def fetch_latest_posts(
    subreddits: Optional[list[str]] = None,
    limit_per_sub: int = 25,
) -> list[RedditPost]:
    result = fetch_latest_posts_detailed(subreddits, limit_per_sub=limit_per_sub)
    return result.posts


def fetch_latest_posts_detailed(
    subreddits: Optional[list[str]] = None,
    limit_per_sub: int = 25,
) -> ScrapeResult:
    targets = subreddits or SUBREDDITS
    token = _oauth_token()
    result = ScrapeResult(auth_mode="oauth" if token else "public/rss")

    for sub in targets:
        posts, err = _fetch_one_subreddit(sub, limit_per_sub, token)
        if err:
            result.errors.append(err)
            print(f"[scraper] {err}")
        for post in posts:
            if post.post_id and post.post_id not in {p.post_id for p in result.posts}:
                result.posts.append(post)
        time.sleep(1.5)

    result.posts.sort(key=lambda p: p.created_utc, reverse=True)
    if not result.posts and result.errors:
        result.errors.append(
            "Reddit blocked unauthenticated scraping. Add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to .env "
            "(reddit.com/prefs/apps, type: script)."
        )
    return result
