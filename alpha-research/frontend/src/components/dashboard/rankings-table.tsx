"use client";

import { Trophy } from "lucide-react";
import Link from "next/link";

import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import { api } from "@/lib/api/client";
import { formatDate, formatNumber } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";

export function RankingsPanel({ limit = 10, showLink = true }: { limit?: number; showLink?: boolean }) {
  const { state, reload } = useApi(`rankings-${limit}`, () => api.rankings(limit));

  return (
    <Panel
      title="Stock rankings"
      icon={Trophy}
      actions={
        showLink && (
          <Link href="/rankings" className="text-xs text-ink-muted hover:text-accent">
            View all
          </Link>
        )
      }
    >
      <DataView state={state} onRetry={reload} loadingLabel="Loading rankings">
        {(entries, response) => (
          <>
            <div className="-mx-4 overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-ink-faint">
                    <th className="px-4 py-2 font-medium">#</th>
                    <th className="px-4 py-2 font-medium">Ticker</th>
                    <th className="px-4 py-2 font-medium">Company</th>
                    <th className="px-4 py-2 text-right font-medium">Score</th>
                    <th className="px-4 py-2 text-right font-medium" title="Share of the methodology that had data">
                      Coverage
                    </th>
                    <th className="px-4 py-2 font-medium">Risk</th>
                    <th className="px-4 py-2 font-medium">As of</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.ticker} className="border-b border-line/60 last:border-0">
                      <td className="px-4 py-2 font-mono text-ink-faint">{entry.rank}</td>
                      <td className="px-4 py-2">
                        <Link
                          href={`/analysis?ticker=${entry.ticker}`}
                          className="font-mono font-semibold text-accent hover:underline"
                        >
                          {entry.ticker}
                        </Link>
                      </td>
                      <td className="max-w-48 truncate px-4 py-2 text-ink-muted">{entry.name}</td>
                      <td className="px-4 py-2 text-right font-mono" title={entry.interpretation}>
                        {formatNumber(entry.total_score, 0)}
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-ink-faint">
                        {Math.round(entry.coverage * 100)}%
                      </td>
                      <td className="px-4 py-2 text-ink-muted">{entry.risk_class ?? "—"}</td>
                      <td className="px-4 py-2 text-ink-faint">{formatDate(entry.as_of)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <SourceNote source={response.source} asOf={response.as_of} />
          </>
        )}
      </DataView>
    </Panel>
  );
}
