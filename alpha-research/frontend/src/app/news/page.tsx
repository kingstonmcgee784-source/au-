import type { Metadata } from "next";

import { FeatureStatus } from "@/components/ui/feature-status";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "News & Catalysts" };

export default function NewsPage() {
  return (
    <>
      <PageHeader item={navItem("/news")} />
      <FeatureStatus
        summary="The news_articles table exists, but no news source is connected and no catalyst tracking is built."
        planned={[
          "Company news feed with publisher, timestamp and source link",
          "SEC filings feed (8-K, 10-Q, 10-K, Form 4) from EDGAR",
          "Earnings calendar with confirmed versus estimated dates",
          "Catalyst records: what, when, confirmed or speculative, and a 0–10 strength score",
        ]}
        dependsOn={["A news data provider", "SEC EDGAR integration"]}
      />
    </>
  );
}
