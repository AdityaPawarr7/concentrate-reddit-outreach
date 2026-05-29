#!/usr/bin/env python3
"""CLI entrypoint (legacy). Prefer the web UI: python run_ui.py"""

from __future__ import annotations

import argparse
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from pipeline import export_excel, run_grader, run_scraper
from store import init_db


def run_cycle(*, verbose_high_only: bool = False) -> int:
    from config import OUTREACH_THRESHOLD
    from store import list_posts

    result = run_scraper()
    grade_result = run_grader()
    print(f"Scraped {result['scraped']} posts, graded {grade_result['graded']}")

    medium_plus = 0
    for row in list_posts(sort="grade"):
        if row.get("outreach_priority") == "low" and verbose_high_only:
            continue
        if int(row.get("alignment_score") or 0) < OUTREACH_THRESHOLD and verbose_high_only:
            continue
        medium_plus += 1
        print(f"[{row.get('outreach_priority', '').upper()} {row.get('alignment_score')}] r/{row.get('subreddit')} | {row.get('title', '')[:70]}")
    return medium_plus


def watch(interval_minutes: float, verbose_high_only: bool) -> None:
    print(f"Watching every {interval_minutes} min. Ctrl+C to stop.")
    while True:
        try:
            run_cycle(verbose_high_only=verbose_high_only)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"Cycle error: {exc}", file=sys.stderr)
        time.sleep(interval_minutes * 60)


def main() -> None:
    init_db()
    parser = argparse.ArgumentParser(description="Concentrate Reddit outreach CLI")
    parser.add_argument("mode", nargs="?", choices=("once", "watch"), default="once")
    parser.add_argument("--high", action="store_true")
    args = parser.parse_args()
    interval = float(os.getenv("SCRAPE_INTERVAL_MINUTES", "5"))
    if args.mode == "watch":
        watch(interval, verbose_high_only=args.high)
    else:
        run_cycle(verbose_high_only=args.high)


if __name__ == "__main__":
    main()
