import type { Metadata } from "next";

import { ScreenerView } from "@/components/screener/screener-view";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Stock Screener" };

export default function ScreenerPage() {
  return (
    <>
      <PageHeader item={navItem("/screener")} />
      <ScreenerView />
    </>
  );
}
