# Concentrate Reddit Outreach Monitor

Scrapes latest posts from AI/coding subreddits, scores how well each thread aligns with [Concentrate.ai](https://concentrate.ai/), and exports leads to CSV + Excel.

## What it does

1. **Scrape** — Fetches `/new` from 7 subreddits every 5 minutes (configurable)
2. **Grade** — Rule-based keyword scoring (optional LLM grading)
3. **Export** — `output/reddit_leads.csv` and `output/reddit_leads.xlsx`

### Target subreddits

- r/ClaudeCode, r/LLMDevs, r/Claude, r/AIAgents, r/Cursor, r/LocalLLM, r/ClaudeAI

## Requirements

- Python 3.9+
- Internet access (Reddit public JSON API; OAuth optional)

## Setup

```bash
git clone https://github.com/YOUR_ORG/concentrate-reddit-outreach.git
cd concentrate-reddit-outreach

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` if you want Reddit OAuth, LLM grading via Concentrate, or Google Sheets (all optional).

## Run

**Single scrape + grade + export:**

```bash
python main.py once
```

**Poll every 5 minutes** (default interval from `SCRAPE_INTERVAL_MINUTES` in `.env`):

```bash
python main.py watch
```

**Only print medium+ priority posts in the terminal:**

```bash
python main.py watch --high
```

## Output

| File | Description |
|------|-------------|
| `output/reddit_leads.csv` | Append-only log, deduped by Reddit post ID |
| `output/reddit_leads.xlsx` | Full sheet sorted by score; high/medium rows color-coded |

Key columns: `alignment_score`, `outreach_priority`, `permalink`, `suggested_angle`, `suggested_reply`.

## Scoring

| Score | Priority | Suggested action |
|-------|----------|------------------|
| 70+ | high | Strong outreach candidate |
| 45–69 | medium | Review manually |
| &lt;45 | low | Usually skip |

Grading is keyword-based by default (gateway, cost, Cursor/Claude Code, guardrails, etc.). To enable LLM-assisted scores, set `USE_LLM_GRADING=true` and `CONCENTRATE_API_KEY` in `.env`.

## Optional configuration (`.env`)

| Variable | Purpose |
|----------|---------|
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Higher rate limits via [Reddit app](https://www.reddit.com/prefs/apps) |
| `USE_LLM_GRADING` / `CONCENTRATE_API_KEY` | Blend in LLM alignment score using Concentrate |
| `CONCENTRATE_BASE_URL` | Concentrate API base URL (default `https://api.concentrate.ai/v1`) |
| `CONCENTRATE_MODEL` | Model slug (e.g. `auto`, `gpt-4o-mini`, `anthropic/claude-sonnet-4-6`) |
| `GOOGLE_SHEETS_ID` / `GOOGLE_SERVICE_ACCOUNT_JSON` | Sync to Google Sheets |
| `SCRAPE_INTERVAL_MINUTES` | Poll interval (default `5`) |
| `POSTS_PER_SUBREDDIT` | Posts fetched per sub per run (default `25`) |

## Concentrate API docs

- Base URL + auth: `https://concentrate.ai/docs/api-reference/introduction`
- Responses endpoint (recommended): `https://concentrate.ai/docs/api-reference/endpoint/create-response`
- Chat Completions compatibility (beta): `https://concentrate.ai/docs/api-reference/endpoint/chat-completions`

## macOS background (launchd)

```bash
# Update paths in scripts/com.concentrate.reddit-outreach.plist if needed, then:
cp scripts/com.concentrate.reddit-outreach.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.concentrate.reddit-outreach.plist
```

## Outreach copy

Starter reply templates live in `outreach_templates.py`, keyed off `suggested_angle` in the spreadsheet.

## Project layout

```
├── main.py              # CLI entry (once / watch)
├── scraper.py           # Reddit fetch
├── grader.py            # Alignment scoring
├── export.py            # CSV / XLSX / Sheets
├── config.py            # Subreddits + keyword signals
├── outreach_templates.py
├── requirements.txt
└── output/              # Generated (gitignored)
```
