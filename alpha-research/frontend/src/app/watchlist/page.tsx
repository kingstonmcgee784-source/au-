import type { Metadata } from "next";

import { PageHeader } from "@/components/ui/page-header";
import { WatchlistManager } from "@/components/watchlist/watchlist-manager";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Watchlist" };

export default function WatchlistPage() {
  return (
    <>
      <PageHeader item={navItem("/watchlist")} />
      <WatchlistManager />
    </>
  );
}
