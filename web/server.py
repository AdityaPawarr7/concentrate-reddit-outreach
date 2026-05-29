"""FastAPI web UI for Reddit outreach."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import threading
from contextlib import asynccontextmanager
from typing import Any, List, Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

load_dotenv()

from pipeline import export_excel, run_grader, run_scraper
from post_format import format_post_html, normalize_author
from reddit_poster import post_comment
from scraper import fetch_post_by_id
from store import (
    get_post,
    get_setting,
    get_subreddits,
    init_db,
    list_posts,
    mark_posted,
    set_setting,
    set_subreddits,
    update_reply,
)

_scheduler_thread: Optional[threading.Thread] = None
_scheduler_stop = threading.Event()
_job_status: dict[str, Any] = {"running": False, "message": "Idle"}


class SettingsUpdate(BaseModel):
    grading_prompt: Optional[str] = None
    comment_prompt: Optional[str] = None
    auto_scrape: Optional[bool] = None
    scrape_interval_minutes: Optional[int] = None
    posts_per_subreddit: Optional[int] = None


class SubredditsUpdate(BaseModel):
    subreddits: List[str]


class RunRequest(BaseModel):
    post_ids: Optional[List[str]] = None


class ReplyUpdate(BaseModel):
    edited_reply: str


class PostCommentRequest(BaseModel):
    text: Optional[str] = None


def _scheduler_loop() -> None:
    import time

    while not _scheduler_stop.is_set():
        if get_setting("auto_scrape", "false").lower() in ("1", "true", "yes"):
            try:
                _job_status["running"] = True
                _job_status["message"] = "Auto-scrape running..."
                run_scraper()
                run_grader()
                _job_status["message"] = "Auto-scrape complete"
            except Exception as exc:
                _job_status["message"] = f"Auto-scrape error: {exc}"
            finally:
                _job_status["running"] = False
        interval = int(get_setting("scrape_interval_minutes", "5"))
        _scheduler_stop.wait(max(1, interval) * 60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _scheduler_thread
    init_db()
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    yield
    _scheduler_stop.set()


app = FastAPI(title="Concentrate Reddit Outreach", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/status")
async def status():
    return {
        "job": _job_status,
        "settings": {
            "auto_scrape": get_setting("auto_scrape", "false"),
            "scrape_interval_minutes": get_setting("scrape_interval_minutes", "5"),
            "posts_per_subreddit": get_setting("posts_per_subreddit", "25"),
        },
    }


@app.get("/api/posts")
async def posts(sort: str = "time", priority: str = "all"):
    return list_posts(sort=sort, priority=None if priority == "all" else priority)


@app.get("/api/posts/{post_id}")
async def post_detail(post_id: str, live: bool = True):
    row = get_post(post_id)
    if not row:
        raise HTTPException(404, "Post not found")
    live_body = None
    if live:
        try:
            live_post = fetch_post_by_id(post_id)
            if live_post:
                live_body = live_post.selftext
                row = {**row, "selftext": live_post.selftext, "score_reddit": live_post.score, "num_comments": live_post.num_comments}
        except Exception as exc:
            live_body = f"(Could not fetch live post: {exc})"
    reply = row.get("edited_reply") or row.get("suggested_reply") or ""
    body_raw = row.get("selftext") or ""
    return {
        **row,
        "author": normalize_author(row.get("author") or ""),
        "display_reply": reply,
        "live_fetch_note": live_body,
        "body_html": format_post_html(body_raw),
        "selftext_plain": body_raw,
    }


@app.patch("/api/posts/{post_id}/reply")
async def save_reply(post_id: str, body: ReplyUpdate):
    if not get_post(post_id):
        raise HTTPException(404, "Post not found")
    update_reply(post_id, body.edited_reply)
    export_excel()
    return {"ok": True}


@app.post("/api/posts/{post_id}/regenerate-comment")
async def regenerate_comment(post_id: str):
    result = run_grader([post_id], regenerate_comments=True)
    row = get_post(post_id)
    return {"ok": True, "result": result, "reply": row.get("edited_reply") or row.get("suggested_reply")}


@app.post("/api/posts/{post_id}/post-to-reddit")
async def post_to_reddit(post_id: str, body: PostCommentRequest):
    row = get_post(post_id)
    if not row:
        raise HTTPException(404, "Post not found")
    text = (body.text or row.get("edited_reply") or row.get("suggested_reply") or "").strip()
    if not text:
        raise HTTPException(400, "No comment text to post")
    try:
        comment_id = post_comment(post_id, text)
        mark_posted(post_id, comment_id)
        export_excel()
        return {"ok": True, "comment_id": comment_id}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/settings")
async def get_settings():
    return {
        "grading_prompt": get_setting("grading_prompt"),
        "comment_prompt": get_setting("comment_prompt"),
        "subreddits": get_subreddits(),
        "auto_scrape": get_setting("auto_scrape", "false"),
        "scrape_interval_minutes": int(get_setting("scrape_interval_minutes", "5")),
        "posts_per_subreddit": int(get_setting("posts_per_subreddit", "25")),
    }


@app.put("/api/settings")
async def update_settings(body: SettingsUpdate):
    if body.grading_prompt is not None:
        set_setting("grading_prompt", body.grading_prompt)
    if body.comment_prompt is not None:
        set_setting("comment_prompt", body.comment_prompt)
    if body.auto_scrape is not None:
        set_setting("auto_scrape", "true" if body.auto_scrape else "false")
    if body.scrape_interval_minutes is not None:
        set_setting("scrape_interval_minutes", str(body.scrape_interval_minutes))
    if body.posts_per_subreddit is not None:
        set_setting("posts_per_subreddit", str(body.posts_per_subreddit))
    return {"ok": True}


@app.put("/api/subreddits")
async def update_subreddits(body: SubredditsUpdate):
    set_subreddits(body.subreddits)
    return {"ok": True, "subreddits": get_subreddits()}


def _run_job(fn, label: str):
    global _job_status
    if _job_status["running"]:
        return
    _job_status = {"running": True, "message": f"{label}..."}
    try:
        result = fn()
        _job_status = {"running": False, "message": f"{label} done: {result}"}
    except Exception as exc:
        _job_status = {"running": False, "message": f"{label} failed: {exc}"}


@app.post("/api/run/scraper")
async def api_run_scraper(bg: BackgroundTasks, body: Optional[RunRequest] = None):
    bg.add_task(_run_job, run_scraper, "Scraper")
    return {"ok": True, "queued": True}


@app.post("/api/run/grader")
async def api_run_grader(bg: BackgroundTasks, body: Optional[RunRequest] = None):
    post_ids = body.post_ids if body and body.post_ids else None
    label = "Grader (selected)" if post_ids else "Grader (all)"
    bg.add_task(_run_job, lambda: run_grader(post_ids), label)
    return {"ok": True, "queued": True, "scope": "selected" if post_ids else "all"}


@app.post("/api/export/excel")
async def api_export_excel():
    path = export_excel()
    return {"ok": True, "path": path}


@app.get("/api/export/download")
async def download_excel():
    path = export_excel()
    return FileResponse(path, filename="reddit_leads.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
