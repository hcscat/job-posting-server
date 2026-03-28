# Job Posting Server

Korean translation: [README.ko.md](./README.ko.md)

FastAPI-based job posting collector and manual collection console.

## What It Does

- saves collection settings from the web UI
- collects broad IT and developer job postings on demand
- stores normalized posting records in SQLite
- stores raw listing and detail responses as compressed blobs
- enriches detail pages with heuristic extraction or OpenAI
- exposes run history, job detail, and raw snapshot views in the browser

## Stack

- Backend: FastAPI
- ORM: SQLAlchemy
- UI: Jinja2 + Vanilla JavaScript
- Default database: SQLite
- Optional AI enrichment: OpenAI API

## Quick Start For Git Bash

```bash
git clone <repository-url>
cd job-posting-server
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./job_harvest.sh
```

The menu lets you:

- install or update dependencies
- start the web server
- start the web server with reload
- run one collection from `config.yaml`
- show generated queries
- run tests
- change config path, host, and port

## Manual-First Workflow

1. Start the server.
2. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).
3. Save collection settings in the web UI.
4. Trigger a run from the dashboard or `POST /api/collect`.
5. Review:
   - `/jobs` for normalized postings
   - `/jobs/{job_id}` for normalized plus raw-linked detail
   - `/runs/{run_id}` for run-scoped postings and raw manifest
   - `/raw/{category}/{sha256}` for stored raw bodies

## Collector Model

The default mode is `broad_it_scan`.

- The collector uses multiple broad IT seeds instead of one oversized query string.
- Listing pages are paginated until a site stops returning new URLs, unless `listing_page_limit` is set.
- URL-centered deduplication avoids repeated detail fetches inside the refetch window.
- Raw listing and detail payloads are stored separately from normalized job rows.
- AI enrichment summarizes detail pages into job family, tech stack, requirements, responsibilities, and benefits.

If you want OpenAI enrichment:

- set `OPENAI_API_KEY` in the server environment
- change the UI setting `AI provider` to `openai`
- set an `AI model` in the UI

## Useful Commands

```bash
./.venv/Scripts/python.exe -m job_harvest serve --host 127.0.0.1 --port 8000
./.venv/Scripts/python.exe -m job_harvest serve --host 127.0.0.1 --port 8000 --reload
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml run
./.venv/Scripts/python.exe -m job_harvest --config ./config.yaml show-queries
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Environment Variables

- `JOB_HARVEST_DATABASE_URL`
  Use PostgreSQL or Supabase instead of SQLite if needed.
- `JOB_HARVEST_DATA_DIR`
  Changes the base directory for SQLite, raw blobs, and exports.
- `OPENAI_API_KEY`
  Required only when `AI provider` is set to `openai`.

## Main API

- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/collect`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/raw/{category}/{sha256_hex}`
- `GET /health`

## Data Paths

Default local data is stored under `data/`.

- `data/app.db`: SQLite database
- `data/raw/...`: compressed raw listing and detail blobs
- `data/exports/runs/...`: per-run JSON, CSV, and Markdown exports

These paths are ignored by Git through `.gitignore`.

## Project Docs

- Project identity: [docs/project-identity.ko.md](./docs/project-identity.ko.md)
- Agent skill pack: [agent-pack/README.md](./agent-pack/README.md)
