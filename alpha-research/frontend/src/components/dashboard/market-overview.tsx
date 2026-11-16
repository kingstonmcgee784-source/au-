"use client";

import { Globe2 } from "lucide-react";

import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import { api } from "@/lib/api/client";
import { changeTone, formatNumber, formatPercent } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";

export function MarketOverviewPanel() {
  const { state, reload } = useApi("market-overview", api.marketOverview);

  return (
    <Panel title="Market overview" icon={Globe2}>
      <DataView state={state} onRetry={reload} loadingLabel="Loading market data">
        {(overview, response) => (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {overview.indices.map((index) => (
                <div key={index.symbol} className="rounded-md border border-line p-3">
                  <p className="text-xs text-ink-muted">{index.name}</p>
                  <p className="mt-1 font-mono text-lg text-ink">{formatNumber(index.level)}</p>
                  <p className={`font-mono text-xs ${changeTone(index.change_percent)}`}>
                    {formatPercent(index.change_percent)}
                  </p>
                </div>
              ))}
            </div>
            <SourceNote source={response.source} asOf={response.as_of} />
          </>
        )}
      </DataView>
    </Panel>
  );
}
