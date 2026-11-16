# Alpha Research

An AI-assisted stock research and screening platform: a FastAPI backend with a
SQLite database, and a Next.js research dashboard.

**Status: foundation, market data and fundamentals.** The application
structure, database, API and dashboard work end to end. Tiingo supplies
quotes and daily price history, and SEC EDGAR supplies reported financial
statements. AI research is not connected yet.
Every endpoint that lacks data returns `status: "unavailable"` with a reason.
The platform never shows invented prices or metrics.

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

## Connecting market data (Tiingo)

1. Create a free account at https://www.tiingo.com and copy your API token
   (Account > API > Token).
2. In `backend/.env`, set:
   ```
   MARKET_DATA_PROVIDER=tiingo
   MARKET_DATA_API_KEY=your-token-here
   ```
3. Restart the backend. **Settings** in the app should show Market data as
   *Connected*.

Quotes and the market overview then load live. To use technical analysis,
load a stock's daily prices, either with **Load price history** on the
Technical Analysis page or from the command line:

```bash
cd alpha-research/backend && .venv/bin/python -m app.cli sync-prices MSFT LIVN PLAB
```

The first sync loads `PRICE_HISTORY_YEARS` of history. Later syncs only fetch
new days.

Notes on the data:
- **Quotes** use Tiingo's IEX reference price. That is a single-venue price,
  not the consolidated tape, and the app labels it that way.
- **The market overview** shows the SPY, QQQ, IWM and DIA ETFs as proxies
  for the indexes, labelled as ETFs.
- **Limits:** Tiingo's free plan caps the number of requests, so quotes are
  cached for 60 seconds.

## Connecting financial statements (SEC EDGAR)

SEC EDGAR is free and needs no key, but the SEC requires every request to name
the requester with a contact email. In `backend/.env`, set:

```
SEC_USER_AGENT=Your Name you@example.com
```

Restart the backend, then use **Load financials** on the Financials page, or
the command line:

```bash
cd alpha-research/backend && .venv/bin/python -m app.cli sync-financials PLTR LIVN
```

How the statements are built:

- **Source:** figures come from the XBRL data in 10-K and 10-Q filings. When a
  period is restated, the latest filing wins.
- **Derived quarters:** 10-Qs report cash flow only year to date, and no filing
  reports a fourth quarter by itself. For additive items, those quarters are
  calculated as the difference of two year-to-date figures, for example
  Q4 = full year minus nine months. The page marks these values with a
  superscript **d**.
- **Not derived:** per-share figures and share counts are never calculated
  this way, so those cells stay empty instead.
- **Not built yet:** TTM statements.

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
| Technical indicators (EMA 9/20/21, SMA 50/100/200, RSI 14, MACD) | Calculated from stored Tiingo prices |
| Scoring methodology (weights, bands) and rankings from stored scores | Working; no scores are produced yet |
| Stock search and profile | From Tiingo when configured, otherwise the local database |
| Quotes, market overview (ETF proxies) | Live from Tiingo when configured |
| Daily price history | Loaded from Tiingo into SQLite on request; incremental after the first load |
| Financial statements (income, balance sheet, cash flow; quarterly and annual) | Loaded from SEC EDGAR into SQLite on request |
| AI report generation | Reports `ai_not_configured` |
| Screener, News & Catalysts, Backtesting, Performance Tracking | Pages describe the planned feature; not built |

See [docs/API.md](docs/API.md) for every endpoint and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design decisions.
