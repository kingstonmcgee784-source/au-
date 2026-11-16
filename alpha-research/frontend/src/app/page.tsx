import type { Metadata } from "next";

import { MarketOverviewPanel } from "@/components/dashboard/market-overview";
import { RankingsPanel } from "@/components/dashboard/rankings-table";
import { RecentResearchPanel } from "@/components/dashboard/recent-research";
import { SystemStatusPanel } from "@/components/dashboard/system-status";
import { WatchlistSummaryPanel } from "@/components/dashboard/watchlist-summary";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Overview" };

export default function OverviewPage() {
  return (
    <>
      <PageHeader item={navItem("/")} />
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <MarketOverviewPanel />
          <RankingsPanel />
        </div>
        <div className="space-y-4">
          <SystemStatusPanel />
          <WatchlistSummaryPanel />
          <RecentResearchPanel />
        </div>
      </div>
    </>
  );
}
