import type { Metadata } from "next";

import { PerformanceView } from "@/components/performance/performance-view";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Performance Tracking" };

export default function PerformancePage() {
  return (
    <>
      <PageHeader item={navItem("/performance")} />
      <PerformanceView />
    </>
  );
}
