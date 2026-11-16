import type { ReactNode } from "react";

import type { FeatureStatus } from "@/lib/navigation";

type Tone = "neutral" | "accent" | "positive" | "negative" | "info" | "warning";

const TONES: Record<Tone, string> = {
  neutral: "border-line-strong text-ink-muted",
  accent: "border-accent/40 bg-accent-soft text-accent",
  positive: "border-positive/40 bg-positive/10 text-positive",
  negative: "border-negative/40 bg-negative/10 text-negative",
  info: "border-info/40 bg-info-soft text-info",
  warning: "border-warning/40 bg-warning-soft text-warning",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export const STATUS_LABEL: Record<FeatureStatus, string> = {
  live: "Live",
  setup: "Needs setup",
  planned: "Not built yet",
  unknown: "Checking",
};

export const STATUS_DESCRIPTION: Record<FeatureStatus, string> = {
  live: "Works with the data sources that are connected",
  setup: "Needs a data source to be configured in backend/.env",
  planned: "Not built yet",
  unknown: "Checking the backend",
};

const STATUS_TONE: Record<FeatureStatus, Tone> = {
  live: "positive",
  setup: "info",
  planned: "warning",
  unknown: "neutral",
};

export function StatusBadge({ status }: { status: FeatureStatus }) {
  return <Badge tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Badge>;
}
