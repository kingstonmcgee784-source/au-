import type { Metadata } from "next";

import { FeatureStatus } from "@/components/ui/feature-status";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Performance Tracking" };

export default function PerformancePage() {
  return (
    <>
      <PageHeader item={navItem("/performance")} />
      <FeatureStatus
        summary="The recommendations table exists, but no recommendations are recorded through the platform yet and there is no price feed to measure them against. No track record is shown until real results exist."
        planned={[
          "Record each recommendation with its date, reference price and source; records are never edited afterwards",
          "Returns after 1 week, 1 month and 3 months, plus maximum favorable and adverse moves",
          "Average and median return, win rate, average gain and loss, maximum drawdown",
          "Outperformance against the S&P 500, Nasdaq 100 and Russell 2000, including dividends",
        ]}
        dependsOn={["Market data provider for daily prices", "Benchmark index history"]}
      />
    </>
  );
}
