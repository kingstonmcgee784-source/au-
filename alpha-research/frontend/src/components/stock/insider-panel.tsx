"use client";

import { UserCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import { api } from "@/lib/api/client";
import type { DataResponse, InsiderActivity, InsiderTransaction } from "@/lib/api/types";
import { formatCompact, formatDate, formatNumber } from "@/lib/format";
import type { ApiState } from "@/lib/hooks/use-api";

import { SyncButton } from "./sync-button";

/** Load the last 180 days of Form 4 filings from SEC EDGAR. */
export function SyncInsidersButton({ ticker, onSynced }: { ticker: string; onSynced: () => void }) {
  return (
    <SyncButton
      label="Load insider filings"
      busyLabel="Reading Form 4 filings…"
      run={() => api.syncInsiders(ticker)}
      describe={(d) =>
        `${d.filings_added} new Form 4 filings read (${d.transactions_added} share transactions).` +
        (d.filings_remaining > 0
          ? ` ${d.filings_remaining} older filings remain: click again to load more.`
          : "")
      }
      onSynced={onSynced}
    />
  );
}

const MAX_ROWS = 25;

export function InsiderPanel({
  ticker,
  state,
  onRetry,
  onSynced,
}: {
  ticker: string;
  state: ApiState<DataResponse<InsiderActivity>>;
  onRetry: () => void;
  onSynced: () => void;
}) {
  return (
    <Panel
      id="insiders"
      title="Insider activity (Form 4, last 180 days)"
      icon={UserCheck}
      actions={<SyncInsidersButton key={`insiders-${ticker}`} ticker={ticker} onSynced={onSynced} />}
    >
      <DataView state={state} onRetry={onRetry}>
        {(activity, response) => (
          <>
            <Summary summary={activity.summary} />
            {activity.transactions.length === 0 ? (
              <p className="mt-4 text-sm text-ink-muted">
                No share transactions by insiders were reported in this period.
              </p>
            ) : (
              <TransactionTable rows={activity.transactions.slice(0, MAX_ROWS)} />
            )}
            {activity.transactions.length > MAX_ROWS && (
              <p className="mt-2 text-xs text-ink-faint">
                Showing the {MAX_ROWS} most recent of {activity.transactions.length} transactions.
              </p>
            )}
            <p className="mt-3 text-[11px] text-ink-faint">
              From SEC Form 4 filings. Open-market purchases are insiders buying with their own
              money. Sales marked 10b5-1 were scheduled in advance under a trading plan; other
              sales are discretionary. Grants, option exercises and tax withholding are
              compensation, not trading decisions. Amended filings (4/A) are not included.
            </p>
            <SourceNote source={response.source} asOf={response.as_of} />
          </>
        )}
      </DataView>
    </Panel>
  );
}

function Summary({ summary }: { summary: Record<string, number | null> }) {
  const items: [string, string][] = [
    ["Open-market buyers", formatNumber(summary.insider_buyers, 0)],
    ["Bought", `$${formatCompact(summary.insider_buy_value)}`],
    ["Sold under 10b5-1 plans", `$${formatCompact(summary.insider_planned_sale_value)}`],
    ["Sold outside plans", `$${formatCompact(summary.insider_discretionary_sale_value)}`],
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label} className="rounded-md border border-line p-3">
          <dt className="text-xs text-ink-muted">{label}</dt>
          <dd className="mt-1 font-mono text-base text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function kind(row: InsiderTransaction): { tone: "positive" | "negative" | "neutral"; text: string } {
  if (row.code === "P") return { tone: "positive", text: "Buy" };
  if (row.code === "S") return { tone: "negative", text: "Sell" };
  return { tone: "neutral", text: row.description };
}

function TransactionTable({ rows }: { rows: InsiderTransaction[] }) {
  return (
    <div className="-mx-4 mt-4 overflow-x-auto">
      <table className="w-full min-w-[760px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-ink-faint">
            <th className="px-4 py-2 font-medium">Date</th>
            <th className="px-4 py-2 font-medium">Insider</th>
            <th className="px-4 py-2 font-medium">Type</th>
            <th className="px-4 py-2 text-right font-medium">Shares</th>
            <th className="px-4 py-2 text-right font-medium">Price</th>
            <th className="px-4 py-2 text-right font-medium">Value</th>
            <th className="px-4 py-2 font-medium">10b5-1 plan</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const k = kind(row);
            return (
              <tr key={`${row.transaction_date}-${index}`} className="border-b border-line/60 last:border-0">
                <td className="px-4 py-1.5 whitespace-nowrap text-ink-muted">
                  {formatDate(row.transaction_date)}
                </td>
                <td className="px-4 py-1.5">
                  <span className="text-ink">{row.owner_name}</span>
                  <span className="block text-xs text-ink-faint">{row.owner_role}</span>
                </td>
                <td className="px-4 py-1.5">
                  <Badge tone={k.tone}>{k.text}</Badge>
                </td>
                <td className="px-4 py-1.5 text-right font-mono text-ink">{formatCompact(row.shares)}</td>
                <td className="px-4 py-1.5 text-right font-mono text-ink">{formatNumber(row.price)}</td>
                <td className="px-4 py-1.5 text-right font-mono text-ink">
                  {row.value === null ? "—" : `$${formatCompact(row.value)}`}
                </td>
                <td className="px-4 py-1.5 text-ink-muted">
                  {row.code === "S" || row.code === "P"
                    ? row.under_10b5_1 === null
                      ? "Not stated"
                      : row.under_10b5_1
                        ? "Yes"
                        : "No"
                    : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
