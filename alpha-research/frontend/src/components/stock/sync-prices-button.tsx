"use client";

import { api } from "@/lib/api/client";
import { formatDate } from "@/lib/format";

import { SyncButton } from "./sync-button";

/** Load daily prices for a ticker from the market data provider. */
export function SyncPricesButton({ ticker, onSynced }: { ticker: string; onSynced: () => void }) {
  return (
    <SyncButton
      label="Load price history"
      busyLabel="Loading prices…"
      run={() => api.syncPrices(ticker)}
      describe={(d) =>
        (d.bars_added > 0
          ? `${d.bars_added} new daily bars stored`
          : "Prices are already up to date (refreshed at most every 6 hours)") +
        ` · ${d.bars_stored} bars from ${formatDate(d.first_date)} to ${formatDate(d.last_date)}.`
      }
      onSynced={onSynced}
    />
  );
}

/** Load reported financial statements for a ticker from SEC EDGAR. */
export function SyncFinancialsButton({
  ticker,
  onSynced,
}: {
  ticker: string;
  onSynced: () => void;
}) {
  return (
    <SyncButton
      label="Load financials"
      busyLabel="Loading from SEC…"
      run={() => api.syncFinancials(ticker)}
      describe={(d) =>
        `${d.company_name}: ${d.quarterly_periods} quarters and ${d.annual_periods} years ` +
        `loaded from SEC filings (latest period ${formatDate(d.latest_period_end)}).`
      }
      onSynced={onSynced}
    />
  );
}
