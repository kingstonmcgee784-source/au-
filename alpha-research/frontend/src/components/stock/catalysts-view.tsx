"use client";

import { CalendarClock, ExternalLink, Newspaper } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { DataView, SourceNote } from "@/components/ui/data-view";
import { Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import type { CatalystEvent, CatalystFeed } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";

import { SyncButton } from "./sync-button";
import { TickerForm, useTickerParam } from "./ticker-form";

type Tone = "positive" | "negative" | "warning" | "info" | "neutral";

const KIND: Record<string, { label: string; tone: Tone }> = {
  earnings: { label: "Earnings", tone: "info" },
  agreement: { label: "Agreement", tone: "positive" },
  acquisition: { label: "M&A", tone: "positive" },
  red_flag: { label: "Red flag", tone: "negative" },
  review: { label: "Read filing", tone: "warning" },
  dilution: { label: "Share sale", tone: "warning" },
  financing: { label: "Financing", tone: "neutral" },
  management: { label: "Management", tone: "neutral" },
  governance: { label: "Governance", tone: "neutral" },
  disclosure: { label: "Disclosure", tone: "neutral" },
  other: { label: "Other", tone: "neutral" },
};

export function CatalystsView() {
  const ticker = useTickerParam();
  const { state, reload } = useApi(ticker ? `catalysts-${ticker}` : null, () =>
    api.catalysts(ticker as string),
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start gap-4">
        <TickerForm key={ticker ?? ""} current={ticker} />
        {ticker && (
          <SyncButton
            key={`events-${ticker}`}
            label="Load SEC events"
            busyLabel="Reading the SEC filing index…"
            run={() => api.syncEvents(ticker)}
            describe={(d) => `${d.events_added} new 8-K events (${d.events_stored} stored).`}
            onSynced={reload}
          />
        )}
      </div>
      {ticker ? (
        <DataView state={state} onRetry={reload} loadingLabel="Loading events">
          {(feed, response) => (
            <div className="grid gap-4 lg:grid-cols-3">
              <EarningsCard feed={feed} />
              <Panel title={`${ticker} events (8-K filings)`} icon={Newspaper} className="lg:col-span-2">
                {feed.events.length === 0 ? (
                  <p className="text-sm text-ink-muted">No 8-K filings in the last 13 months.</p>
                ) : (
                  <ul className="divide-y divide-line/60">
                    {feed.events.map((event) => (
                      <EventRow key={event.url} event={event} />
                    ))}
                  </ul>
                )}
                <p className="mt-3 text-[11px] text-ink-faint">
                  Classified from the item numbers each 8-K reports. That shows what kind of event
                  it was, not whether it was good or bad: open the filing to judge. Only reliable
                  red flags (bankruptcy, impairments, restated financials, auditor changes) count
                  against the score.
                </p>
                <SourceNote source={response.source} asOf={response.as_of} />
              </Panel>
            </div>
          )}
        </DataView>
      ) : (
        <EmptyState title="Choose a stock">
          Enter a ticker to see its company events and estimated next earnings date.
        </EmptyState>
      )}
    </div>
  );
}

function EarningsCard({ feed }: { feed: CatalystFeed }) {
  const estimate = feed.next_earnings_estimate;
  const days = feed.days_to_next_earnings;
  return (
    <Panel title="Next earnings" icon={CalendarClock}>
      {estimate ? (
        <>
          <p className="font-mono text-2xl text-ink">{formatDate(estimate)}</p>
          <p className="text-sm text-ink-muted">
            {days !== null && days >= 0 ? `in about ${days} days` : "around now"}
          </p>
          <p className="mt-3">
            <Badge tone="warning">Estimate</Badge>
          </p>
          <p className="mt-2 text-xs text-ink-faint">
            Estimated from when the company released results a year earlier (8-K item 2.02). The
            company has not necessarily announced this date; check its investor relations site.
          </p>
        </>
      ) : (
        <p className="text-sm text-ink-muted">
          Not enough earnings history in the loaded filings to estimate a date.
        </p>
      )}
    </Panel>
  );
}

function EventRow({ event }: { event: CatalystEvent }) {
  const kind = KIND[event.kind] ?? KIND.other;
  const extra = event.items.filter((i) => i.label !== event.headline);
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={kind.tone}>{kind.label}</Badge>
          <span className="text-sm text-ink">{event.headline}</span>
        </div>
        {extra.length > 0 && (
          <p className="text-xs text-ink-faint">Also: {extra.map((i) => i.label).join(" · ")}</p>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs text-ink-muted">
        <span className="whitespace-nowrap">
          {formatDate(event.filed_on)} · {event.form}
        </span>
        <a
          href={event.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-accent hover:underline"
        >
          Filing <ExternalLink className="size-3" aria-hidden />
        </a>
      </div>
    </li>
  );
}
