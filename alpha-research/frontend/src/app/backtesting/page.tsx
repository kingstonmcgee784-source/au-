import type { Metadata } from "next";

import { FeatureStatus } from "@/components/ui/feature-status";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Backtesting" };

export default function BacktestingPage() {
  return (
    <>
      <PageHeader item={navItem("/backtesting")} />
      <FeatureStatus
        summary="The backtest_results table exists, but there is no backtesting engine and no price history to run it on."
        planned={[
          "Replay a screen or scoring rule over historical dates without look-ahead bias",
          "Returns, volatility, maximum drawdown and win rate per strategy",
          "Comparison against the S&P 500, Nasdaq 100 and Russell 2000",
          "Saved runs with their exact parameters, so results can be reproduced",
        ]}
        dependsOn={[
          "Historical daily prices for the universe and the benchmarks",
          "Point-in-time fundamentals (as they were known on each date)",
        ]}
      />
    </>
  );
}
