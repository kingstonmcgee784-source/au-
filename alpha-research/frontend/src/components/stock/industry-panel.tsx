"use client";

import { Factory } from "lucide-react";
import Link from "next/link";

import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import type { DataResponse, IndustryComparison } from "@/lib/api/types";
import { formatCompact, formatNumber } from "@/lib/format";
import type { ApiState } from "@/lib/hooks/use-api";

const LABELS: Record<string, string> = {
  revenue_growth_ttm: "Revenue growth",
  operating_margin: "Operating margin",
  fcf_margin: "FCF margin",
  roe: "Return on equity",
  return_6m: "6-month return",
  pe_ttm: "P/E (lower is cheaper)",
  price_to_sales: "Price/sales (lower is cheaper)",
  ev_to_sales: "EV/sales (lower is cheaper)",
  fcf_yield: "FCF yield (higher is cheaper)",
};

const TABLE: [string, string, "money" | "percent" | "multiple"][] = [
  ["market_cap", "Mkt cap", "money"],
  ["revenue_growth_ttm", "Rev growth", "percent"],
  ["operating_margin", "Op margin", "percent"],
  ["roe", "ROE", "percent"],
  ["pe_ttm", "P/E", "multiple"],
  ["price_to_sales", "P/S", "multiple"],
  ["return_6m", "6m return", "percent"],
];

function cell(value: number | null | undefined, format: "money" | "percent" | "multiple"): string {
  if (value === null || value === undefined) return "—";
  if (format === "money") return `$${formatCompact(value)}`;
  if (format === "percent") return `${(value * 100).toFixed(1)}%`;
  return `${formatNumber(value, 1)}×`;
}

function Rank({ title, values }: { title: string; values: Record<string, number | null> }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">{title}</h3>
      <ul className="space-y-2">
        {Object.entries(values).map(([key, pct]) => (
          <li key={key}>
            <div className="flex justify-between text-xs">
              <span className="text-ink-muted">{LABELS[key] ?? key}</span>
              <span className="font-mono text-ink">
                {pct === null ? "—" : `better than ${Math.round(pct * 100)}%`}
              </span>
            </div>
            <div className="mt-1 h-1 rounded bg-surface-raised">
              {pct !== null && <div className="h-1 rounded bg-accent" style={{ width: `${pct * 100}%` }} />}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function IndustryPanel({
  state,
  onRetry,
}: {
  state: ApiState<DataResponse<IndustryComparison>>;
  onRetry: () => void;
}) {
  return (
    <Panel id="industry" title="Industry comparison" icon={Factory} collapsible>
      <DataView state={state} onRetry={onRetry}>
        {(data, response) => (
          <>
            <p className="mb-4 text-sm text-ink-muted">
              {data.industry ?? "Industry"} · peer group {data.peer_group} ·{" "}
              {data.rows.length - 1} peers scored in this app
            </p>
            <div className="grid gap-6 md:grid-cols-2">
              <Rank title="Positioning (scored)" values={data.positioning} />
              <Rank title="Valuation vs peers (for reference)" values={data.valuation} />
            </div>
            <div className="-mx-4 mt-5 overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-b border-line text-right text-[11px] uppercase tracking-wider text-ink-faint">
                    <th className="px-4 py-2 text-left font-medium">Stock</th>
                    <th className="px-3 py-2 font-medium">Score</th>
                    {TABLE.map(([key, label]) => (
                      <th key={key} className="px-3 py-2 font-medium">
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row) => (
                    <tr
                      key={row.ticker}
                      className={`border-b border-line/60 text-right last:border-0 ${row.is_subject ? "bg-accent-soft" : ""}`}
                    >
                      <td className="px-4 py-1.5 text-left">
                        <Link
                          href={`/analysis?ticker=${row.ticker}`}
                          className="font-mono font-semibold text-accent hover:underline"
                        >
                          {row.ticker}
                        </Link>
                      </td>
                      <td className="px-3 py-1.5 font-mono">{formatNumber(row.score, 0)}</td>
                      {TABLE.map(([key, , format]) => (
                        <td key={key} className="px-3 py-1.5 font-mono text-ink">
                          {cell(row.metrics[key], format)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11px] text-ink-faint">
              Peers are the other stocks scored in this app with the same SEC industry code (SIC),
              widened to related codes when there are fewer than four. The comparison is only as
              broad as the stocks you have scanned. Positioning feeds the score; valuation vs
              peers is shown for reference.
            </p>
            <SourceNote source={response.source} asOf={response.as_of} />
          </>
        )}
      </DataView>
    </Panel>
  );
}
