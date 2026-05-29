# Concentrate Reddit Outreach

Scrape AI/coding subreddits, grade alignment with [Concentrate.ai](https://concentrate.ai/), review leads in a local web UI, and export to Excel.

## Requirements

- Python 3.9+
- macOS / Linux / Windows

## First-time setup

```bash
cd ~/Documents/concentrate-reddit-outreach

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cp .env.example .env               # optional — see below
```

## Launch the app

```bash
cd ~/Documents/concentrate-reddit-outreach
source .venv/bin/activate
python run_ui.py
```

Open in your browser:

**http://127.0.0.1:8000**

Stop the server with `Ctrl+C`.

> Use `python run_ui.py` (not bare `python` / `pip`) unless your venv is activated.

## Daily workflow

1. **Run scraper (all)** — fetch latest posts from your subreddit list  
2. **Run grader (all)** — score posts and generate suggested replies  
3. Click a post on the left → read the formatted thread in the center  
4. **Copy reply** → **Open post on Reddit** → paste your comment manually  
5. **Download Excel** anytime from the top bar (`output/reddit_leads.xlsx`)

## Environment variables (`.env`)

### Bare minimum (works today)

No credentials required. Scraping uses RSS fallback; grading uses keywords; replies use templates.

Optional — disable AI grading explicitly:

```bash
USE_LLM_GRADING=false
```

### Recommended (AI grading + replies)

```bash
CONCENTRATE_API_KEY=your_key_here
CONCENTRATE_MODEL=gpt-4o-mini
USE_LLM_GRADING=true
```

Get a key from [Concentrate.ai](https://concentrate.ai/). Docs: https://concentrate.ai/docs/api-reference/introduction

### Optional (better Reddit scraping)

When you have a Reddit **script** app approved:

```bash
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=ConcentrateOutreach/1.0 by u/your_username
```

Without these, scraping still works via RSS (may have thinner post bodies).

## UI overview

| Panel | What it does |
|-------|----------------|
| **Left** | Post list — sort by newest / grade / scraped; filter priority |
| **Center** | Reddit-formatted post body + editable suggested reply + manual post flow |
| **Right** | Run scraper/grader, auto-scrape, subreddits, grading/comment prompts |

Features: Concentrate green theme, light/dark toggle, Excel export, copy-to-clipboard for manual Reddit replies.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `command not found: pip` / `python` | Activate venv: `source .venv/bin/activate` |
| `No module named 'export'` | Run from project root; ensure `export.py` exists |
| Scraper 403 / no posts | Restart app (RSS fallback); add Reddit OAuth creds if you have them |
| AI grading not used | Set `USE_LLM_GRADING=true` and `CONCENTRATE_API_KEY` in `.env` |
| Stale UI after updates | Hard refresh browser (`Cmd+Shift+R`) |

## CLI (optional)

```bash
source .venv/bin/activate
python main.py once      # scrape + grade once
python main.py watch     # repeat on interval
```

## Output files

| File | Description |
|------|-------------|
| `output/reddit_leads.xlsx` | Excel export (sorted by score) |
| `output/reddit_leads.csv` | CSV log |
| `output/outreach.db` | SQLite database for the UI |
