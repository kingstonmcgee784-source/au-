"use client";

import { Calculator, Gauge } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import { api } from "@/lib/api/client";
import type { CategoryScore, DataResponse, MetricsSnapshot, StockScore } from "@/lib/api/types";
import { formatCompact, formatDate, formatNumber } from "@/lib/format";
import type { ApiState } from "@/lib/hooks/use-api";

import { SyncButton } from "./sync-button";

/** Refresh the stock's data, calculate its metrics and score it. */
export function CalculateScoreButton({
  ticker,
  onScored,
}: {
  ticker: string;
  onScored: () => void;
}) {
  return (
    <SyncButton
      label="Calculate score"
      busyLabel="Loading data and scoring…"
      run={() => api.calculateScore(ticker)}
      describe={(s) =>
        `Scored ${formatNumber(s.total_score, 0)}/100 using ${Math.round(s.coverage * 100)}% of ` +
        "the methodology. Prices and SEC filings were refreshed first."
      }
      onSynced={onScored}
    />
  );
}

export function ScorePanel({
  state,
  onRetry,
}: {
  state: ApiState<DataResponse<StockScore>>;
  onRetry: () => void;
}) {
  return (
    <Panel title="Research score" icon={Gauge}>
      <DataView state={state} onRetry={onRetry}>
        {(score, response) => (
          <>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <p className="font-mono text-3xl text-ink">
                {formatNumber(score.total_score, 0)}
                <span className="text-sm text-ink-faint"> / 100</span>
              </p>
              {score.risk_class && <Badge tone="neutral">Risk: {score.risk_class}</Badge>}
            </div>
            <p className="text-sm text-ink-muted">{score.interpretation}</p>
            <p className="mt-1 text-xs text-warning">
              Based on {Math.round(score.coverage * 100)}% of the methodology. Categories without
              data are left out, not counted as zero.
            </p>
            <ul className="mt-4 space-y-2.5">
              {score.categories.map((category) => (
                <CategoryRow key={category.key} category={category} />
              ))}
            </ul>
            <p className="mt-3 text-xs text-ink-faint">
              Prices as of {formatDate(score.as_of)} · methodology v{score.methodology_version}
            </p>
            {score.notes && <p className="mt-1 text-[11px] text-ink-faint">{score.notes}</p>}
            <SourceNote source={response.source} asOf={response.as_of} />
          </>
        )}
      </DataView>
    </Panel>
  );
}

function CategoryRow({ category }: { category: CategoryScore }) {
  const rated = category.points !== null;
  const share = rated ? (category.points as number) / category.weight : 0;
  const inputs = Object.entries(category.inputs);
  return (
    <li title={rated ? inputs.map(([k, v]) => `${k}: ${Math.round(v * 100)}%`).join("\n") : undefined}>
      <div className="flex justify-between gap-3 text-xs">
        <span className={rated ? "text-ink-muted" : "text-ink-faint"}>{category.label}</span>
        <span className="font-mono text-ink">
          {rated ? (
            <>
              {formatNumber(category.points, 1)}
              <span className="text-ink-faint"> / {category.weight}</span>
            </>
          ) : (
            <span className="text-ink-faint">no data</span>
          )}
        </span>
      </div>
      <div className="mt-1 h-1 rounded bg-surface-raised">
        {rated && <div className="h-1 rounded bg-accent" style={{ width: `${share * 100}%` }} />}
      </div>
      {!rated && category.unrated_reason && (
        <p className="mt-0.5 text-[11px] text-ink-faint">{category.unrated_reason}</p>
      )}
    </li>
  );
}

type Format = "money" | "percent" | "multiple" | "ratio" | "price";

const METRIC_GROUPS: { title: string; metrics: [string, string, Format][] }[] = [
  {
    title: "Valuation",
    metrics: [
      ["market_cap", "Market cap", "money"],
      ["enterprise_value", "Enterprise value", "money"],
      ["pe_ttm", "P/E (TTM)", "multiple"],
      ["price_to_sales", "Price / sales", "multiple"],
      ["ev_to_sales", "EV / sales", "multiple"],
      ["ev_to_ebitda", "EV / EBITDA", "multiple"],
      ["price_to_book", "Price / book", "multiple"],
      ["fcf_yield", "FCF yield", "percent"],
    ],
  },
  {
    title: "Profitability (TTM)",
    metrics: [
      ["revenue_ttm", "Revenue", "money"],
      ["net_income_ttm", "Net income", "money"],
      ["free_cash_flow_ttm", "Free cash flow", "money"],
      ["gross_margin", "Gross margin", "percent"],
      ["operating_margin", "Operating margin", "percent"],
      ["net_margin", "Net margin", "percent"],
      ["fcf_margin", "FCF margin", "percent"],
      ["roe", "Return on equity", "percent"],
      ["sbc_to_revenue", "Stock comp / revenue", "percent"],
    ],
  },
  {
    title: "Growth",
    metrics: [
      ["revenue_growth_yoy", "Revenue, latest quarter YoY", "percent"],
      ["revenue_growth_ttm", "Revenue, TTM YoY", "percent"],
      ["net_income_growth_ttm", "Net income, TTM YoY", "percent"],
      ["revenue_acceleration", "Revenue growth acceleration", "percent"],
    ],
  },
  {
    title: "Balance sheet",
    metrics: [
      ["net_cash", "Net cash", "money"],
      ["current_ratio", "Current ratio", "ratio"],
      ["debt_to_equity", "Debt / equity", "ratio"],
      ["share_change_yoy", "Share count change YoY", "percent"],
    ],
  },
  {
    title: "Price behaviour",
    metrics: [
      ["price", "Last close", "price"],
      ["price_vs_sma200", "vs 200-day average", "percent"],
      ["rsi_14", "RSI (14)", "ratio"],
      ["return_3m", "3-month return", "percent"],
      ["return_6m", "6-month return", "percent"],
      ["relative_strength_6m", "6-month vs S&P 500", "percent"],
      ["volatility_1y", "Volatility (1y)", "percent"],
      ["max_drawdown_1y", "Max drawdown (1y)", "percent"],
      ["from_52w_high", "From 52-week high", "percent"],
    ],
  },
];

function formatMetric(value: number | null | undefined, format: Format): string {
  if (value === null || value === undefined) return "—";
  switch (format) {
    case "money":
      return `$${formatCompact(value)}`;
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "multiple":
      return `${formatNumber(value, 1)}×`;
    case "price":
      return formatNumber(value);
    case "ratio":
      return formatNumber(value, 2);
  }
}

export function MetricsPanel({
  state,
  onRetry,
}: {
  state: ApiState<DataResponse<MetricsSnapshot>>;
  onRetry: () => void;
}) {
  return (
    <Panel title="Key metrics" icon={Calculator}>
      <DataView state={state} onRetry={onRetry}>
        {(snapshot, response) => (
          <>
            <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-5">
              {METRIC_GROUPS.map((group) => (
                <div key={group.title}>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-faint">
                    {group.title}
                  </h3>
                  <dl className="space-y-1.5 text-sm">
                    {group.metrics.map(([key, label, format]) => (
                      <div key={key} className="flex justify-between gap-3">
                        <dt className="text-ink-muted">{label}</dt>
                        <dd className="font-mono text-ink">
                          {formatMetric(snapshot.values[key], format)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ))}
            </div>
            <p className="mt-4 text-[11px] text-ink-faint">
              Calculated by Alpha Research from stored Tiingo prices and SEC filings, as of{" "}
              {formatDate(snapshot.as_of)}. TTM sums the last four reported quarters. A dash means
              the inputs are missing or the metric is not meaningful (for example P/E with negative
              earnings, or EV when debt is not reported).
            </p>
            <SourceNote source={response.source} asOf={response.as_of} />
          </>
        )}
      </DataView>
    </Panel>
  );
}
