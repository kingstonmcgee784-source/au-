import type { Metadata } from "next";
import { Suspense } from "react";

import { TechnicalView } from "@/components/stock/technical-view";
import { PageHeader } from "@/components/ui/page-header";
import { LoadingState } from "@/components/ui/states";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Technical Analysis" };

export default function Page() {
  return (
    <>
      <PageHeader item={navItem("/technical")} />
      {/* The view reads ?ticker= from the URL, which needs a Suspense boundary. */}
      <Suspense fallback={<LoadingState />}>
        <TechnicalView />
      </Suspense>
    </>
  );
}
