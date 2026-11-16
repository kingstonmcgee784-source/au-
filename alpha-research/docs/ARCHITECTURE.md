# Architecture

## Principles

1. **No invented data.** If the platform does not have a number, the API says
   it is unavailable and why. The UI shows that state instead of a
   placeholder. Missing values render as "—", never as 0.
2. **Provenance on every stored data point.** Price, statement, metric and news
   rows carry `source` and `retrieved_at`. Responses carry `source` and `as_of`.
3. **Separation of concerns.** Each concern has its own backend package:

   | Package | Concern | Rules |
   |---|---|---|
   | `providers/` | Data retrieval | External APIs only; no calculations |
   | `analysis/` | Calculations | Pure functions, no I/O, unit-tested |
   | `ai/` | AI analysis | Writes narrative only from supplied, already-calculated data |
   | `services/` | Orchestration | Combines the database, providers and analysis; the only layer routes call |
   | `api/` | HTTP | Validation, dependencies and response models; no business logic |

4. **Secrets stay on the server.** The frontend calls a same-origin
   `/api/backend` path that Next.js rewrites to the backend, so neither keys
   nor the backend address appear in browser code.

## Request flow

```
Browser ──► Next.js /api/backend/* ──rewrite──► FastAPI /api/v1/*
                                                   │
                                     api/routes ──► services ──► db (SQLAlchemy)
                                                       ├──────► providers (external data)
                                                       ├──────► analysis (calculations)
                                                       └──────► ai (narrative)
```

## Backend decisions

- **Unavailable data is HTTP 200.** A missing provider or empty table is a
  normal state, not a server fault, so data endpoints return 200 with
  `status: "unavailable"`. HTTP errors are kept for client mistakes (404,
  409, 422) and real failures (500). Monitoring then sees no false errors,
  and the frontend handles one shape.
- **SQLite first, portable schema.** Models use standard SQLAlchemy types and
  Alembic batch mode, so moving to PostgreSQL means changing `DATABASE_URL`.
  Prices and metrics are stored as `Float`, which is enough for analysis;
  use `Numeric` if accounting-grade precision is ever needed.
- **UTC everywhere.** The `UTCDateTime` column type stores UTC and always
  returns timezone-aware values, even on SQLite.
- **Financial statement line items are JSON**, keyed by line-item name,
  because reported items vary by company and filing.
- **Recommendations are append-only by convention.** Outcomes will be
  recorded alongside the original call, so the track record cannot be
  rewritten later.
- **Providers are protocols.** `providers/base.py` defines the interface, and
  `providers/registry.py` picks the implementation from settings. Adding a
  vendor means one new module plus one branch in the registry; services do
  not change.
- **Scoring cannot hide gaps.** `analysis/scoring.total_score` refuses to
  score when a category rating is missing, so incomplete analysis cannot
  silently produce a number.

## Frontend decisions

- **Next.js 16 with Cache Components.** Pages prerender as static shells.
  Client components fetch live data through the typed client in
  `lib/api/client.ts`.
- **One loading and error pattern.** `useApi` drives every request, and
  `DataView` renders the loading, error, unavailable and success states the
  same way everywhere.
- **Feature status is live, not hard-coded.** `lib/navigation.ts` marks each
  section as `built` or `planned` and lists the integrations it `requires`.
  The sidebar and page headers compare those integrations with `/health` and
  show **Live**, **Needs setup** (an integration is not configured) or **Not
  built yet**. Planned pages use `FeatureStatus` to say what is missing and
  what it depends on.
- **URL holds the ticker** (`?ticker=`), so analysis pages can be linked and
  bookmarked.
