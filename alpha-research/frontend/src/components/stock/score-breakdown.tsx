"use client";

import { ChevronDown, ChevronRight, ListTree } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DataView } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import type { CategoryScore, DataResponse, StockScore } from "@/lib/api/types";
import { formatNumber } from "@/lib/format";
import type { ApiState } from "@/lib/hooks/use-api";

/** Where to see the raw data behind each category. */
function detailLink(key: string, ticker: string): { href: string; label: string } | null {
  switch (key) {
    case "fundamentals":
    case "growth":
      return { href: `/financials?ticker=${ticker}`, label: "Financial statements" };
    case "valuation":
      return { href: "#key-metrics", label: "Key metrics" };
    case "technical":
    case "risk_reward":
      return { href: `/technical?ticker=${ticker}`, label: "Technical analysis" };
    case "catalysts":
      return { href: `/news?ticker=${ticker}`, label: "Events and earnings date" };
    case "institutional":
      return { href: "#insiders", label: "Insider activity" };
    case "industry":
      return { href: "#industry", label: "Industry comparison" };
    default:
      return null;
  }
}

const WHAT_IT_MEASURES: Record<string, string> = {
  fundamentals: "Profitability, cash generation, balance-sheet strength and share dilution.",
  valuation: "How expensive the stock is relative to its earnings, cash flow and sales.",
  technical: "Price trend and momentum, including performance against the S&P 500.",
  growth: "How fast revenue and earnings are growing, and whether growth is speeding up.",
  catalysts: "Company events from SEC 8-K filings and the next estimated earnings date.",
  institutional: "Insider buying and selling from SEC Form 4 filings (no 13F data yet).",
  industry: "How the stock ranks against stored peers with the same SEC industry code.",
  risk_reward: "Volatility, drawdowns and distance from the 52-week high.",
};

function barColor(rating: number): string {
  if (rating >= 0.7) return "bg-positive";
  if (rating >= 0.4) return "bg-accent";
  return "bg-negative";
}

export function ScoreBreakdownPanel({
  ticker,
  state,
  onRetry,
}: {
  ticker: string;
  state: ApiState<DataResponse<StockScore>>;
  onRetry: () => void;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const toggle = (key: string) =>
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <Panel title="Score breakdown" icon={ListTree} id="score-breakdown">
      <DataView state={state} onRetry={onRetry}>
        {(score) => (
          <>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-muted">
              <span>
                Every input behind the {formatNumber(score.total_score, 0)}/100 score, its value,
                how it rated, and the scale it was judged on.
              </span>
              <span className="flex gap-3">
                <button
                  type="button"
                  className="hover:text-accent"
                  onClick={() => setCollapsed(new Set())}
                >
                  Expand all
                </button>
                <button
                  type="button"
                  className="hover:text-accent"
                  onClick={() => setCollapsed(new Set(score.categories.map((c) => c.key)))}
                >
                  Collapse all
                </button>
              </span>
            </div>
            <div className="divide-y divide-line/60 rounded-md border border-line">
              {score.categories.map((category) => (
                <CategorySection
                  key={category.key}
                  ticker={ticker}
                  category={category}
                  open={!collapsed.has(category.key)}
                  onToggle={() => toggle(category.key)}
                />
              ))}
            </div>
            <p className="mt-3 text-[11px] text-ink-faint">
              Each input is rated from 0% to 100% on the scale shown; a category&apos;s points are the
              average of its inputs times its weight. Thresholds are the same for every industry
              (methodology v{score.methodology_version}), so read them alongside the industry
              comparison.
            </p>
          </>
        )}
      </DataView>
    </Panel>
  );
}

function CategorySection({
  ticker,
  category,
  open,
  onToggle,
}: {
  ticker: string;
  category: CategoryScore;
  open: boolean;
  onToggle: () => void;
}) {
  const rated = category.points !== null;
  const share = rated ? (category.points as number) / category.weight : 0;
  const link = detailLink(category.key, ticker);
  const Chevron = open ? ChevronDown : ChevronRight;

  return (
    <div id={`breakdown-${category.key}`} className="scroll-mt-20">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-surface-raised/50"
      >
        <Chevron className="size-4 shrink-0 text-ink-faint" aria-hidden />
        <span className={`flex-1 text-sm ${rated ? "text-ink" : "text-ink-faint"}`}>
          {category.label}
        </span>
        <span className="hidden w-40 sm:block">
          <span className="block h-1 rounded bg-surface-raised">
            {rated && (
              <span className="block h-1 rounded bg-accent" style={{ width: `${share * 100}%` }} />
            )}
          </span>
        </span>
        <span className="w-20 text-right font-mono text-sm">
          {rated ? (
            <>
              {formatNumber(category.points, 1)}
              <span className="text-ink-faint"> / {category.weight}</span>
            </>
          ) : (
            <span className="text-ink-faint">no data</span>
          )}
        </span>
      </button>

      {open && (
        <div className="space-y-3 px-3 pb-4 pl-10">
          <p className="text-xs text-ink-muted">{WHAT_IT_MEASURES[category.key]}</p>
          {category.summary && <p className="text-sm text-ink">{category.summary}</p>}

          {category.breakdown.length > 0 && (
            <div className="-mx-3 overflow-x-auto">
              <table className="w-full min-w-[640px] table-fixed text-sm">
                <colgroup>
                  <col className="w-[26%]" />
                  <col className="w-[10%]" />
                  <col className="w-[14%]" />
                  <col className="w-[50%]" />
                </colgroup>
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-wider text-ink-faint">
                    <th className="px-3 py-1 font-medium">Input</th>
                    <th className="px-3 py-1 text-right font-medium">Value</th>
                    <th className="px-3 py-1 font-medium">Rating</th>
                    <th className="px-3 py-1 font-medium">Why it got this rating</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/40">
                  {category.breakdown.map((input) => (
                    <tr key={input.metric} className="align-top">
                      <td className="px-3 py-1.5 text-ink">
                        {input.label}
                        {input.meaning && (
                          <span className="mt-0.5 block text-[11px] leading-snug text-ink-faint">
                            {input.meaning}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono whitespace-nowrap text-ink">
                        {input.value_text ?? "—"}
                      </td>
                      <td className="px-3 py-1.5">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-24 rounded bg-surface-raised">
                            <div
                              className={`h-1.5 rounded ${barColor(input.rating)}`}
                              style={{ width: `${input.rating * 100}%` }}
                            />
                          </div>
                          <span className="font-mono text-xs text-ink-muted">
                            {Math.round(input.rating * 100)}%
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-1.5 text-xs">
                        {input.explanation && (
                          <span className="block text-ink-muted">{input.explanation}</span>
                        )}
                        {input.scale && (
                          <span className="mt-0.5 block text-ink-faint">Scale: {input.scale}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {category.missing.length > 0 && (
            <p className="text-xs text-ink-faint">
              <span className="text-warning">No data:</span> {category.missing.join(", ")}.
              {rated
                ? " These inputs were left out of the average."
                : ` At least ${category.minimum_inputs} inputs are needed to rate this category.`}
            </p>
          )}
          {!rated && category.unrated_reason && (
            <p className="text-xs text-ink-muted">{category.unrated_reason}</p>
          )}

          {link &&
            (link.href.startsWith("#") ? (
              <a href={link.href} className="inline-block text-xs text-accent hover:underline">
                See {link.label.toLowerCase()} →
              </a>
            ) : (
              <Link href={link.href} className="inline-block text-xs text-accent hover:underline">
                See {link.label.toLowerCase()} →
              </Link>
            ))}
        </div>
      )}
    </div>
  );
}
