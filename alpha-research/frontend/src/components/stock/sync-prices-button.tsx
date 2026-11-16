"use client";

import { DownloadCloud, Loader2 } from "lucide-react";
import { useState } from "react";

import { ApiError, api } from "@/lib/api/client";
import { formatDate } from "@/lib/format";

type Result = { kind: "ok"; text: string } | { kind: "error"; text: string } | null;

/**
 * Fetch daily prices for a ticker from the market data provider and store
 * them. Calls `onSynced` afterwards so the page can reload calculations.
 */
export function SyncPricesButton({ ticker, onSynced }: { ticker: string; onSynced: () => void }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result>(null);

  async function sync() {
    setBusy(true);
    setResult(null);
    try {
      const response = await api.syncPrices(ticker);
      if (response.status === "ok" && response.data) {
        const d = response.data;
        setResult({
          kind: "ok",
          text:
            `${d.bars_added} new daily bars stored (${d.bars_stored} total, ` +
            `${formatDate(d.first_date)} to ${formatDate(d.last_date)}).`,
        });
        onSynced();
      } else {
        setResult({ kind: "error", text: response.message ?? "Prices could not be loaded." });
      }
    } catch (error) {
      setResult({
        kind: "error",
        text: error instanceof ApiError ? error.message : "Prices could not be loaded.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <button
        type="button"
        onClick={() => void sync()}
        disabled={busy}
        className="inline-flex h-9 items-center gap-1.5 self-start rounded-md border border-line-strong px-3 text-sm text-ink hover:border-accent hover:text-accent disabled:opacity-50"
      >
        {busy ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <DownloadCloud className="size-3.5" aria-hidden />
        )}
        {busy ? "Loading prices…" : "Load price history"}
      </button>
      {result && (
        <p
          className={`text-xs ${result.kind === "ok" ? "text-positive" : "text-negative"}`}
          role="status"
        >
          {result.text}
        </p>
      )}
    </div>
  );
}
