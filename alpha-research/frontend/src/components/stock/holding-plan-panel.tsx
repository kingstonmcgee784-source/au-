"use client";

import { CalendarClock, Check, TriangleAlert, X } from "lucide-react";

import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import type { DataResponse, HoldingPlan, SectorTrend } from "@/lib/api/types";
import { formatDate, formatNumber } from "@/lib/format";
import type { ApiState } from "@/lib/hooks/use-api";

const FIT: Record<HoldingPlan["fit"], { label: string; tone: string; text: string }> = {
  good: {
    label: "Good fit",
    tone: "border-positive/40 text-positive",
    text: "The price trend supports a short hold.",
  },
  mixed: {
    label: "Mixed fit",
    tone: "border-warning/40 text-warning",
    text: "Some trend checks pass and some fail. Keep the position smaller or wait for a cleaner setup.",
  },
  poor: {
    label: "Poor fit",
    tone: "border-negative/40 text-negative",
    text: "The trend works against a short hold right now, whatever the score says.",
  },
  unknown: {
    label: "Not enough data",
    tone: "border-line text-ink-muted",
    text: "Too little price history to check the trend.",
  },
};

function pct(value: number | null): string {
  return value === null ? "—" : `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function Level({
  label,
  price,
  change,
  tone,
  note,
}: {
  label: string;
  price: number | null;
  change?: string;
  tone?: string;
  note: string;
}) {
  return (
    <div className="rounded-md border border-line p-3">
      <p className="text-xs uppercase tracking-wider text-ink-faint">{label}</p>
      <p className={`mt-1 font-mono text-xl ${tone ?? "text-ink"}`}>
        {formatNumber(price)}
        {change && <span className="ml-2 text-sm">{change}</span>}
      </p>
      <p className="mt-1 text-xs text-ink-muted">{note}</p>
    </div>
  );
}

export function HoldingPlanPanel({
  state,
  onRetry,
}: {
  state: ApiState<DataResponse<HoldingPlan>>;
  onRetry: () => void;
}) {
  return (
    <Panel id="holding-plan" title="1–3 month holding plan" icon={CalendarClock}>
      <DataView state={state} onRetry={onRetry}>
        {(plan, response) => {
          const fit = FIT[plan.fit];
          return (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className={`rounded border px-2 py-0.5 text-sm font-medium ${fit.tone}`}>
                  {fit.label} for a 1–3 month hold
                </span>
                <span className="text-sm text-ink-muted">{fit.text}</span>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Level
                  label={`Price (${formatDate(plan.as_of)} close)`}
                  price={plan.price}
                  note={
                    plan.typical_move_3m !== null
                      ? `Typical 3-month move: about ±${(plan.typical_move_3m * 100).toFixed(0)}%`
                      : "Not enough history for a typical move."
                  }
                />
                <Level
                  label="Stop-loss: sell if it closes below"
                  price={plan.stop_price}
                  change={pct(plan.stop_pct)}
                  tone="text-negative"
                  note={`2.5× its average daily range (${formatNumber(plan.atr)}), so normal swings don't trigger it.`}
                />
                <Level
                  label="Target: consider taking profit"
                  price={plan.target_price}
                  change={pct(plan.target_pct)}
                  tone="text-positive"
                  note="Twice the stop distance: risk 1 to make 2."
                />
                <Level
                  label="Trend line: 50-day average"
                  price={plan.sma_50}
                  note="Two closes in a row below it means the short-term trend has turned."
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
                    Timeline if bought today
                  </h3>
                  <ul className="space-y-1.5 text-sm text-ink-muted">
                    <li>
                      <span className="text-ink">{formatDate(plan.check_in_on)}</span> — 1-month
                      check-in: rescore it; if it hasn&apos;t moved and the score fell, free up the
                      money.
                    </li>
                    {plan.next_earnings && (
                      <li>
                        <span className="text-ink">~{formatDate(plan.next_earnings)}</span> —
                        expected earnings (estimated from past reports): rescore after it.
                      </li>
                    )}
                    <li>
                      <span className="text-ink">{formatDate(plan.ends_on)}</span> — 3 months: plan
                      ends. Sell, or keep only if a fresh score and the trend still support it.
                    </li>
                  </ul>
                  <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wider text-ink-faint">
                    Sell early if
                  </h3>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-ink-muted">
                    <li>It closes below the stop-loss ({formatNumber(plan.stop_price)}).</li>
                    <li>It closes below the 50-day average two days in a row.</li>
                    <li>The score drops below 60 after you rescore it.</li>
                    <li>
                      It reaches the target: sell part, and raise the stop to your buy price on
                      the rest.
                    </li>
                  </ul>
                </div>

                <div>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
                    Trend checks
                  </h3>
                  <ul className="space-y-2">
                    {plan.checks.map((check) => (
                      <li key={check.label} className="flex gap-2 text-sm">
                        {check.passed ? (
                          <Check className="mt-0.5 size-4 shrink-0 text-positive" aria-label="Pass" />
                        ) : (
                          <X className="mt-0.5 size-4 shrink-0 text-negative" aria-label="Fail" />
                        )}
                        <span>
                          <span className="text-ink">{check.label}</span>
                          <span className="block text-xs text-ink-muted">{check.detail}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                  {plan.driver && <p className="mt-3 text-sm text-ink-muted">{plan.driver}</p>}
                </div>
              </div>

              <ContextRow plan={plan} />

              {plan.warnings.length > 0 && (
                <ul className="space-y-2">
                  {plan.warnings.map((warning) => (
                    <li
                      key={warning}
                      className="flex gap-2 rounded-md border border-warning/30 bg-warning-soft p-3 text-sm text-ink"
                    >
                      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
                      {warning}
                    </li>
                  ))}
                </ul>
              )}

              <p className="text-xs text-ink-faint">
                Guidance from fixed rules applied to this stock&apos;s own prices, not a prediction.
                The levels are set when you use Track this call and shown on Performance Tracking.
              </p>
              <SourceNote source={response.source} asOf={response.as_of} />
            </div>
          );
        }}
      </DataView>
    </Panel>
  );
}

const DIRECTION: Record<SectorTrend["direction"], { text: string; tone: string }> = {
  up: { text: "Uptrend", tone: "text-positive" },
  down: { text: "Downtrend", tone: "text-negative" },
  mixed: { text: "No clear trend", tone: "text-warning" },
};

function ContextRow({ plan }: { plan: HoldingPlan }) {
  if (plan.context.length === 0 && plan.context_missing.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
        Sector{plan.context.some((t) => t.kind === "oil") || plan.context_missing.includes("USO") ? " and oil" : ""} right now
      </h3>
      <div className="grid gap-3 sm:grid-cols-2">
        {plan.context.map((t) => {
          const d = DIRECTION[t.direction];
          return (
            <div key={t.symbol} className="rounded-md border border-line p-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm text-ink">{t.label}</span>
                <span className={`text-sm font-medium ${d.tone}`}>{d.text}</span>
              </div>
              <dl className="mt-2 grid grid-cols-3 gap-2 font-mono text-xs">
                <div>
                  <dt className="font-sans text-ink-faint">vs 50-day</dt>
                  <dd className={t.vs_sma_50 >= 0 ? "text-positive" : "text-negative"}>{pct(t.vs_sma_50)}</dd>
                </div>
                <div>
                  <dt className="font-sans text-ink-faint">1 month</dt>
                  <dd className={(t.return_1m ?? 0) >= 0 ? "text-positive" : "text-negative"}>{pct(t.return_1m)}</dd>
                </div>
                <div>
                  <dt className="font-sans text-ink-faint">3 months</dt>
                  <dd className={(t.return_3m ?? 0) >= 0 ? "text-positive" : "text-negative"}>{pct(t.return_3m)}</dd>
                </div>
              </dl>
              {t.stock_vs_1m !== null && (
                <p className="mt-2 text-xs text-ink-muted">
                  {plan.ticker} vs this over 1 month: {pct(t.stock_vs_1m)}
                </p>
              )}
            </div>
          );
        })}
      </div>
      {plan.context_missing.length > 0 && (
        <p className="mt-2 text-xs text-ink-muted">
          Prices for {plan.context_missing.join(" and ")} are not loaded yet. Click Calculate score
          to load them (they refresh at most every 6 hours).
        </p>
      )}
    </div>
  );
}
