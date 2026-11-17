"use client";

import { Loader2, Radar, Square } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { ErrorState } from "@/components/ui/states";
import { ApiError, api } from "@/lib/api/client";
import type { Scan } from "@/lib/api/types";
import { formatNumber } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { isValidTicker, normalizeTicker } from "@/lib/ticker";

const POLL_MS = 3000;
const ACTIVE = new Set(["queued", "running", "waiting"]);

const ITEM_TONE: Record<string, "positive" | "negative" | "warning" | "neutral"> = {
  scored: "positive",
  not_scored: "warning",
  failed: "negative",
  pending: "neutral",
};

function parseTickers(text: string): { valid: string[]; invalid: string[] } {
  const parts = text.split(/[\s,;]+/).map(normalizeTicker).filter(Boolean);
  return {
    valid: [...new Set(parts.filter(isValidTicker))],
    invalid: parts.filter((p) => !isValidTicker(p)),
  };
}

/** Start a batch scan and follow its progress. Calls `onFinished` when a scan completes. */
export function ScanPanel({ onFinished }: { onFinished: () => void }) {
  const scans = useApi("scans", () => api.scans(1));
  const watchlists = useApi("scan-watchlists", api.watchlists);
  const [text, setText] = useState("");
  const [watchlistId, setWatchlistId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const latest = scans.state.kind === "success" ? scans.state.data[0] : undefined;
  const active = latest !== undefined && ACTIVE.has(latest.status);

  // Poll while a scan is running; refresh results when it finishes.
  const wasActive = useRef(false);
  const reloadScans = scans.reload;
  useEffect(() => {
    if (wasActive.current && !active) onFinished();
    wasActive.current = active;
    if (!active) return;
    const id = window.setInterval(reloadScans, POLL_MS);
    return () => window.clearInterval(id);
  }, [active, reloadScans, onFinished]);

  async function start(event: FormEvent) {
    event.preventDefault();
    const { valid, invalid } = parseTickers(text);
    if (invalid.length > 0) {
      setError(`Not valid ticker symbols: ${invalid.join(", ")}`);
      return;
    }
    if (valid.length === 0 && !watchlistId) {
      setError("Enter some tickers or choose a watchlist.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.startScan({ tickers: valid, watchlistId: watchlistId ? Number(watchlistId) : undefined });
      setText("");
      scans.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the scan.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel(scan: Scan) {
    try {
      await api.cancelScan(scan.id);
    } finally {
      scans.reload();
    }
  }

  return (
    <Panel title="Scan stocks" icon={Radar}>
      <form onSubmit={start} className="grid gap-3 lg:grid-cols-[1fr_auto_auto] lg:items-end">
        <div className="space-y-1">
          <label htmlFor="scan-tickers" className="text-xs text-ink-muted">
            Tickers (separated by spaces or commas)
          </label>
          <textarea
            id="scan-tickers"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={2}
            placeholder="PLTR LIVN MRCY FLYW HCSG"
            spellCheck={false}
            className="w-full rounded-md border border-line bg-canvas px-3 py-2 font-mono text-sm uppercase text-ink placeholder:font-sans placeholder:normal-case placeholder:text-ink-faint focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="scan-watchlist" className="text-xs text-ink-muted">
            and/or a watchlist
          </label>
          <select
            id="scan-watchlist"
            value={watchlistId}
            onChange={(e) => setWatchlistId(e.target.value)}
            className="h-9 w-full rounded-md border border-line bg-canvas px-2 text-sm text-ink focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">None</option>
            {watchlists.state.kind === "success" &&
              watchlists.state.data.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.items.length})
                </option>
              ))}
          </select>
        </div>
        <button
          type="submit"
          disabled={busy || active}
          className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md bg-accent px-4 text-sm font-medium text-canvas hover:bg-accent/90 disabled:opacity-50"
        >
          {busy && <Loader2 className="size-3.5 animate-spin" aria-hidden />}
          Start scan
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-negative">{error}</p>}
      <p className="mt-2 text-[11px] text-ink-faint">
        Each new stock uses about 3 Tiingo requests, and the free plan allows 50 an hour, so a long
        list pauses and resumes on its own. You can leave this page; the scan runs in the backend.
      </p>

      {scans.state.kind === "error" && <ErrorState error={scans.state.error} onRetry={scans.reload} />}
      {latest && <ScanProgress scan={latest} onCancel={() => void cancel(latest)} />}
    </Panel>
  );
}

function ScanProgress({ scan, onCancel }: { scan: Scan; onCancel: () => void }) {
  const active = ACTIVE.has(scan.status);
  const share = scan.total ? scan.completed / scan.total : 0;
  return (
    <div className="mt-4 rounded-md border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <div className="flex items-center gap-2">
          {active && <Loader2 className="size-3.5 animate-spin text-accent" aria-hidden />}
          <span className="text-ink">{scan.name}</span>
          <Badge tone={scan.status === "waiting" ? "warning" : active ? "info" : "neutral"}>
            {scan.status}
          </Badge>
        </div>
        <div className="flex items-center gap-3 text-xs text-ink-muted">
          {scan.completed} / {scan.total}
          {active && (
            <button
              type="button"
              onClick={onCancel}
              className="inline-flex items-center gap-1 text-ink-faint hover:text-negative"
            >
              <Square className="size-3" aria-hidden /> Cancel
            </button>
          )}
        </div>
      </div>
      <div className="mt-2 h-1 rounded bg-surface-raised">
        <div className="h-1 rounded bg-accent transition-all" style={{ width: `${share * 100}%` }} />
      </div>
      {scan.message && (
        <p className="mt-2 text-xs text-ink-muted">
          {scan.message}
          {scan.status === "waiting" && scan.resume_at && (
            <> Resumes about {new Date(scan.resume_at).toLocaleTimeString()}.</>
          )}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {scan.items.map((item) => (
          <span key={item.ticker} title={item.message ?? undefined}>
            <Badge tone={ITEM_TONE[item.status] ?? "neutral"}>
              {item.ticker}
              {item.score !== null && ` ${formatNumber(item.score, 0)}`}
            </Badge>
          </span>
        ))}
      </div>
    </div>
  );
}
