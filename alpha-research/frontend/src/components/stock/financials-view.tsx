"use client";

import { FileSpreadsheet } from "lucide-react";
import { useState } from "react";

import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import type { FinancialStatement, PeriodType, StatementType } from "@/lib/api/types";
import { formatCompact, formatDate, formatNumber, humanize } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";

import { SyncFinancialsButton } from "./sync-prices-button";
import { TickerForm, useTickerParam } from "./ticker-form";

const STATEMENTS: { value: StatementType; label: string }[] = [
  { value: "income", label: "Income statement" },
  { value: "balance", label: "Balance sheet" },
  { value: "cashflow", label: "Cash flow" },
];

const PERIODS: { value: PeriodType; label: string }[] = [
  { value: "quarterly", label: "Quarterly" },
  { value: "annual", label: "Annual" },
  { value: "ttm", label: "TTM" },
];

export function FinancialsView() {
  const ticker = useTickerParam();
  const [statementType, setStatementType] = useState<StatementType>("income");
  const [periodType, setPeriodType] = useState<PeriodType>("quarterly");

  const key = ticker ? `financials-${ticker}-${statementType}-${periodType}` : null;
  const { state, reload } = useApi(key, () =>
    api.financials(ticker as string, { statementType, periodType }),
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start gap-4">
        <TickerForm key={ticker ?? ""} current={ticker} />
        {ticker && <SyncFinancialsButton key={`sync-${ticker}`} ticker={ticker} onSynced={reload} />}
      </div>
      <div className="flex flex-wrap items-start gap-4">
        <Segmented options={STATEMENTS} value={statementType} onChange={setStatementType} />
        <Segmented options={PERIODS} value={periodType} onChange={setPeriodType} />
      </div>
      {ticker ? (
        <Panel title={`${ticker} · ${humanize(statementType)} · ${periodType}`} icon={FileSpreadsheet}>
          <DataView state={state} onRetry={reload} loadingLabel="Loading statements">
            {(statements, response) => (
              <>
                <StatementTable statements={statements} />
                <SourceNote source={response.source} asOf={response.as_of} />
              </>
            )}
          </DataView>
        </Panel>
      ) : (
        <EmptyState title="Choose a stock">Enter a ticker to load its financial statements.</EmptyState>
      )}
    </div>
  );
}

function StatementTable({ statements }: { statements: FinancialStatement[] }) {
  // Union of line items across periods, in first-seen order.
  const lineItems = [...new Set(statements.flatMap((s) => Object.keys(s.line_items)))];
  const anyDerived = statements.some((s) => s.derived_items.length > 0);
  return (
    <>
      <div className="-mx-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-wider text-ink-faint">
              <th className="sticky left-0 bg-surface px-4 py-2 text-left font-medium">Line item</th>
              {statements.map((s) => (
                <th key={s.period_end} className="px-4 py-2 text-right font-medium whitespace-nowrap">
                  {periodLabel(s)}
                  <span className="block font-normal normal-case">{formatDate(s.period_end)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lineItems.map((item) => (
              <tr key={item} className="border-b border-line/60 last:border-0">
                <td className="sticky left-0 bg-surface px-4 py-1.5 whitespace-nowrap text-ink-muted">
                  {humanize(item)}
                </td>
                {statements.map((s) => {
                  const derived = s.derived_items.includes(item);
                  return (
                    <td
                      key={s.period_end}
                      className="px-4 py-1.5 text-right font-mono whitespace-nowrap text-ink"
                      title={derived ? "Calculated from year-to-date figures" : undefined}
                    >
                      {formatValue(item, s.line_items[item])}
                      {derived && <sup className="ml-0.5 text-[9px] text-warning">d</sup>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px] text-ink-faint">
        Figures from 10-K and 10-Q filings; when a period was restated, the latest filing is used.
        {anyDerived && (
          <>
            {" "}
            <sup className="text-warning">d</sup> Not reported for the quarter on its own; calculated
            as the difference of two year-to-date figures (for example Q4 = full year minus nine
            months).
          </>
        )}
      </p>
    </>
  );
}

function periodLabel(statement: FinancialStatement): string {
  if (statement.period_type === "annual") return `FY${statement.fiscal_year}`;
  if (statement.fiscal_quarter) return `Q${statement.fiscal_quarter} FY${statement.fiscal_year}`;
  return "Period";
}

/** Per-share values keep cents; everything else is shown compactly. */
function formatValue(item: string, value: number | null | undefined): string {
  if (item.startsWith("eps_")) return formatNumber(value);
  return formatCompact(value);
}

function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-line p-0.5" role="group">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
          className={`rounded px-3 py-1.5 text-xs ${
            option.value === value ? "bg-surface-raised text-ink" : "text-ink-muted hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
