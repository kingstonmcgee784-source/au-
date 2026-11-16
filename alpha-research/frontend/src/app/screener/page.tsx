import type { Metadata } from "next";

import { FeatureStatus } from "@/components/ui/feature-status";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Stock Screener" };

export default function ScreenerPage() {
  return (
    <>
      <PageHeader item={navItem("/screener")} />
      <FeatureStatus
        summary="The screener needs a universe of stocks with fundamental, price and liquidity data. None of that is ingested yet, so there is nothing to filter."
        planned={[
          "Filters for market cap ($50M–$10B focus), average daily dollar volume, share price and 52-week range",
          "Fundamental filters: revenue and EPS growth, margins, debt, free cash flow",
          "Valuation filters: forward P/E, PEG, EV/EBITDA, FCF yield",
          "Technical filters: position versus 50- and 200-day averages, RSI, relative strength",
          "Dilution and liquidity exclusions, with every excluded name and the reason listed",
          "Saved screens and sending results to a watchlist",
        ]}
        dependsOn={[
          "Market data provider (prices, volume)",
          "Fundamentals ingestion (SEC EDGAR or a data vendor)",
          "Universe of U.S.-listed securities in the stocks table",
        ]}
      />
    </>
  );
}
