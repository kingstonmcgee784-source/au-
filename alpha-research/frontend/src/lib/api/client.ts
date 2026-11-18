/**
 * Typed client for the Alpha Research backend.
 *
 * All requests go to the same-origin `/api/backend` path, which Next.js
 * rewrites to the FastAPI server (see next.config.ts). No API keys or
 * backend addresses live in frontend code.
 */

import type {
  HoldingPlan,
  MarketConditions,
  IndustryComparison,
  Scan,
  ScreenerRow,
  PriceUpdateResult,
  TrackedCall,
  TrackRecord,
  CatalystFeed,
  EventsSyncResult,
  DataResponse,
  FinancialStatement,
  FinancialsSyncResult,
  HealthResponse,
  InsiderActivity,
  InsiderSyncResult,
  MetricsSnapshot,
  MarketOverview,
  PeriodType,
  PriceSyncResult,
  Quote,
  RankingEntry,
  ResearchReport,
  ResearchReportSummary,
  ScoringMethodology,
  StatementType,
  StockScore,
  StockSummary,
  TechnicalSnapshot,
  Watchlist,
} from "./types";

const API_BASE = "/api/backend";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Could not reach the Alpha Research backend.", null);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(errorMessage(body, response), response.status);
  }
  return body as T;
}

function errorMessage(body: unknown, response: Response): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first.msg === "string") return first.msg.replace(/^Value error, /, "");
    }
  }
  if (response.status >= 500) {
    return "The backend is not responding. Is the API server running?";
  }
  return `Request failed (${response.status} ${response.statusText})`;
}

const ticker = (symbol: string) => encodeURIComponent(symbol.trim().toUpperCase());

export const api = {
  health: () => request<HealthResponse>("/health"),

  marketOverview: () => request<DataResponse<MarketOverview>>("/market/overview"),
  marketConditions: () => request<DataResponse<MarketConditions>>("/market/conditions"),
  refreshMarketConditions: () =>
    request<DataResponse<MarketConditions>>("/market/conditions/refresh", { method: "POST" }),

  searchStocks: (query: string, limit = 20) =>
    request<DataResponse<StockSummary[]>>(
      `/stocks/search?${new URLSearchParams({ q: query, limit: String(limit) })}`,
    ),

  stockProfile: (symbol: string) =>
    request<DataResponse<StockSummary>>(`/stocks/${ticker(symbol)}`),

  quote: (symbol: string) => request<DataResponse<Quote>>(`/stocks/${ticker(symbol)}/quote`),

  financials: (
    symbol: string,
    filters: { statementType?: StatementType; periodType?: PeriodType } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.statementType) params.set("statement_type", filters.statementType);
    if (filters.periodType) params.set("period_type", filters.periodType);
    const query = params.size ? `?${params}` : "";
    return request<DataResponse<FinancialStatement[]>>(
      `/stocks/${ticker(symbol)}/financials${query}`,
    );
  },

  syncPrices: (symbol: string) =>
    request<DataResponse<PriceSyncResult>>(`/stocks/${ticker(symbol)}/sync-prices`, {
      method: "POST",
    }),

  syncFinancials: (symbol: string) =>
    request<DataResponse<FinancialsSyncResult>>(`/stocks/${ticker(symbol)}/sync-financials`, {
      method: "POST",
    }),

  technicals: (symbol: string) =>
    request<DataResponse<TechnicalSnapshot>>(`/stocks/${ticker(symbol)}/technicals`),

  score: (symbol: string) => request<DataResponse<StockScore>>(`/stocks/${ticker(symbol)}/score`),

  calculateScore: (symbol: string) =>
    request<DataResponse<StockScore>>(`/stocks/${ticker(symbol)}/score`, { method: "POST" }),

  metrics: (symbol: string) =>
    request<DataResponse<MetricsSnapshot>>(`/stocks/${ticker(symbol)}/metrics`),

  syncInsiders: (symbol: string) =>
    request<DataResponse<InsiderSyncResult>>(`/stocks/${ticker(symbol)}/sync-insiders`, {
      method: "POST",
    }),

  insiders: (symbol: string, days = 180) =>
    request<DataResponse<InsiderActivity>>(`/stocks/${ticker(symbol)}/insiders?days=${days}`),

  syncEvents: (symbol: string) =>
    request<DataResponse<EventsSyncResult>>(`/stocks/${ticker(symbol)}/sync-events`, {
      method: "POST",
    }),

  catalysts: (symbol: string) =>
    request<DataResponse<CatalystFeed>>(`/stocks/${ticker(symbol)}/catalysts`),

  trackRecord: () => request<TrackRecord>("/recommendations"),

  trackCall: (symbol: string, thesis?: string) =>
    request<DataResponse<TrackedCall>>("/recommendations", {
      method: "POST",
      body: JSON.stringify({ ticker: symbol, thesis: thesis || null }),
    }),

  deleteCall: (id: number) => request<void>(`/recommendations/${id}`, { method: "DELETE" }),

  updateTrackedPrices: () =>
    request<DataResponse<PriceUpdateResult>>("/recommendations/update-prices", { method: "POST" }),

  screener: () => request<ScreenerRow[]>("/screener"),

  scans: (limit = 5) => request<Scan[]>(`/screener/scans?limit=${limit}`),

  startScan: (options: { tickers?: string[]; watchlistId?: number; name?: string }) =>
    request<Scan>("/screener/scans", {
      method: "POST",
      body: JSON.stringify({
        tickers: options.tickers ?? [],
        watchlist_id: options.watchlistId ?? null,
        name: options.name || null,
      }),
    }),

  cancelScan: (id: number) => request<Scan>(`/screener/scans/${id}/cancel`, { method: "POST" }),

  holdingPlan: (symbol: string) =>
    request<DataResponse<HoldingPlan>>(`/stocks/${ticker(symbol)}/holding-plan`),
  industry: (symbol: string) =>
    request<DataResponse<IndustryComparison>>(`/stocks/${ticker(symbol)}/industry`),

  rankings: (limit = 10) => request<DataResponse<RankingEntry[]>>(`/rankings?limit=${limit}`),

  scoringMethodology: () => request<ScoringMethodology>("/scoring/methodology"),

  reports: (limit = 20) => request<ResearchReportSummary[]>(`/reports?limit=${limit}`),

  generateReport: (symbol: string) =>
    request<DataResponse<ResearchReport>>("/reports/generate", {
      method: "POST",
      body: JSON.stringify({ ticker: symbol }),
    }),

  watchlists: () => request<Watchlist[]>("/watchlists"),

  createWatchlist: (name: string, description?: string) =>
    request<Watchlist>("/watchlists", {
      method: "POST",
      body: JSON.stringify({ name, description: description || null }),
    }),

  deleteWatchlist: (id: number) => request<void>(`/watchlists/${id}`, { method: "DELETE" }),

  addWatchlistItem: (id: number, symbol: string, notes?: string) =>
    request<Watchlist>(`/watchlists/${id}/items`, {
      method: "POST",
      body: JSON.stringify({ ticker: symbol, notes: notes || null }),
    }),

  removeWatchlistItem: (id: number, symbol: string) =>
    request<Watchlist>(`/watchlists/${id}/items/${ticker(symbol)}`, { method: "DELETE" }),
};
