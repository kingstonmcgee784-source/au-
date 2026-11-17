/**
 * Types mirroring the backend's Pydantic schemas (backend/app/schemas).
 * Keep these in sync when the API changes.
 */

export type DataStatus = "ok" | "unavailable";

export type UnavailableReason =
  | "provider_not_configured"
  | "ai_not_configured"
  | "no_stored_data"
  | "insufficient_history"
  | "unknown_ticker"
  | "provider_error";

/** Envelope used by every data endpoint. `data` is null when unavailable. */
export interface DataResponse<T> {
  status: DataStatus;
  data: T | null;
  reason: UnavailableReason | null;
  message: string | null;
  source: string | null;
  as_of: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  app: string;
  version: string;
  environment: string;
  database: {
    connected: boolean;
    revision: string | null;
    head_revision: string | null;
    up_to_date: boolean;
    error: string | null;
  };
  integrations: {
    market_data: IntegrationState;
    fundamentals: IntegrationState;
    ai_research: IntegrationState;
  };
}

export type IntegrationState = "configured" | "not_configured";

export interface StockSummary {
  ticker: string;
  name: string;
  exchange: string | null;
  sector: string | null;
  industry: string | null;
  currency: string;
}

export interface Quote {
  ticker: string;
  price: number;
  change: number | null;
  change_percent: number | null;
  previous_close: number | null;
  volume: number | null;
  timestamp: string;
  /** Which price feed this is, e.g. a single-venue reference price. */
  feed: string;
}

export interface PriceSyncResult {
  ticker: string;
  bars_added: number;
  bars_stored: number;
  first_date: string | null;
  last_date: string | null;
}

export interface FinancialsSyncResult {
  ticker: string;
  cik: number;
  company_name: string;
  statements_stored: number;
  quarterly_periods: number;
  annual_periods: number;
  latest_period_end: string | null;
}

export type StatementType = "income" | "balance" | "cashflow";
export type PeriodType = "annual" | "quarterly" | "ttm";

export interface FinancialStatement {
  statement_type: StatementType;
  period_type: PeriodType;
  fiscal_year: number;
  fiscal_quarter: number | null;
  period_end: string;
  filing_date: string | null;
  currency: string;
  line_items: Record<string, number | null>;
  /** Line items calculated from other reported figures, e.g. Q4 = year minus nine months. */
  derived_items: string[];
  source: string;
  retrieved_at: string;
}

export interface IndicatorValue {
  name: string;
  value: number | null;
  required_bars: number;
}

export interface TechnicalSnapshot {
  ticker: string;
  as_of_date: string;
  bars_available: number;
  last_close: number;
  indicators: IndicatorValue[];
}

export interface ScoreCategory {
  key: string;
  label: string;
  weight: number;
}

export interface ScoringMethodology {
  version: string;
  categories: ScoreCategory[];
  bands: { min_score: number; label: string }[];
}

export interface CategoryScore {
  key: string;
  label: string;
  weight: number;
  /** Null when the category could not be rated for lack of data. */
  points: number | null;
  /** Sub-rating label -> rating (0-1) for the inputs that had data. */
  inputs: Record<string, number>;
  unrated_reason: string | null;
}

export interface StockScore {
  ticker: string;
  as_of: string;
  total_score: number;
  interpretation: string;
  /** Fraction of the methodology's weight that was rated (1 = all categories). */
  coverage: number;
  categories: CategoryScore[];
  methodology_version: string;
  risk_class: string | null;
  notes: string | null;
  calculated_at: string;
}

export interface MetricsSnapshot {
  ticker: string;
  as_of: string;
  values: Record<string, number | null>;
}

export interface RankingEntry {
  rank: number;
  ticker: string;
  name: string;
  total_score: number;
  coverage: number;
  interpretation: string;
  risk_class: string | null;
  as_of: string;
}

export interface IndexLevel {
  symbol: string;
  name: string;
  level: number;
  change_percent: number | null;
}

export interface MarketOverview {
  indices: IndexLevel[];
}

export interface ResearchReportSummary {
  id: number;
  title: string;
  summary: string | null;
  origin: string;
  status: string;
  report_date: string;
  created_at: string;
}

export interface ResearchReport extends ResearchReportSummary {
  body_markdown: string;
}

export interface WatchlistItem {
  id: number;
  ticker: string;
  notes: string | null;
  added_at: string;
}

export interface Watchlist {
  id: number;
  name: string;
  description: string | null;
  created_at: string;
  items: WatchlistItem[];
}

export interface InsiderSyncResult {
  ticker: string;
  filings_checked: number;
  filings_added: number;
  transactions_added: number;
  filings_remaining: number;
  unreadable_filings: number;
}

export interface InsiderTransaction {
  transaction_date: string;
  filed_on: string;
  owner_name: string;
  owner_role: string;
  code: string;
  description: string;
  acquired: boolean;
  shares: number;
  price: number | null;
  value: number | null;
  shares_after: number | null;
  /** True = under a pre-arranged Rule 10b5-1 plan; null = not stated. */
  under_10b5_1: boolean | null;
}

export interface InsiderActivity {
  ticker: string;
  days: number;
  synced_at: string;
  summary: Record<string, number | null>;
  transactions: InsiderTransaction[];
}

export interface EventsSyncResult {
  ticker: string;
  events_added: number;
  events_stored: number;
}

export interface EventItem {
  code: string;
  label: string;
  kind: string;
}

export interface CatalystEvent {
  filed_on: string;
  form: string;
  headline: string;
  kind: string;
  items: EventItem[];
  url: string;
}

export interface CatalystFeed {
  ticker: string;
  synced_at: string;
  /** Estimated from the timing of past earnings releases, not announced. */
  next_earnings_estimate: string | null;
  days_to_next_earnings: number | null;
  events: CatalystEvent[];
}

export interface TrackedCall {
  id: number;
  ticker: string;
  name: string;
  recommended_on: string;
  reference_price: number;
  reference_price_source: string;
  score: number | null;
  risk_class: string | null;
  thesis: string | null;
  horizon_days: number;
  created_at: string;
  /** True only on the day the call was recorded. */
  deletable: boolean;
  /** Returns as fractions; null means pending or not available. */
  performance: Record<string, number | null>;
}

export interface TrackRecord {
  calls: TrackedCall[];
  summary: Record<string, Record<string, number | null>>;
  benchmarks_missing: string[];
}

export interface PriceUpdateResult {
  results: { ticker: string; ok: boolean; message: string }[];
}
