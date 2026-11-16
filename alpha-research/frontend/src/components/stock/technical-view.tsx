"use client";

import { CandlestickChart } from "lucide-react";

import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { formatDate, formatNumber, indicatorLabel } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";

import { TickerForm, useTickerParam } from "./ticker-form";

export function TechnicalView() {
  const ticker = useTickerParam();
  const { state, reload } = useApi(ticker ? `technicals-${ticker}` : null, () =>
    api.technicals(ticker as string),
  );

  return (
    <div className="space-y-4">
      <TickerForm key={ticker ?? ""} current={ticker} />
      {ticker ? (
        <Panel title={`${ticker} indicators`} icon={CandlestickChart}>
          <DataView state={state} onRetry={reload} loadingLabel="Calculating indicators">
            {(snapshot, response) => (
              <>
                <p className="text-sm text-ink-muted">
                  Last close{" "}
                  <span className="font-mono text-ink">{formatNumber(snapshot.last_close)}</span> on{" "}
                  {formatDate(snapshot.as_of_date)} · {snapshot.bars_available} daily bars stored
                </p>
                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  {snapshot.indicators.map((indicator) => (
                    <div key={indicator.name} className="rounded-md border border-line p-3">
                      <p className="text-xs text-ink-muted">{indicatorLabel(indicator.name)}</p>
                      {indicator.value === null ? (
                        <p
                          className="mt-1 text-xs text-ink-faint"
                          title={`Needs ${indicator.required_bars} bars`}
                        >
                          Needs {indicator.required_bars} bars
                        </p>
                      ) : (
                        <p className="mt-1 font-mono text-base text-ink">
                          {formatNumber(indicator.value)}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
                <SourceNote source={response.source} asOf={response.as_of} />
              </>
            )}
          </DataView>
        </Panel>
      ) : (
        <EmptyState title="Choose a stock">
          Enter a ticker to calculate indicators from its stored price history.
        </EmptyState>
      )}
    </div>
  );
}
