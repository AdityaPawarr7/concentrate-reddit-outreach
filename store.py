"""SQLite persistence for posts and UI settings."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from config import DEFAULT_COMMENT_PROMPT, DEFAULT_GRADING_PROMPT, SUBREDDITS

DB_PATH = Path(os.getenv("DB_PATH", "./output/outreach.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def import_csv_if_empty() -> int:
    """Load existing output/reddit_leads.csv into SQLite on first run."""
    import csv
    from pathlib import Path

    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM posts").fetchone()["c"]
    if count:
        return 0

    csv_path = Path(os.getenv("OUTPUT_CSV", "./output/reddit_leads.csv"))
    if not csv_path.exists():
        return 0

    imported = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            upsert_post({
                "post_id": row.get("post_id", ""),
                "subreddit": row.get("subreddit", ""),
                "title": row.get("title", ""),
                "author": row.get("author", ""),
                "selftext": row.get("selftext_preview", ""),
                "permalink": row.get("permalink", ""),
                "url": "",
                "created_utc": row.get("created_utc", ""),
                "scraped_at": row.get("scraped_at", ""),
                "score_reddit": int(row.get("score_reddit") or 0),
                "num_comments": int(row.get("num_comments") or 0),
                "alignment_score": int(row.get("alignment_score") or 0),
                "outreach_priority": row.get("outreach_priority", "low"),
                "suggested_angle": row.get("suggested_angle", ""),
                "suggested_reply": row.get("suggested_reply", ""),
                "edited_reply": None,
                "matched_signals": row.get("matched_signals", ""),
                "rationale": row.get("rationale", ""),
                "llm_graded": 1 if str(row.get("llm_graded")).lower() in ("true", "1") else 0,
                "reddit_posted": 0,
                "reddit_comment_id": None,
                "updated_at": _now(),
            })
            imported += 1
    return imported


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS posts (
                post_id TEXT PRIMARY KEY,
                subreddit TEXT,
                title TEXT,
                author TEXT,
                selftext TEXT,
                permalink TEXT,
                url TEXT,
                created_utc TEXT,
                scraped_at TEXT,
                score_reddit INTEGER,
                num_comments INTEGER,
                alignment_score INTEGER DEFAULT 0,
                outreach_priority TEXT DEFAULT 'low',
                suggested_angle TEXT,
                suggested_reply TEXT,
                edited_reply TEXT,
                matched_signals TEXT,
                rationale TEXT,
                llm_graded INTEGER DEFAULT 0,
                reddit_posted INTEGER DEFAULT 0,
                reddit_comment_id TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        defaults = {
            "grading_prompt": DEFAULT_GRADING_PROMPT,
            "comment_prompt": DEFAULT_COMMENT_PROMPT,
            "subreddits": json.dumps(SUBREDDITS),
            "auto_scrape": "false",
            "scrape_interval_minutes": "5",
            "posts_per_subreddit": "25",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
    import_csv_if_empty()


def get_setting(key: str, default: str = "") -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_subreddits() -> list[str]:
    raw = get_setting("subreddits", json.dumps(SUBREDDITS))
    try:
        data = json.loads(raw)
        return [s.strip() for s in data if s.strip()]
    except json.JSONDecodeError:
        return list(SUBREDDITS)


def set_subreddits(subs: list[str]) -> None:
    cleaned = [s.strip().lstrip("r/") for s in subs if s.strip()]
    set_setting("subreddits", json.dumps(cleaned))


def upsert_post(row: dict[str, Any]) -> None:
    row = dict(row)
    row.setdefault("updated_at", _now())
    cols = [
        "post_id", "subreddit", "title", "author", "selftext", "permalink", "url",
        "created_utc", "scraped_at", "score_reddit", "num_comments", "alignment_score",
        "outreach_priority", "suggested_angle", "suggested_reply", "edited_reply",
        "matched_signals", "rationale", "llm_graded", "reddit_posted", "reddit_comment_id",
        "updated_at",
    ]
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "post_id")
    values = [row.get(c) for c in cols]
    with connect() as conn:
        conn.execute(
            f"INSERT INTO posts ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(post_id) DO UPDATE SET {updates}",
            values,
        )


def list_posts(
    *,
    sort: str = "time",
    priority: str | None = None,
) -> list[dict[str, Any]]:
    order = {
        "time": "created_utc DESC",
        "grade": "alignment_score DESC, created_utc DESC",
        "scraped": "scraped_at DESC",
    }.get(sort, "created_utc DESC")

    query = "SELECT * FROM posts"
    params: list[Any] = []
    if priority and priority != "all":
        query += " WHERE outreach_priority = ?"
        params.append(priority)
    query += f" ORDER BY {order}"

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_post(post_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,)).fetchone()
    return dict(row) if row else None


def get_posts_by_ids(post_ids: list[str]) -> list[dict[str, Any]]:
    if not post_ids:
        return []
    placeholders = ", ".join("?" for _ in post_ids)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM posts WHERE post_id IN ({placeholders})",
            post_ids,
        ).fetchall()
    return [dict(r) for r in rows]


def update_reply(post_id: str, edited_reply: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE posts SET edited_reply = ?, updated_at = ? WHERE post_id = ?",
            (edited_reply, _now(), post_id),
        )


def mark_posted(post_id: str, comment_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE posts SET reddit_posted = 1, reddit_comment_id = ?, updated_at = ? WHERE post_id = ?",
            (comment_id, _now(), post_id),
        )


def all_posts_for_export() -> list[dict[str, Any]]:
    posts = list_posts(sort="grade")
    rows = []
    for p in posts:
        rows.append({
            "scraped_at": p.get("scraped_at", ""),
            "post_id": p.get("post_id", ""),
            "subreddit": p.get("subreddit", ""),
            "title": p.get("title", ""),
            "author": p.get("author", ""),
            "created_utc": p.get("created_utc", ""),
            "score_reddit": p.get("score_reddit", 0),
            "num_comments": p.get("num_comments", 0),
            "permalink": p.get("permalink", ""),
            "alignment_score": p.get("alignment_score", 0),
            "outreach_priority": p.get("outreach_priority", "low"),
            "suggested_angle": p.get("suggested_angle", ""),
            "suggested_reply": p.get("edited_reply") or p.get("suggested_reply", ""),
            "matched_signals": p.get("matched_signals", ""),
            "rationale": p.get("rationale", ""),
            "llm_graded": bool(p.get("llm_graded")),
            "selftext_preview": (p.get("selftext") or "")[:500],
        })
    return rows
