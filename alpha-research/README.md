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
- **Request limits:** Tiingo's free plan allows 50 requests an hour and 1,000 a
  day. To stay within that:
  - Quotes are cached for 10 minutes. When the limit is hit, the last cached
    quote is shown with its timestamp.
  - Company details are stored after the first lookup.
  - A stock's prices are refreshed at most every 6 hours.

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

## Insider activity (SEC Form 4)

On **Stock Analysis**, **Load insider filings** reads the last 180 days of Form 4
filings, which insiders file when they buy or sell company shares. The same
`SEC_USER_AGENT` setting is used, and no key is needed. **Calculate score**
also loads them. From the command line:

```bash
cd alpha-research/backend && .venv/bin/python -m app.cli sync-insiders PLTR LIVN
```

- **What is shown:** only non-derivative share transactions. Each one is
  labelled as an open-market buy, an open-market sale, a grant, an option
  exercise, tax withholding, or a gift.
- **10b5-1 plans:** a sale is marked as scheduled under a Rule 10b5-1 plan
  when the Form 4 checkbox (`aff10b5One`) or one of its footnotes says so.
  Older filings that state neither are shown as "Not stated".
- **What feeds the score:** the number of distinct open-market buyers, and the
  value of sales made outside 10b5-1 plans relative to market cap. Together
  these rate the "Institutional and insider activity" category.
  Institutional holdings from 13F filings are not connected yet.
- **Not included:** amended filings (4/A), so trades are not double counted.
- **Limit per load:** at most 60 filings are read at a time. Click again to
  load older ones.

## Catalysts (SEC 8-K events)

**News & Catalysts** lists a stock's 8-K filings from the last 13 months, with a
link to each one, and an estimated next earnings date. Use **Load SEC events**;
**Calculate score** loads them too. It costs one SEC request, with no document
downloads. From the command line:

```bash
cd alpha-research/backend && .venv/bin/python -m app.cli sync-events PLTR LIVN
```

- **Classification:** each 8-K is labelled from the item numbers it reports,
  for example 2.02 = earnings release, 1.01 = material agreement, 5.02 =
  executive change. That shows the type of event, not whether it was good or
  bad.
- **What counts against the score:** only reliable red flags, which are
  bankruptcy (1.03), impairments (2.06), restated financials (4.02) and
  auditor changes (4.01). Ambiguous items are marked "Read filing". For
  example, 3.01 covers both delisting notices and voluntary exchange
  transfers.
- **Next earnings date:** estimated from when the company reported a year
  earlier, and always labelled as an estimate.
- **Effect on scoring:** catalysts fill the "Upcoming catalysts" category, so
  scores now cover **95%** of the methodology. Only industry positioning is
  missing.

## Scoring

On **Stock Analysis**, **Calculate score** refreshes the stock's prices and SEC
statements, calculates its metrics, and scores it 0–100. Scored stocks then
appear on **Stock Rankings**. From the command line:

```bash
cd alpha-research/backend && .venv/bin/python -m app.cli score PLTR LIVN MRCY
```

The pipeline runs in three layers:

1. **Metrics** (`app/analysis/metrics.py`). Valuation (P/E, P/S, EV/EBITDA,
   P/B, FCF yield), margins, ROE, growth, balance-sheet strength, dilution,
   trend, momentum, relative strength vs SPY, and volatility. All come from
   stored prices and the last four reported quarters (TTM).
2. **Ratings** (`app/analysis/ratings.py`). Each metric maps to 0–1 through a
   documented threshold table, and each category averages the inputs it has.
3. **Score** (`app/analysis/scoring.py`). Categories are combined using the
   weights 20/20/15/15/10/5/5/10.

Rules that keep the score honest:

- **Missing data is not zero.** A metric whose inputs are missing, or that is
  not meaningful (for example P/E with negative earnings), is left empty.
  Debt that a company does not report is not assumed to be zero.
- **Unscored category.** Industry positioning has no data source yet, so it is
  not scored. Institutional and insider activity uses Form 4 insider trades
  only, and catalysts use 8-K event types. The total is the share of points
  earned in the categories that were rated, shown with its **coverage**
  (normally 95%).
- **Core categories are required.** A stock is not scored unless
  fundamentals, valuation, technicals and growth can all be rated.
  Otherwise the app says what data is missing.
- **Known limitation:** thresholds are absolute, not sector-relative. A score
  is a research aid, not a recommendation.

## Performance tracking

On **Stock Analysis**, after **Calculate score**, use **Track this call**. It
records the stock's current score, risk class and its latest stored adjusted
closing price, with the date. **Performance Tracking** then measures each
call:

- **Measures per call:** the return now and after 1 week, 1 month and 3
  months, plus the best and worst point since the call. Each is compared with
  SPY (S&P 500), QQQ (Nasdaq 100) and IWM (Russell 2000) over the same
  window.
- **Summary per horizon:** average and median return, win rate, average gain
  and loss, best and worst, average excess return over the S&P 500, and how
  often the call beat it.
- **Pending periods:** a period that has not ended in the stored prices shows
  as "pending". Adjusted prices are used, so dividends are included.
- **Update prices:** refreshes the tracked stocks and the benchmarks, at most
  every 6 hours each.
- **No rewriting history:** calls cannot be edited, and can be removed only
  on the day they were recorded. The same stock cannot be tracked twice from
  the same price date.

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
| Metrics, 0–100 scores and rankings | Calculated from stored prices, SEC statements and Form 4 insider trades; 85% coverage until catalyst and industry data exist |
| Insider activity (Form 4) | Loaded from SEC EDGAR on request; buys, sales, 10b5-1 status |
| Stock search and profile | From Tiingo when configured, otherwise the local database |
| Quotes, market overview (ETF proxies) | Live from Tiingo when configured |
| Daily price history | Loaded from Tiingo into SQLite on request; incremental after the first load |
| Financial statements (income, balance sheet, cash flow; quarterly and annual) | Loaded from SEC EDGAR into SQLite on request |
| AI report generation | Reports `ai_not_configured` |
| News & Catalysts (8-K events, estimated earnings date) | Loaded from the SEC filing index on request |
| Performance tracking (tracked calls vs S&P 500, Nasdaq 100, Russell 2000) | Working, from stored prices |
| Screener, Backtesting | Pages describe the planned feature; not built |

See [docs/API.md](docs/API.md) for every endpoint and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design decisions.
