"""Post comments to Reddit via authenticated API."""

from __future__ import annotations

import os

import requests

USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT",
    "ConcentrateOutreach/1.0 (https://concentrate.ai)",
)


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _user_token() -> str:
    client_id = _env("REDDIT_CLIENT_ID")
    client_secret = _env("REDDIT_CLIENT_SECRET")
    username = _env("REDDIT_USERNAME")
    password = _env("REDDIT_PASSWORD")
    refresh_token = _env("REDDIT_REFRESH_TOKEN")

    if not client_id or not client_secret:
        raise ValueError("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env")

    headers = {"User-Agent": USER_AGENT}
    auth = (client_id, client_secret)

    if refresh_token:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            headers=headers,
            timeout=30,
        )
    elif username and password:
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            data={"grant_type": "password", "username": username, "password": password},
            headers=headers,
            timeout=30,
        )
    else:
        raise ValueError(
            "Set REDDIT_USERNAME + REDDIT_PASSWORD (script app) or REDDIT_REFRESH_TOKEN in .env"
        )

    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError(f"Reddit auth failed: {resp.text[:200]}")
    return token


def post_comment(post_id: str, text: str) -> str:
    """Post a comment on a submission. Returns Reddit comment id."""
    token = _user_token()
    headers = {
        "Authorization": f"bearer {token}",
        "User-Agent": USER_AGENT,
    }
    data = {
        "thing_id": f"t3_{post_id}",
        "text": text,
        "api_type": "json",
    }
    resp = requests.post(
        "https://oauth.reddit.com/api/comment",
        headers=headers,
        data=data,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    errors = payload.get("json", {}).get("errors") or []
    if errors:
        raise ValueError(f"Reddit API error: {errors}")
    things = payload.get("json", {}).get("data", {}).get("things") or []
    if not things:
        raise ValueError("Reddit returned no comment data")
    comment_id = things[0].get("data", {}).get("id", "")
    return comment_id
