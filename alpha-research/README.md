# Alpha Research

An AI-assisted stock research and screening platform: a FastAPI backend with a
SQLite database, and a Next.js research dashboard.

**Status: foundation milestone.** The application structure, database, API and
dashboard work end to end. No market data, fundamentals or AI provider is
connected yet. Every endpoint that needs one returns `status: "unavailable"`
with a reason. The platform never shows invented prices or metrics.

## Layout

```
alpha-research/
├── backend/            FastAPI + SQLAlchemy + Alembic (Python 3.12+)
│   ├── app/
│   │   ├── api/        HTTP routes and dependencies
│   │   ├── models/     SQLAlchemy ORM models
│   │   ├── schemas/    Pydantic request/response models
│   │   ├── services/   Use cases: combine storage, providers and analysis
│   │   ├── analysis/   Pure calculations: indicators, scoring (no I/O)
│   │   ├── providers/  External data retrieval interfaces (no calculations)
│   │   ├── ai/         AI report writing interface (kept separate)
│   │   ├── core/       Settings and domain errors
│   │   └── db/         Engine, sessions, migrations, init command
│   ├── alembic/        Database migrations
│   └── tests/
├── frontend/           Next.js 16 + React 19 + TypeScript + Tailwind 4 + Lucide
│   └── src/
│       ├── app/        One folder per page (12 sections)
│       ├── components/ layout/, ui/, dashboard/, stock/, watchlist/, research/
│       └── lib/        Typed API client, hooks, formatting, navigation
└── docs/               API reference and architecture notes
```

## Requirements

- Python 3.12 or newer
- Node.js 20.9 or newer, with npm

## Setup

Backend:

```bash
cd alpha-research/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.db.init_db
```

Frontend:

```bash
cd alpha-research/frontend
npm install
cp .env.example .env.local
```

## Running

Start the backend (http://127.0.0.1:8000, interactive docs at `/docs`):

```bash
cd alpha-research/backend && .venv/bin/uvicorn app.main:app --reload --port 8000
```

Start the frontend (http://localhost:3000):

```bash
cd alpha-research/frontend && npm run dev
```

The frontend calls `/api/backend/*`, which Next.js proxies to the backend's
`/api/v1/*`. The browser never talks to the backend directly, and API keys
live only in `backend/.env`.

## Database

SQLite at `backend/data/alpha_research.db` by default. Schema changes go
through Alembic:

```bash
cd alpha-research/backend && source .venv/bin/activate
python -m app.db.init_db                                # create or upgrade to latest
alembic revision --autogenerate -m "describe change"    # after editing models
alembic upgrade head
```

The API also applies pending migrations on startup when `AUTO_MIGRATE=true`.
No sample or placeholder data is ever inserted.

## Tests and checks

```bash
cd alpha-research/backend && .venv/bin/python -m pytest
```

```bash
cd alpha-research/frontend && npm run lint && npm run build
```

## What works today

| Area | State |
|---|---|
| Health check: API, database connection, schema revision, integration status | Working |
| Watchlists: create, delete, add and remove tickers | Working, stored in SQLite |
| Technical indicators (EMA 9/20/21, SMA 50/100/200, RSI 14, MACD) | Calculated correctly from stored prices; no price ingestion yet |
| Scoring methodology (weights, bands) and rankings from stored scores | Working; no scores are produced yet |
| Stock search and profile from the local database | Working; the stocks table is empty until ingestion exists |
| Quotes, market overview | Report `provider_not_configured` |
| Financial statements | Read from the database; report `no_stored_data` until ingestion exists |
| AI report generation | Reports `ai_not_configured` |
| Screener, News & Catalysts, Backtesting, Performance Tracking | Pages describe the planned feature; not built |

See [docs/API.md](docs/API.md) for every endpoint and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design decisions.
