import type { Metadata } from "next";
import { Suspense } from "react";

import { FinancialsView } from "@/components/stock/financials-view";
import { PageHeader } from "@/components/ui/page-header";
import { LoadingState } from "@/components/ui/states";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Financials" };

export default function Page() {
  return (
    <>
      <PageHeader item={navItem("/financials")} />
      {/* The view reads ?ticker= from the URL, which needs a Suspense boundary. */}
      <Suspense fallback={<LoadingState />}>
        <FinancialsView />
      </Suspense>
    </>
  );
}
