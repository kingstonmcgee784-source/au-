import {
  BarChart3,
  Bot,
  CandlestickChart,
  FileSpreadsheet,
  Filter,
  History,
  LayoutDashboard,
  type LucideIcon,
  Newspaper,
  Search,
  Settings,
  Star,
  Trophy,
} from "lucide-react";

import type { HealthResponse } from "@/lib/api/types";

/** A backend integration a page needs before it can show data. */
export type Integration = keyof HealthResponse["integrations"];

/**
 * Whether a section is built at all. A built section is "live" only once the
 * integrations it `requires` are configured; that is checked at runtime
 * against the backend's health endpoint (see `featureStatus`).
 */
export type FeatureStage = "built" | "planned";

/** What the badges show. */
export type FeatureStatus = "live" | "setup" | "planned" | "unknown";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  stage: FeatureStage;
  requires?: readonly Integration[];
  description: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  {
    href: "/",
    label: "Overview",
    icon: LayoutDashboard,
    stage: "built",
    requires: ["market_data"],
    description: "Market overview, rankings, watchlist and recent research at a glance.",
  },
  {
    href: "/screener",
    label: "Stock Screener",
    icon: Filter,
    stage: "planned",
    description: "Filter the market by fundamentals, valuation, technicals and liquidity.",
  },
  {
    href: "/rankings",
    label: "Stock Rankings",
    icon: Trophy,
    stage: "built",
    requires: ["market_data", "fundamentals"],
    description: "Stocks ranked by their latest 0-100 research score.",
  },
  {
    href: "/analysis",
    label: "Stock Analysis",
    icon: Search,
    stage: "built",
    requires: ["market_data"],
    description: "Profile, live quote, research score and key metrics for a single stock.",
  },
  {
    href: "/financials",
    label: "Financials",
    icon: FileSpreadsheet,
    stage: "built",
    requires: ["fundamentals"],
    description: "Income statement, balance sheet and cash flow history from SEC filings.",
  },
  {
    href: "/technical",
    label: "Technical Analysis",
    icon: CandlestickChart,
    stage: "built",
    requires: ["market_data"],
    description: "Load daily prices, then calculate moving averages, RSI and MACD from them.",
  },
  {
    href: "/news",
    label: "News & Catalysts",
    icon: Newspaper,
    stage: "built",
    requires: ["fundamentals"],
    description: "Company events from SEC 8-K filings and the estimated next earnings date.",
  },
  {
    href: "/watchlist",
    label: "Watchlist",
    icon: Star,
    stage: "built",
    description: "Create watchlists and track tickers.",
  },
  {
    href: "/ai-research",
    label: "AI Research",
    icon: Bot,
    stage: "built",
    requires: ["ai_research"],
    description: "AI-written research reports built from platform data.",
  },
  {
    href: "/backtesting",
    label: "Backtesting",
    icon: History,
    stage: "planned",
    description: "Test screening and scoring strategies against history.",
  },
  {
    href: "/performance",
    label: "Performance Tracking",
    icon: BarChart3,
    stage: "planned",
    description: "Track every recommendation against the S&P 500, Nasdaq 100 and Russell 2000.",
  },
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
    stage: "built",
    description: "System status and integration configuration.",
  },
];

export function findNavItem(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  );
}

/** Look up a nav item by route. Throws at build time if a page uses an unknown route. */
export function navItem(href: string): NavItem {
  const item = NAV_ITEMS.find((candidate) => candidate.href === href);
  if (!item) throw new Error(`No navigation item for ${href}`);
  return item;
}

/** Live status of a section given the backend's health (null while unknown). */
export function featureStatus(item: NavItem, health: HealthResponse | null): FeatureStatus {
  if (item.stage === "planned") return "planned";
  if (!item.requires?.length) return "live";
  if (!health) return "unknown";
  return item.requires.every((name) => health.integrations[name] === "configured")
    ? "live"
    : "setup";
}
