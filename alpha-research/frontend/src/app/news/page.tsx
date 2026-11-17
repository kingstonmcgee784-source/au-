import type { Metadata } from "next";
import { Suspense } from "react";

import { CatalystsView } from "@/components/stock/catalysts-view";
import { PageHeader } from "@/components/ui/page-header";
import { LoadingState } from "@/components/ui/states";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "News & Catalysts" };

export default function NewsPage() {
  return (
    <>
      <PageHeader item={navItem("/news")} />
      {/* The view reads ?ticker= from the URL, which needs a Suspense boundary. */}
      <Suspense fallback={<LoadingState />}>
        <CatalystsView />
      </Suspense>
    </>
  );
}
