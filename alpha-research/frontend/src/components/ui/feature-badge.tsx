"use client";

import { useFeatureStatus } from "@/components/layout/health-context";

import { StatusBadge } from "./badge";

/** The live status badge for a page, e.g. "Live" or "Needs setup". */
export function FeatureBadge({ href }: { href: string }) {
  return <StatusBadge status={useFeatureStatus(href)} />;
}
