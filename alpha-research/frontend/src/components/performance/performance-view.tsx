"use client";

import { BarChart3, ListChecks, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { SyncButton } from "@/components/stock/sync-button";
import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { ApiError, api } from "@/lib/api/client";
import type { TrackedCall } from "@/lib/api/types";
import { formatDate, formatNumber } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";

const HORIZONS: { key: string; label: string }[] = [
  { key: "1w", label: "After 1 week" },
  { key: "1m", label: "After 1 month" },
  { key: "3m", label: "After 3 months" },
  { key: "now", label: "Since the call" },
];

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}

function tone(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "text-ink-muted";
  return value > 0 ? "text-positive" : "text-negative";
}

export function PerformanceView() {
  const { state, reload } = useApi("track-record", api.trackRecord);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function remove(call: TrackedCall) {
    if (!window.confirm(`Remove the ${call.ticker} call from ${formatDate(call.recommended_on)}?`)) return;
    setDeleteError(null);
    try {
      await api.deleteCall(call.id);
      reload();
    } catch (error) {
      setDeleteError(error instanceof ApiError ? error.message : "Could not remove the call.");
    }
  }

  return (
    <div className="space-y-4">
      <SyncButton
        label="Update prices"
        busyLabel="Updating prices…"
        run={() => api.updateTrackedPrices()}
        isPartial={(d) => d.results.some((r) => !r.ok)}
        describe={(d) => {
          const failed = d.results.filter((r) => !r.ok);
          if (failed.length === 0) {
            return `Prices checked for ${d.results.length} tickers (each refreshed at most every 6 hours).`;
          }
          const updated = d.results.length - failed.length;
          if (d.rate_limited) {
            return `Tiingo's free plan allows 50 requests an hour, and that limit has been reached (a running scan uses it too). ${updated} of ${d.results.length} tickers were updated; try again in about an hour for ${failed.map((r) => r.ticker).join(", ")}.`;
          }
          return `Some prices could not be updated: ${failed.map((r) => `${r.ticker} (${r.message})`).join("; ")}`;
        }}
        onSynced={reload}
      />

      {state.kind === "loading" && <LoadingState label="Loading track record" />}
      {state.kind === "error" && <ErrorState error={state.error} onRetry={reload} />}
      {state.kind === "success" &&
        (state.data.calls.length === 0 ? (
          <Panel title="Track record" icon={ListChecks}>
            <EmptyState title="No calls tracked yet">
              Open a stock in{" "}
              <Link href="/analysis" className="text-accent hover:underline">
                Stock Analysis
              </Link>
              , calculate its score, then use <strong>Track this call</strong>. Its return is then
              measured here against the S&amp;P 500, Nasdaq 100 and Russell 2000.
            </EmptyState>
          </Panel>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {HORIZONS.map(({ key, label }) => {
                const s = state.data.summary[key] ?? {};
                const count = s.count ?? 0;
                return (
                  <Panel key={key} title={label} icon={BarChart3}>
                    {count === 0 ? (
                      <p className="text-sm text-ink-faint">
                        No call has reached this point yet.
                      </p>
                    ) : (
                      <dl className="space-y-1.5 text-sm">
                        <Stat label="Calls measured" value={formatNumber(count, 0)} />
                        <Stat label="Average return" value={pct(s.average)} className={tone(s.average)} />
                        <Stat label="Median return" value={pct(s.median)} className={tone(s.median)} />
                        <Stat label="Win rate" value={pct(s.win_rate).replace("+", "")} />
                        <Stat label="Average gain" value={pct(s.average_gain)} />
                        <Stat label="Average loss" value={pct(s.average_loss)} />
                        <Stat
                          label="Average vs S&P 500"
                          value={pct(s.average_excess_vs_spy)}
                          className={tone(s.average_excess_vs_spy)}
                        />
                        <Stat label="Beat the S&P 500" value={pct(s.beat_spy_rate).replace("+", "")} />
                      </dl>
                    )}
                  </Panel>
                );
              })}
            </div>

            <Panel title="Tracked calls" icon={ListChecks}>
              {deleteError && <p className="mb-3 text-sm text-negative">{deleteError}</p>}
              <div className="-mx-4 overflow-x-auto">
                <table className="w-full min-w-[1180px] text-sm">
                  <thead>
                    <tr className="border-b border-line text-right text-[11px] uppercase tracking-wider text-ink-faint">
                      <th className="px-4 py-2 text-left font-medium">Stock</th>
                      <th className="px-4 py-2 text-left font-medium">Called on</th>
                      <th className="px-4 py-2 font-medium">Score</th>
                      <th className="px-4 py-2 font-medium">Price then</th>
                      <th className="px-4 py-2 font-medium">Stop / target</th>
                      <th className="px-4 py-2 text-left font-medium">Plan</th>
                      <th className="px-4 py-2 font-medium">Price now</th>
                      <th className="px-4 py-2 font-medium">Return</th>
                      <th className="px-4 py-2 font-medium">vs S&amp;P</th>
                      <th className="px-4 py-2 font-medium">1 wk</th>
                      <th className="px-4 py-2 font-medium">1 mo</th>
                      <th className="px-4 py-2 font-medium">3 mo</th>
                      <th className="px-4 py-2 font-medium">Best</th>
                      <th className="px-4 py-2 font-medium">Worst</th>
                      <th className="px-4 py-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {state.data.calls.map((call) => {
                      const p = call.performance;
                      return (
                        <tr key={call.id} className="border-b border-line/60 text-right last:border-0">
                          <td className="px-4 py-2 text-left">
                            <Link
                              href={`/analysis?ticker=${call.ticker}`}
                              className="font-mono font-semibold text-accent hover:underline"
                            >
                              {call.ticker}
                            </Link>
                            {call.thesis && (
                              <span className="block max-w-56 truncate text-xs text-ink-faint" title={call.thesis}>
                                {call.thesis}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-2 text-left text-ink-muted">
                            {formatDate(call.recommended_on)}
                          </td>
                          <td className="px-4 py-2 font-mono">
                            {formatNumber(call.score, 0)}
                            {call.risk_class && (
                              <span className="ml-2">
                                <Badge>{call.risk_class}</Badge>
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-2 font-mono" title={call.reference_price_source}>
                            {formatNumber(call.reference_price)}
                          </td>
                          <td className="px-4 py-2 font-mono text-xs">
                            {call.stop_price !== null && call.target_price !== null ? (
                              <>
                                <span className="text-negative">{formatNumber(call.stop_price)}</span>
                                <span className="text-ink-faint"> / </span>
                                <span className="text-positive">{formatNumber(call.target_price)}</span>
                              </>
                            ) : (
                              <span className="text-ink-faint">—</span>
                            )}
                          </td>
                          <td className="whitespace-nowrap px-4 py-2 text-left">
                            <PlanStatus call={call} />
                          </td>
                          <td className="px-4 py-2 font-mono">
                            {p.current_price === null ? (
                              <span className="whitespace-nowrap text-xs text-ink-faint" title="The first closing price after the call date has not been loaded yet. Use Update prices after the market closes.">
                                waiting for next close
                              </span>
                            ) : (
                              formatNumber(p.current_price)
                            )}
                          </td>
                          <td className={`px-4 py-2 font-mono ${tone(p.return_now)}`}>{pct(p.return_now)}</td>
                          <td className={`px-4 py-2 font-mono ${tone(p.excess_vs_spy_now)}`}>
                            {pct(p.excess_vs_spy_now)}
                          </td>
                          {(["1w", "1m", "3m"] as const).map((h) => (
                            <td key={h} className={`px-4 py-2 font-mono ${tone(p[`return_${h}`])}`}>
                              {p[`return_${h}`] === null ? (
                                <span className="text-ink-faint">pending</span>
                              ) : (
                                pct(p[`return_${h}`])
                              )}
                            </td>
                          ))}
                          <td className="px-4 py-2 font-mono text-ink-muted">{pct(p.max_gain)}</td>
                          <td className="px-4 py-2 font-mono text-ink-muted">{pct(p.max_drawdown)}</td>
                          <td className="px-4 py-2">
                            {call.deletable && (
                              <button
                                type="button"
                                onClick={() => void remove(call)}
                                className="rounded p-1 text-ink-faint hover:text-negative"
                                aria-label={`Remove the ${call.ticker} call`}
                                title="Calls can be removed only within 24 hours of being recorded"
                              >
                                <Trash2 className="size-4" />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-[11px] text-ink-faint">
                Returns use adjusted closing prices, so dividends are included. A call is measured
                from the closing price on the day it was recorded. Each period is measured at the
                first trading day after it ends; until then it shows as pending. Calls cannot be
                edited, and can be removed only within 24 hours of being recorded. Past results do not
                predict future returns.
                {state.data.benchmarks_missing.length > 0 &&
                  ` Benchmark prices missing for ${state.data.benchmarks_missing.join(", ")}: use Update prices.`}
              </p>
            </Panel>
          </>
        ))}
    </div>
  );
}

function Stat({ label, value, className = "text-ink" }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-ink-muted">{label}</dt>
      <dd className={`font-mono ${className}`}>{value}</dd>
    </div>
  );
}

function PlanStatus({ call }: { call: TrackedCall }) {
  const when = call.plan_status_date ? formatDate(call.plan_status_date) : "";
  switch (call.plan_status) {
    case "stop_hit":
      return (
        <span className="text-xs text-negative" title="Closed at or below the stop-loss: the plan says sell.">
          Stop hit {when} — sell
        </span>
      );
    case "target_hit":
      return (
        <span className="text-xs text-positive" title="Closed at or above the target: consider taking profit.">
          Target hit {when}
        </span>
      );
    case "time_up":
      return (
        <span className="text-xs text-warning" title="The hold period is over: sell, or rescore before keeping it.">
          Time up {when} — review
        </span>
      );
    case "open":
      return <span className="text-xs text-ink-muted">Holding until {when}</span>;
    default:
      return <span className="text-xs text-ink-faint" title="Tracked before holding plans existed.">No plan</span>;
  }
}
