"use client";

import { ArrowDown, ArrowUp, Filter } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/states";
import type { ScreenerRow } from "@/lib/api/types";
import { formatCompact, formatDate, formatNumber } from "@/lib/format";

type Format = "score" | "money" | "multiple" | "percent" | "count";

interface Column {
  key: string;
  label: string;
  format: Format;
  value: (row: ScreenerRow) => number | null;
}

const metric = (key: string) => (row: ScreenerRow) => row.metrics[key] ?? null;

const COLUMNS: Column[] = [
  { key: "score", label: "Score", format: "score", value: (r) => r.score },
  { key: "market_cap", label: "Mkt cap", format: "money", value: metric("market_cap") },
  { key: "pe_ttm", label: "P/E", format: "multiple", value: metric("pe_ttm") },
  { key: "price_to_sales", label: "P/S", format: "multiple", value: metric("price_to_sales") },
  { key: "fcf_yield", label: "FCF yield", format: "percent", value: metric("fcf_yield") },
  { key: "revenue_growth_ttm", label: "Rev growth", format: "percent", value: metric("revenue_growth_ttm") },
  { key: "operating_margin", label: "Op margin", format: "percent", value: metric("operating_margin") },
  { key: "return_6m", label: "6m return", format: "percent", value: metric("return_6m") },
  { key: "insider_buyers", label: "Insider buyers", format: "count", value: metric("insider_buyers") },
];

function show(value: number | null, format: Format): string {
  if (value === null) return "—";
  switch (format) {
    case "score":
      return formatNumber(value, 0);
    case "money":
      return `$${formatCompact(value)}`;
    case "multiple":
      return `${formatNumber(value, 1)}×`;
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "count":
      return formatNumber(value, 0);
  }
}

interface Filters {
  minScore: string;
  maxPe: string;
  minGrowth: string;
  minCapM: string;
  maxCapM: string;
  maxDilution: string;
  insiderBuying: boolean;
  risks: Set<string>;
}

const RISKS = ["Low", "Moderate", "Elevated", "High", "Speculative"];

const EMPTY: Filters = {
  minScore: "",
  maxPe: "",
  minGrowth: "",
  minCapM: "",
  maxCapM: "",
  maxDilution: "",
  insiderBuying: false,
  risks: new Set(RISKS),
};

const num = (text: string): number | null => (text.trim() === "" ? null : Number(text));

/** Keep a row only if it meets every filter that is set. Missing data fails a set filter. */
function passes(row: ScreenerRow, f: Filters): boolean {
  const checks: [number | null, number | null, (v: number, limit: number) => boolean][] = [
    [row.score, num(f.minScore), (v, l) => v >= l],
    [row.metrics.pe_ttm ?? null, num(f.maxPe), (v, l) => v <= l],
    [row.metrics.revenue_growth_ttm ?? null, num(f.minGrowth), (v, l) => v * 100 >= l],
    [row.metrics.market_cap ?? null, num(f.minCapM), (v, l) => v >= l * 1e6],
    [row.metrics.market_cap ?? null, num(f.maxCapM), (v, l) => v <= l * 1e6],
    [row.metrics.share_change_yoy ?? null, num(f.maxDilution), (v, l) => v * 100 <= l],
  ];
  for (const [value, limit, test] of checks) {
    if (limit === null || Number.isNaN(limit)) continue;
    if (value === null || !test(value, limit)) return false;
  }
  if (f.insiderBuying && !((row.metrics.insider_buyers ?? 0) >= 1)) return false;
  if (row.risk_class && !f.risks.has(row.risk_class)) return false;
  return true;
}

export function ResultsTable({ rows }: { rows: ScreenerRow[] }) {
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [sort, setSort] = useState<{ key: string; desc: boolean }>({ key: "score", desc: true });

  const shown = useMemo(() => {
    const column = COLUMNS.find((c) => c.key === sort.key) ?? COLUMNS[0];
    return rows
      .filter((row) => passes(row, filters))
      .sort((a, b) => {
        const va = column.value(a);
        const vb = column.value(b);
        if (va === null && vb === null) return 0;
        if (va === null) return 1; // missing values last
        if (vb === null) return -1;
        return sort.desc ? vb - va : va - vb;
      });
  }, [rows, filters, sort]);

  if (rows.length === 0) {
    return (
      <Panel title="Results" icon={Filter}>
        <EmptyState title="No scored stocks yet">
          Scan a list of tickers above. Every stock you score anywhere in the app appears here.
        </EmptyState>
      </Panel>
    );
  }

  const set = (patch: Partial<Filters>) => setFilters((f) => ({ ...f, ...patch }));
  const input = (key: keyof Filters, label: string, placeholder: string) => (
    <label className="space-y-1 text-xs text-ink-muted">
      <span className="block">{label}</span>
      <input
        type="number"
        value={filters[key] as string}
        onChange={(e) => set({ [key]: e.target.value } as Partial<Filters>)}
        placeholder={placeholder}
        className="h-8 w-28 rounded-md border border-line bg-canvas px-2 font-mono text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:ring-1 focus:ring-accent"
      />
    </label>
  );

  return (
    <Panel title={`Results (${shown.length} of ${rows.length})`} icon={Filter}>
      <div className="flex flex-wrap items-end gap-3">
        {input("minScore", "Min score", "60")}
        {input("maxPe", "Max P/E", "30")}
        {input("minGrowth", "Min revenue growth %", "10")}
        {input("minCapM", "Min market cap ($M)", "300")}
        {input("maxCapM", "Max market cap ($M)", "10000")}
        {input("maxDilution", "Max share dilution %", "5")}
        <label className="flex h-8 items-center gap-2 text-xs text-ink-muted">
          <input
            type="checkbox"
            checked={filters.insiderBuying}
            onChange={(e) => set({ insiderBuying: e.target.checked })}
          />
          Insider buying
        </label>
        <button
          type="button"
          onClick={() => setFilters({ ...EMPTY, risks: new Set(RISKS) })}
          className="h-8 text-xs text-ink-faint hover:text-accent"
        >
          Clear filters
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink-muted">
        <span>Risk:</span>
        {RISKS.map((risk) => (
          <label key={risk} className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={filters.risks.has(risk)}
              onChange={(e) => {
                const risks = new Set(filters.risks);
                if (e.target.checked) risks.add(risk);
                else risks.delete(risk);
                set({ risks });
              }}
            />
            {risk}
          </label>
        ))}
      </div>

      <div className="-mx-4 mt-4 overflow-x-auto">
        <table className="w-full min-w-[1080px] text-sm">
          <thead>
            <tr className="border-b border-line text-right text-[11px] uppercase tracking-wider text-ink-faint">
              <th className="px-4 py-2 text-left font-medium">Stock</th>
              {COLUMNS.map((column) => (
                <th key={column.key} className="px-3 py-2 font-medium">
                  <button
                    type="button"
                    onClick={() =>
                      setSort((s) => ({ key: column.key, desc: s.key === column.key ? !s.desc : true }))
                    }
                    className="inline-flex items-center gap-1 uppercase hover:text-ink"
                  >
                    {column.label}
                    {sort.key === column.key &&
                      (sort.desc ? <ArrowDown className="size-3" /> : <ArrowUp className="size-3" />)}
                  </button>
                </th>
              ))}
              <th className="px-3 py-2 text-left font-medium">Risk</th>
              <th className="px-3 py-2 text-left font-medium">Scored</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={row.ticker} className="border-b border-line/60 text-right last:border-0">
                <td className="max-w-56 px-4 py-2 text-left">
                  <Link
                    href={`/analysis?ticker=${row.ticker}`}
                    className="font-mono font-semibold text-accent hover:underline"
                  >
                    {row.ticker}
                  </Link>
                  <span className="block truncate text-xs text-ink-faint" title={row.industry ?? undefined}>
                    {row.name}
                  </span>
                </td>
                {COLUMNS.map((column) => (
                  <td key={column.key} className="px-3 py-2 font-mono text-ink">
                    {show(column.value(row), column.format)}
                    {column.key === "score" && row.coverage < 1 && (
                      <span className="block text-[10px] text-ink-faint">
                        {Math.round(row.coverage * 100)}% cov.
                      </span>
                    )}
                  </td>
                ))}
                <td className="px-3 py-2 text-left">
                  {row.risk_class ? <Badge>{row.risk_class}</Badge> : "—"}
                </td>
                <td className="px-3 py-2 text-left text-xs text-ink-faint">{formatDate(row.scored_on)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px] text-ink-faint">
        Every stock scored in this app, with its latest score and metrics. A stock missing a
        metric is left out when you filter on that metric. Click a column to sort.
      </p>
    </Panel>
  );
}
