# Job Posting Server

Korean translation: [README.ko.md](./README.ko.md)

FastAPI based job posting collector and web dashboard.

The server can:

- save crawl settings from the web UI
- collect broad IT/developer job postings on demand
- collect on fixed times or hourly intervals
- store structured metadata in SQLite and raw HTML snapshots as compressed blobs
- summarize detail pages with heuristic extraction or OpenAI
- show collected postings and run history in the browser

## Stack

- Backend: FastAPI
- Scheduler: APScheduler
- ORM: SQLAlchemy
- Template UI: Jinja2 + Vanilla JavaScript
- Default DB: SQLite

## Quick Start For Git Bash

Move to the workspace and create the virtual environment once:

```bash
git clone <repository-url>
cd job-posting-server
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

After that, run the menu script:

```bash
cd job-posting-server
./job_harvest.sh
```

The menu lets you choose:

- install or update dependencies
- start the web server
- start the web server with reload
- run one collection from `config.yaml`
- start scheduled collection from `config.yaml`
- show generated queries
- run tests
- change config path, host, and port

## Collection Model

The current default mode is `broad_it_scan`.

- The collector crawls multiple broad IT seeds instead of relying on one oversized search string.
- Listing pages are paginated until the site stops returning new URLs, unless `listing_page_limit` is set.
- Raw listing/detail HTML is stored as compressed blobs under `data/raw/`.
- URL-based deduplication prevents repeated detail fetches for already-known postings inside the refetch window.
- Job detail content is summarized into normalized fields such as job family, tech stack, requirements, responsibilities, and benefits.

If you want AI enrichment with OpenAI:

- set `OPENAI_API_KEY` in your local environment
- switch the UI setting `AI provider` to `openai`
- set an `AI model` in the UI or `config.yaml`

## Manual Commands

If you want to bypass the menu:

```bash
cd job-posting-server
./.venv/Scripts/python.exe -m job_harvest serve --host 127.0.0.1 --port 8000
```

Other useful commands:

```bash
./.venv/Scripts/python.exe -m job_harvest serve --host 127.0.0.1 --port 8000 --reload
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml run
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml schedule
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml show-queries
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Open the browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Environment Variables

- `JOB_HARVEST_DATABASE_URL`
  - Default is SQLite.
  - You can point this to PostgreSQL or Supabase later.
- `JOB_HARVEST_DATA_DIR`
  - Changes the base directory for SQLite and exports.
- `OPENAI_API_KEY`
  - Required only when `AI provider` is set to `openai`.

## Settings Flow

When the server starts:

- if DB settings already exist, the server uses DB values
- if DB settings do not exist yet and `config.yaml` exists, the server loads initial values from `config.yaml`
- after that, settings saved in the web UI become the main source of truth

## Main API

- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/collect`
- `GET /api/jobs`
- `GET /api/runs`
- `GET /api/scheduler`
- `GET /health`

## Data Paths

Default local data is stored under `data/`.

- `data/app.db`: SQLite database
- `data/raw/...`: compressed raw listing/detail HTML blobs
- `data/exports/runs/...`: per-run JSON, CSV, and Markdown exports

These paths are ignored by Git through `.gitignore`.
