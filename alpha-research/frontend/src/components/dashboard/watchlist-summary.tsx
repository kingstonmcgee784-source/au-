"use client";

import { Star } from "lucide-react";
import Link from "next/link";

import { Panel } from "@/components/ui/panel";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { useApi } from "@/lib/hooks/use-api";

export function WatchlistSummaryPanel() {
  const { state, reload } = useApi("watchlists", api.watchlists);

  return (
    <Panel
      title="Watchlist"
      icon={Star}
      actions={
        <Link href="/watchlist" className="text-xs text-ink-muted hover:text-accent">
          Manage
        </Link>
      }
    >
      {state.kind === "loading" && <LoadingState label="Loading watchlists" />}
      {state.kind === "error" && <ErrorState error={state.error} onRetry={reload} />}
      {state.kind === "success" &&
        (state.data.length === 0 ? (
          <EmptyState title="No watchlists yet">
            <Link href="/watchlist" className="text-accent hover:underline">
              Create a watchlist
            </Link>{" "}
            to start tracking tickers.
          </EmptyState>
        ) : (
          <ul className="space-y-4">
            {state.data.map((watchlist) => (
              <li key={watchlist.id}>
                <p className="text-xs font-medium text-ink-muted">
                  {watchlist.name}{" "}
                  <span className="text-ink-faint">({watchlist.items.length})</span>
                </p>
                {watchlist.items.length === 0 ? (
                  <p className="mt-1 text-xs text-ink-faint">No tickers on this list.</p>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {watchlist.items.map((item) => (
                      <Link
                        key={item.id}
                        href={`/analysis?ticker=${item.ticker}`}
                        className="rounded border border-line px-2 py-0.5 font-mono text-xs text-ink hover:border-accent hover:text-accent"
                      >
                        {item.ticker}
                      </Link>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        ))}
      <p className="mt-4 text-[11px] text-ink-faint">
        Prices are not shown until a market data provider is connected.
      </p>
    </Panel>
  );
}
