# Alpha Research API

Base URL: `http://127.0.0.1:8000/api/v1`. The running server also serves
interactive OpenAPI docs at `/docs` and the schema at `/openapi.json`.

From the frontend, call the same paths under `/api/backend` (for example
`/api/backend/health`). Next.js proxies them to the backend.

## The data envelope

Every endpoint that returns market or company data answers with HTTP 200 and
this envelope:

```json
{
  "status": "ok",
  "data": { "...": "..." },
  "reason": null,
  "message": null,
  "source": "local_database",
  "as_of": "2026-11-16T20:20:16.296028Z"
}
```

When the data cannot be provided, `status` is `"unavailable"`, `data` is
`null`, and `reason` says why:

| `reason` | Meaning |
|---|---|
| `provider_not_configured` | Needs an external market data provider, and none is configured |
| `ai_not_configured` | Needs an AI provider, and none is configured |
| `no_stored_data` | Nothing is stored for this request yet |
| `insufficient_history` | Some price history is stored, but too little to calculate from |
| `unknown_ticker` | The data provider does not recognize the ticker |
| `provider_error` | The provider failed: bad API key, rate limit, timeout or outage (see `message`) |

`message` is a human-readable explanation. Clients must treat `unavailable`
as "no data", never as zero.

`source` names where the data came from, and `as_of` is when it was
retrieved or calculated. Timestamps are ISO 8601 in UTC.

## Errors

Errors that are not about data availability use standard HTTP status codes
with a `detail` field:

| Code | When |
|---|---|
| 404 | A watchlist or report id does not exist |
| 409 | Duplicate watchlist name, or a ticker already on the watchlist |
| 422 | Invalid input, such as a malformed ticker (`detail` is a list of field errors) |
| 500 | Unexpected server error (`{"detail": "Internal server error"}`; details are only logged) |

Tickers are case-insensitive and normalized to upper case. Valid forms are
1–10 letters and digits starting with a letter, with an optional `.` or `-`
class suffix (`MSFT`, `BRK.B`, `BF-B`).

## Endpoints

### Health

`GET /health` returns a plain object (not the envelope):

```json
{
  "status": "ok",
  "app": "Alpha Research API",
  "version": "0.1.0",
  "environment": "development",
  "database": {"connected": true, "revision": "0001", "head_revision": "0001", "up_to_date": true, "error": null},
  "integrations": {"market_data": "configured", "fundamentals": "configured", "ai_research": "not_configured"}
}
```

`status` is `"degraded"` if the database is unreachable or not migrated.

### Stocks

| Method & path | Returns (`data`) | Current behavior |
|---|---|---|
| `GET /stocks/search?q=&limit=20` | `StockSummary[]` | Searches the provider when configured (falling back to the local `stocks` table if the provider fails); without a provider, searches the local table and reports `provider_not_configured` when nothing matches |
| `GET /stocks/{ticker}` | `StockSummary` | From the database, otherwise from the provider |
| `GET /stocks/{ticker}/quote` | `Quote` | From the provider, cached for 60 seconds |
| `POST /stocks/{ticker}/sync-prices` | `PriceSyncResult` | Fetches daily bars from the provider and stores the ones not stored yet |
| `POST /stocks/{ticker}/sync-financials` | `FinancialsSyncResult` | Fetches statements from SEC EDGAR and stores them, replacing earlier copies of the same periods |
| `GET /stocks/{ticker}/financials?statement_type=&period_type=&limit=12` | `FinancialStatement[]` | From the database, newest period first, otherwise `no_stored_data` |
| `GET /stocks/{ticker}/technicals` | `TechnicalSnapshot` | Calculated from stored daily prices; `insufficient_history` with fewer than 2 bars |
| `GET /stocks/{ticker}/score` | `StockScore` | Latest stored score, otherwise `no_stored_data` |
| `POST /stocks/{ticker}/score?refresh=true` | `StockScore` | Refreshes prices (and SPY) and SEC statements, calculates metrics, scores and stores. `insufficient_history` when a core category cannot be rated |
| `GET /stocks/{ticker}/metrics` | `MetricsSnapshot` | The most recently calculated metrics, keyed by name |
| `POST /stocks/{ticker}/sync-insiders` | `InsiderSyncResult` | Reads Form 4 filings from the last 180 days that are not stored yet (up to 60 per call) |
| `GET /stocks/{ticker}/insiders?days=180` | `InsiderActivity` | Stored non-derivative insider transactions, newest first, with a summary (buyers, bought, sold under or outside 10b5-1 plans). `no_stored_data` until filings are loaded |

A `Quote` has `price`, `change`, `change_percent`, `previous_close`,
`volume` and `timestamp`. It also has `feed`, which names the price feed.
With Tiingo that is an IEX reference price from a single venue, not the
consolidated tape.

A `PriceSyncResult` has `bars_added`, `bars_stored`, `first_date` and
`last_date`. The first sync loads `PRICE_HISTORY_YEARS` of history. Later
syncs request only the days after the newest stored bar.

A `FinancialStatement` has `line_items`, a map of line-item name to value
(for example `revenue`, `net_income`, `operating_cash_flow`), and
`derived_items`, which lists the items calculated from year-to-date figures
rather than reported for that period on their own. `source` is `sec_edgar`.
`filing_date` is when the period was first filed.

`statement_type` is one of `income`, `balance` or `cashflow`. `period_type`
is one of `annual`, `quarterly` or `ttm` (TTM is not built yet).

In a `TechnicalSnapshot`, each indicator has `name`, `value` and
`required_bars`. `value` is `null` when the stored history is shorter than
`required_bars`. The indicators are `ema_9`, `ema_20`, `ema_21`, `sma_50`,
`sma_100`, `sma_200`, `rsi_14`, `macd`, `macd_signal` and `macd_histogram`.

### Scoring

A `StockScore` has the following fields:

- `total_score`: 0–100, calculated over the categories that were rated.
- `coverage`: the fraction of the methodology's weight that was rated.
- `categories`: one entry per category, with `points` (`null` when unrated),
  `inputs` (the sub-ratings used) and `unrated_reason`.
- `risk_class`.
- `notes`: lists the categories that were not scored and the methodology
  limitations.

| Method & path | Returns |
|---|---|
| `GET /scoring/methodology` | The category weights (summing to 100) and score bands; a plain object, not the envelope |
| `GET /rankings?limit=10` | Envelope of `RankingEntry[]`: each stock's latest score, highest first; `no_stored_data` when nothing is scored |

The scoring weights are:

| Category | Weight |
|---|---|
| Fundamentals | 20 |
| Valuation | 20 |
| Technical | 15 |
| Growth | 15 |
| Catalysts | 10 |
| Institutional | 5 |
| Industry | 5 |
| Risk/reward | 10 |

### Market

`GET /market/overview` returns an envelope of `MarketOverview`. Index levels
need a licensed index feed, so the entries are the SPY, QQQ, IWM and DIA ETFs.
Their names say "ETF" so they are not mistaken for the indexes.

### Research reports

| Method & path | Returns |
|---|---|
| `GET /reports?limit=20` | `ResearchReportSummary[]`, newest first (plain list) |
| `GET /reports/{id}` | `ResearchReport` with `body_markdown`, or 404 |
| `POST /reports/generate` with body `{"ticker": "MSFT"}` | Envelope of `ResearchReport`; currently `ai_not_configured` |

### Watchlists

| Method & path | Body | Returns |
|---|---|---|
| `GET /watchlists` | | `Watchlist[]` with items |
| `POST /watchlists` | `{"name": "...", "description": "..."}` | 201, `Watchlist` |
| `DELETE /watchlists/{id}` | | 204 |
| `POST /watchlists/{id}/items` | `{"ticker": "LIVN", "notes": "..."}` | 201, `Watchlist` |
| `DELETE /watchlists/{id}/items/{ticker}` | | `Watchlist` |

The schemas are defined in `backend/app/schemas/`. The frontend mirrors them
in `frontend/src/lib/api/types.ts`.
