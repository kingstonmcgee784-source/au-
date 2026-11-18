"use client";

import { Activity, TriangleAlert } from "lucide-react";

import { SyncButton } from "@/components/stock/sync-button";
import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import { api } from "@/lib/api/client";
import type { MarketConditions, MarketGauge } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";

export const LEVEL: Record<MarketConditions["level"], { label: string; tone: string }> = {
  calm: { label: "Calm", tone: "border-positive/40 text-positive" },
  caution: { label: "Caution", tone: "border-warning/40 text-warning" },
  stress: { label: "Under stress", tone: "border-negative/40 text-negative" },
  unknown: { label: "Not enough data", tone: "border-line text-ink-muted" },
};

const DOT: Record<MarketGauge["level"], string> = {
  calm: "bg-positive",
  caution: "bg-warning",
  stress: "bg-negative",
};

export function GaugeList({ conditions }: { conditions: MarketConditions }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {conditions.gauges.map((gauge) => (
        <li key={gauge.key} className="rounded-md border border-line p-3">
          <div className="flex items-center gap-2 text-sm text-ink">
            <span className={`size-2 rounded-full ${DOT[gauge.level]}`} aria-hidden />
            {gauge.label}
            <span className="ml-auto text-xs capitalize text-ink-muted">{gauge.level}</span>
          </div>
          <p className="mt-1 text-xs text-ink-muted">{gauge.summary}</p>
        </li>
      ))}
    </ul>
  );
}

export function MarketWarning({ text }: { text: string }) {
  return (
    <p className="flex gap-2 rounded-md border border-negative/30 bg-negative/5 p-3 text-sm text-ink">
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-negative" aria-hidden />
      {text}
    </p>
  );
}

export function MarketConditionsPanel() {
  const { state, reload } = useApi("market-conditions", api.marketConditions);
  return (
    <Panel
      title="Market conditions"
      icon={Activity}
      actions={
        <SyncButton
          label="Refresh gauges"
          busyLabel="Loading…"
          run={api.refreshMarketConditions}
          describe={() => "Gauge prices checked (each refreshed at most every 6 hours)."}
          onSynced={reload}
        />
      }
    >
      <DataView state={state} onRetry={reload}>
        {(conditions, response) => {
          const level = LEVEL[conditions.level];
          return (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <span className={`rounded border px-2 py-0.5 text-sm font-medium ${level.tone}`}>
                  {level.label}
                </span>
                <span className="text-xs text-ink-muted">
                  Closing prices of {formatDate(conditions.as_of)}. Calm only when all four gauges
                  are calm. Under stress when two are in stress, one in stress and two in caution,
                  or three in caution at once.
                </span>
              </div>
              {conditions.warning && <MarketWarning text={conditions.warning} />}
              <GaugeList conditions={conditions} />
              {conditions.missing.length > 0 && (
                <p className="text-xs text-ink-muted">
                  Not loaded yet: {conditions.missing.join(", ")}. Use Refresh gauges.
                </p>
              )}
              <p className="text-[11px] text-ink-faint">
                From ETF prices, since the free data plan has no VIX index or interest-rate
                series: VIXY follows VIX futures, TLT long-term Treasury bonds (its price falls
                when rates rise), HYG junk bonds and IEF 7–10 year Treasuries.
              </p>
              <SourceNote source={response.source} asOf={response.as_of} />
            </div>
          );
        }}
      </DataView>
    </Panel>
  );
}
