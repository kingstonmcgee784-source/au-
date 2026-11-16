import type { Metadata } from "next";

import { AiResearchView } from "@/components/research/ai-research-view";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "AI Research" };

export default function AiResearchPage() {
  return (
    <>
      <PageHeader item={navItem("/ai-research")} />
      <AiResearchView />
    </>
  );
}
