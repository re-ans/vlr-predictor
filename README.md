# VLR Predictor

A full-stack web app that predicts winners of upcoming professional Valorant
matches using a **hybrid data source**:

- **PandaScore** (free-tier commercial API) — the **source of truth** for match
  schedules and results. No scraping risk; keeps the app correct on its own even
  if the scraper below is offline.
- **A self-hosted [vlrggapi](https://github.com/re-ans/vlrggapi) fork** — richer
  vlr.gg data (per-map stats, economy, head-to-head, roster transactions) that
  PandaScore's free tier lacks. **Runs locally only** — vlr.gg blocks
  cloud/datacenter IPs, so this must run on a residential connection.

> The public `vlrggapi.vercel.app` is **down** and is never used. Do **not**
> deploy the vlrggapi fork to any cloud platform — it will be network-blocked.

## Architecture (target)

| Layer | Tech | Where it runs |
|---|---|---|
| Data source 1 (results/schedule) | PandaScore API (free tier) | cloud |
| Data source 2 (rich stats) | vlrggapi fork (FastAPI scraper, Docker) | **your home machine only** |
| Database | PostgreSQL (Neon/Supabase) | cloud |
| Cloud ETL | scheduled sync PandaScore → Postgres | cloud |
| Local ETL | script vlrggapi → Postgres (outbound DB only) | **your home machine** |
| Prediction service | scikit-learn / XGBoost + FastAPI | cloud |
| Backend API | FastAPI | cloud |
| Frontend | Next.js + TypeScript + Tailwind | Vercel |
| Cache | Redis | cloud |

## Repository layout

```
backend/
  app/
    config.py            # settings loaded from .env (single source of truth)
    clients/
      pandascore.py      # PandaScore API client (source of truth)
      vlrggapi.py        # local vlrggapi client (enrichment)
  scripts/
    check_pandascore.py  # Phase 1 smoke test (live)
    check_vlrggapi.py    # Phase 1 smoke test (live, run on home machine)
  tests/                 # mocked unit tests (no live services needed)
  requirements.txt
.env.example
```

## Setup

Requires Python 3.11+ (validated on 3.14). From the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env        # then fill in real values (never commit .env)
```

Set at minimum `PANDASCORE_TOKEN` in `.env` (get one free at
<https://pandascore.co>). `.env` is gitignored.

### Database migrations (Alembic)

`DATABASE_URL` must be set. **Supabase note:** use the **Session pooler**
connection string (host `aws-0-<region>.pooler.supabase.com`, user
`postgres.<project-ref>`), *not* the Direct connection — the direct host is
IPv6-only and won't resolve on most home networks. SSL and the psycopg driver
are applied automatically.

```bash
.venv/bin/alembic upgrade head            # apply migrations
.venv/bin/alembic revision --autogenerate -m "message"   # create a new one
```

### Run the tests

```bash
.venv/bin/python -m pytest backend/tests -q
```

### Phase 1 verification

```bash
# PandaScore (needs a valid PANDASCORE_TOKEN):
.venv/bin/python -m backend.scripts.check_pandascore

# vlrggapi (run on / near your home machine, see below):
.venv/bin/python -m backend.scripts.check_vlrggapi
```

## Self-hosting the vlrggapi fork (your machine — macOS)

The AI agent cannot run this on your home machine; do it yourself and confirm it
works from your home network.

1. **Clone your fork** (default branch is `master`):
   ```bash
   git clone https://github.com/re-ans/vlrggapi.git
   cd vlrggapi
   ```

2. **Run it via Docker** (the fork ships a `Dockerfile` and `docker-compose.yml`,
   exposing port **3001**):
   ```bash
   docker compose up -d --build
   ```
   Or without compose:
   ```bash
   docker build -t vlrggapi .
   docker run -d --name vlrggapi -p 3001:3001 vlrggapi
   ```

3. **Confirm it works from your home network:**
   ```bash
   curl http://127.0.0.1:3001/v2/health
   curl http://127.0.0.1:3001/v2/news
   ```
   Both should return `{"status": "success", ...}` (health may return an `ok`
   status object). Interactive Swagger docs are at <http://127.0.0.1:3001/>.

4. **Point this app at it:** leave `VLRGGAPI_BASE_URL=http://127.0.0.1:3001` in
   `.env` (the default). If the scraper runs on a different LAN host, set the URL
   to that host's LAN IP instead.

If `/v2/health` fails or vlr.gg returns bot-protection errors, verify you are on
a residential connection (not a VPN exiting through a datacenter).

## Data-source notes

- vlrggapi is **not a database** — it re-scrapes live pages and has no long-term
  memory. Postgres is the source of truth for anything historical.
- The vlr.gg enrichment path is **best-effort**: clients raise `VlrggApiError`
  when the local instance is unreachable so downstream code can degrade
  gracefully rather than fail.
- This is a personal stats/prediction tool. It does **not** output betting odds
  or staking advice (PandaScore's stats plans prohibit betting use).

## Status

- [x] **Phase 1** — data-source clients (PandaScore + vlrggapi) and smoke tests
- [x] **Phase 2** — Postgres schema + Alembic migrations (applied to Supabase)
- [ ] Phase 3 — ingestion / backfill (both paths + reconciliation)
- [ ] Phase 4 — feature engineering
- [ ] Phase 5 — prediction service
- [ ] Phase 6 — backend API + Redis
- [ ] Phase 7 — frontend
- [ ] Phase 8 — deployment & CI
