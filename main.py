#!/usr/bin/env python3
"""
Concentrate.ai Reddit outreach monitor.

Scrapes target subreddits, grades posts for product alignment, exports to spreadsheet.

Usage:
  python main.py once          # single scrape + grade + export
  python main.py watch         # repeat every SCRAPE_INTERVAL_MINUTES (default 5)
  python main.py watch --high  # only print high/medium priority to console
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from config import OUTREACH_THRESHOLD, SUBREDDITS
from export import export_all
from grader import grade_posts
from scraper import fetch_latest_posts

load_dotenv()


def run_cycle(*, verbose_high_only: bool = False) -> int:
    limit = int(os.getenv("POSTS_PER_SUBREDDIT", "25"))
    started = datetime.now(timezone.utc)
    print(f"\n[{started.isoformat()}] Scraping {len(SUBREDDITS)} subreddits…")

    posts = fetch_latest_posts(limit_per_sub=limit)
    print(f"  Fetched {len(posts)} posts")

    graded = grade_posts(posts)
    paths = export_all(graded)

    high = [g for _, g in graded if g.outreach_priority == "high"]
    medium = [g for _, g in graded if g.outreach_priority == "medium"]

    print(f"  Graded: {len(high)} high, {len(medium)} medium, "
          f"{len(graded) - len(high) - len(medium)} low (threshold {OUTREACH_THRESHOLD})")
    print(f"  CSV:  {paths['csv']}")
    print(f"  XLSX: {paths['xlsx']}")
    if paths.get("google_sheets"):
        print("  Google Sheets: updated")

    for post, grade in sorted(graded, key=lambda x: x[1].alignment_score, reverse=True):
        if verbose_high_only and grade.outreach_priority == "low":
            continue
        if grade.alignment_score < OUTREACH_THRESHOLD and verbose_high_only:
            continue
        flag = grade.outreach_priority.upper()
        print(
            f"  [{flag} {grade.alignment_score:>3}] r/{post.subreddit} | {post.title[:70]}\n"
            f"         → {grade.suggested_angle}\n"
            f"         {post.permalink}"
        )

    return len(high) + len(medium)


def watch(interval_minutes: float, verbose_high_only: bool) -> None:
    print(f"Watching every {interval_minutes} min. Ctrl+C to stop.")
    while True:
        try:
            run_cycle(verbose_high_only=verbose_high_only)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"  Cycle error: {exc}", file=sys.stderr)
        time.sleep(interval_minutes * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Concentrate Reddit outreach scraper")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("once", "watch"),
        default="once",
        help="Run once or on an interval",
    )
    parser.add_argument(
        "--high",
        action="store_true",
        help="Only print medium+ priority posts to console",
    )
    args = parser.parse_args()

    interval = float(os.getenv("SCRAPE_INTERVAL_MINUTES", "5"))

    if args.mode == "watch":
        watch(interval, verbose_high_only=args.high)
    else:
        run_cycle(verbose_high_only=args.high)


if __name__ == "__main__":
    main()
