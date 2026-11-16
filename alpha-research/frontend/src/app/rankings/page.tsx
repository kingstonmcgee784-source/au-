import type { Metadata } from "next";

import { RankingsPanel } from "@/components/dashboard/rankings-table";
import { ScoringMethodologyPanel } from "@/components/research/scoring-methodology";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Stock Rankings" };

export default function RankingsPage() {
  return (
    <>
      <PageHeader item={navItem("/rankings")} />
      <div className="grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <RankingsPanel limit={50} showLink={false} />
        </div>
        <ScoringMethodologyPanel />
      </div>
    </>
  );
}
