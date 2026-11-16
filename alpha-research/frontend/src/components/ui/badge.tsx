import type { ReactNode } from "react";

import type { FeatureStage } from "@/lib/navigation";

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

const STAGE_LABEL: Record<FeatureStage, string> = {
  live: "Live",
  partial: "Needs data",
  planned: "Planned",
};

const STAGE_TONE: Record<FeatureStage, Tone> = {
  live: "positive",
  partial: "info",
  planned: "warning",
};

export function StageBadge({ stage }: { stage: FeatureStage }) {
  return <Badge tone={STAGE_TONE[stage]}>{STAGE_LABEL[stage]}</Badge>;
}
