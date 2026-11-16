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

export interface StockScore {
  ticker: string;
  as_of: string;
  total_score: number;
  interpretation: string;
  category_scores: Record<string, number>;
  methodology_version: string;
  risk_class: string | null;
  notes: string | null;
}

export interface RankingEntry {
  rank: number;
  ticker: string;
  name: string;
  total_score: number;
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
