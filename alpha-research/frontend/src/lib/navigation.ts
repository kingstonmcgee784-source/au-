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

/**
 * How far along a section is. Shown in the sidebar so nobody mistakes an
 * unfinished page for a working feature.
 *  - live:    works end to end with the data the platform has.
 *  - partial: the page and API exist, but need data integrations to show data.
 *  - planned: page structure only; the feature is not built yet.
 */
export type FeatureStage = "live" | "partial" | "planned";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  stage: FeatureStage;
  description: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  {
    href: "/",
    label: "Overview",
    icon: LayoutDashboard,
    stage: "partial",
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
    stage: "partial",
    description: "Stocks ranked by the 0-100 composite score.",
  },
  {
    href: "/analysis",
    label: "Stock Analysis",
    icon: Search,
    stage: "partial",
    description: "Profile, quote and score for a single stock.",
  },
  {
    href: "/financials",
    label: "Financials",
    icon: FileSpreadsheet,
    stage: "partial",
    description: "Income statement, balance sheet and cash flow history.",
  },
  {
    href: "/technical",
    label: "Technical Analysis",
    icon: CandlestickChart,
    stage: "partial",
    description: "Moving averages, RSI and MACD calculated from stored prices.",
  },
  {
    href: "/news",
    label: "News & Catalysts",
    icon: Newspaper,
    stage: "planned",
    description: "Company news, earnings dates and catalyst tracking.",
  },
  {
    href: "/watchlist",
    label: "Watchlist",
    icon: Star,
    stage: "live",
    description: "Create watchlists and track tickers.",
  },
  {
    href: "/ai-research",
    label: "AI Research",
    icon: Bot,
    stage: "partial",
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
    stage: "partial",
    description: "System status and integration configuration.",
  },
];

export function findNavItem(pathname: string): NavItem | undefined {
  return NAV_ITEMS.find((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  );
}
