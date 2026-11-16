import type { Metadata } from "next";
import { Suspense } from "react";

import { StockAnalysisView } from "@/components/stock/stock-analysis-view";
import { PageHeader } from "@/components/ui/page-header";
import { LoadingState } from "@/components/ui/states";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Stock Analysis" };

export default function Page() {
  return (
    <>
      <PageHeader item={navItem("/analysis")} />
      {/* The view reads ?ticker= from the URL, which needs a Suspense boundary. */}
      <Suspense fallback={<LoadingState />}>
        <StockAnalysisView />
      </Suspense>
    </>
  );
}
