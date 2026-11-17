"use client";

import { Building2, LineChart } from "lucide-react";
import Link from "next/link";

import { DataView, SourceNote } from "@/components/ui/data-view";
import { EmptyState } from "@/components/ui/states";
import { Panel } from "@/components/ui/panel";
import { api } from "@/lib/api/client";
import {
  changeTone,
  formatCompact,
  formatNumber,
  formatPercent,
} from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";

import { IndustryPanel } from "./industry-panel";
import { ScoreBreakdownPanel } from "./score-breakdown";
import { InsiderPanel } from "./insider-panel";
import { CalculateScoreButton, MetricsPanel, ScorePanel, TrackCallButton } from "./score-panels";
import { TickerForm, useTickerParam } from "./ticker-form";

export function StockAnalysisView() {
  const ticker = useTickerParam();

  return (
    <div className="space-y-4">
      <TickerForm key={ticker ?? ""} current={ticker} />
      {ticker ? (
        <TickerResearch key={`research-${ticker}`} ticker={ticker} />
      ) : (
        <EmptyState title="Choose a stock">Enter a ticker above to load its research data.</EmptyState>
      )}
    </div>
  );
}

function TickerResearch({ ticker }: { ticker: string }) {
  const score = useApi(`score-${ticker}`, () => api.score(ticker));
  const metrics = useApi(`metrics-${ticker}`, () => api.metrics(ticker));
  const insiders = useApi(`insiders-${ticker}`, () => api.insiders(ticker));
  const industry = useApi(`industry-${ticker}`, () => api.industry(ticker));
  const reloadAll = () => {
    score.reload();
    metrics.reload();
    insiders.reload();
    industry.reload();
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start gap-4">
        <CalculateScoreButton ticker={ticker} onScored={reloadAll} />
        <TrackCallButton ticker={ticker} onTracked={() => undefined} />
        <Link
          href={`/news?ticker=${ticker}`}
          className="inline-flex h-9 items-center rounded-md px-3 text-sm text-ink-muted hover:text-accent"
        >
          Events and earnings date →
        </Link>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <ProfilePanel ticker={ticker} />
        <QuotePanel ticker={ticker} />
        <ScorePanel state={score.state} onRetry={score.reload} />
      </div>
      <ScoreBreakdownPanel ticker={ticker} state={score.state} onRetry={score.reload} />
      <MetricsPanel state={metrics.state} onRetry={metrics.reload} />
      <IndustryPanel state={industry.state} onRetry={industry.reload} />
      <InsiderPanel
        ticker={ticker}
        state={insiders.state}
        onRetry={insiders.reload}
        onSynced={insiders.reload}
      />
    </div>
  );
}

function ProfilePanel({ ticker }: { ticker: string }) {
  const { state, reload } = useApi(`profile-${ticker}`, () => api.stockProfile(ticker));
  return (
    <Panel title={`${ticker} profile`} icon={Building2}>
      <DataView state={state} onRetry={reload}>
        {(stock, response) => (
          <>
            <p className="text-base font-medium text-ink">{stock.name}</p>
            <dl className="mt-3 space-y-1.5 text-sm">
              {(
                [
                  ["Exchange", stock.exchange],
                  ["Sector", stock.sector],
                  ["Industry", stock.industry],
                  ["Currency", stock.currency],
                ] as const
              ).map(([label, value]) => (
                <div key={label} className="flex justify-between gap-3">
                  <dt className="text-ink-muted">{label}</dt>
                  <dd className="text-right text-ink">{value ?? "—"}</dd>
                </div>
              ))}
            </dl>
            <SourceNote source={response.source} asOf={response.as_of} />
          </>
        )}
      </DataView>
    </Panel>
  );
}

function QuotePanel({ ticker }: { ticker: string }) {
  const { state, reload } = useApi(`quote-${ticker}`, () => api.quote(ticker));
  return (
    <Panel title="Quote" icon={LineChart}>
      <DataView state={state} onRetry={reload}>
        {(quote, response) => (
          <>
            <p className="font-mono text-2xl text-ink">{formatNumber(quote.price)}</p>
            <p className={`font-mono text-sm ${changeTone(quote.change)}`}>
              {formatNumber(quote.change)} ({formatPercent(quote.change_percent)})
            </p>
            <p className="mt-2 text-xs text-ink-muted">
              Previous close {formatNumber(quote.previous_close)} · Volume{" "}
              {formatCompact(quote.volume)}
            </p>
            <p className="mt-1 text-[11px] text-ink-faint">Feed: {quote.feed}</p>
            <SourceNote source={response.source} asOf={response.as_of} />
          </>
        )}
      </DataView>
    </Panel>
  );
}
