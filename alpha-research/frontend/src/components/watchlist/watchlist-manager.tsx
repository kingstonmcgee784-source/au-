"use client";

import { Plus, Star, Trash2, X } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useState } from "react";

import { Panel } from "@/components/ui/panel";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { ApiError, api } from "@/lib/api/client";
import type { Watchlist } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { isValidTicker, normalizeTicker } from "@/lib/ticker";

const inputClass =
  "h-9 rounded-md border border-line bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:ring-1 focus:ring-accent";
const primaryButton =
  "inline-flex h-9 items-center gap-1.5 rounded-md bg-accent px-3 text-sm font-medium text-canvas hover:bg-accent/90 disabled:opacity-50";

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong.";
}

export function WatchlistManager() {
  const { state, reload } = useApi("watchlists-manager", api.watchlists);

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="lg:col-span-1">
        <CreateWatchlistForm onCreated={reload} />
      </div>
      <div className="space-y-4 lg:col-span-2">
        {state.kind === "loading" && <LoadingState label="Loading watchlists" />}
        {state.kind === "error" && <ErrorState error={state.error} onRetry={reload} />}
        {state.kind === "success" &&
          (state.data.length === 0 ? (
            <Panel title="Your watchlists" icon={Star}>
              <EmptyState title="No watchlists yet">
                Create one to start tracking tickers.
              </EmptyState>
            </Panel>
          ) : (
            state.data.map((watchlist) => (
              <WatchlistCard key={watchlist.id} watchlist={watchlist} onChanged={reload} />
            ))
          ))}
      </div>
    </div>
  );
}

function CreateWatchlistForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.createWatchlist(name.trim(), description.trim());
      setName("");
      setDescription("");
      onCreated();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="New watchlist" icon={Plus}>
      <form onSubmit={submit} className="space-y-3">
        <div className="space-y-1">
          <label htmlFor="watchlist-name" className="text-xs text-ink-muted">
            Name
          </label>
          <input
            id="watchlist-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={128}
            required
            className={`${inputClass} w-full`}
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="watchlist-description" className="text-xs text-ink-muted">
            Description (optional)
          </label>
          <textarea
            id="watchlist-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={2000}
            rows={3}
            className={`${inputClass} h-auto w-full py-2`}
          />
        </div>
        {error && <p className="text-xs text-negative">{error}</p>}
        <button type="submit" disabled={busy || !name.trim()} className={primaryButton}>
          <Plus className="size-3.5" aria-hidden />
          Create watchlist
        </button>
      </form>
    </Panel>
  );
}

function WatchlistCard({ watchlist, onChanged }: { watchlist: Watchlist; onChanged: () => void }) {
  const [ticker, setTicker] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  function addTicker(event: FormEvent) {
    event.preventDefault();
    const symbol = normalizeTicker(ticker);
    if (!isValidTicker(symbol)) {
      setError("Enter a valid ticker symbol, e.g. MSFT or BRK.B");
      return;
    }
    void run(async () => {
      await api.addWatchlistItem(watchlist.id, symbol);
      setTicker("");
    });
  }

  function deleteList() {
    if (window.confirm(`Delete the watchlist "${watchlist.name}"?`)) {
      void run(() => api.deleteWatchlist(watchlist.id));
    }
  }

  return (
    <Panel
      title={watchlist.name}
      icon={Star}
      actions={
        <button
          type="button"
          onClick={deleteList}
          disabled={busy}
          className="inline-flex items-center gap-1 text-xs text-ink-faint hover:text-negative"
        >
          <Trash2 className="size-3.5" aria-hidden />
          Delete
        </button>
      }
      footer={`Created ${formatDate(watchlist.created_at)}`}
    >
      {watchlist.description && <p className="mb-3 text-sm text-ink-muted">{watchlist.description}</p>}

      <form onSubmit={addTicker} className="flex gap-2">
        <label htmlFor={`add-ticker-${watchlist.id}`} className="sr-only">
          Add ticker to {watchlist.name}
        </label>
        <input
          id={`add-ticker-${watchlist.id}`}
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Add ticker"
          autoComplete="off"
          spellCheck={false}
          className={`${inputClass} w-40 font-mono uppercase placeholder:font-sans placeholder:normal-case`}
        />
        <button type="submit" disabled={busy || !ticker.trim()} className={primaryButton}>
          Add
        </button>
      </form>
      {error && <p className="mt-2 text-xs text-negative">{error}</p>}

      {watchlist.items.length === 0 ? (
        <p className="mt-4 text-sm text-ink-faint">No tickers yet.</p>
      ) : (
        <ul className="mt-4 divide-y divide-line/60">
          {watchlist.items.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-3 py-2">
              <div>
                <Link
                  href={`/analysis?ticker=${item.ticker}`}
                  className="font-mono text-sm font-semibold text-accent hover:underline"
                >
                  {item.ticker}
                </Link>
                <p className="text-xs text-ink-faint">Added {formatDate(item.added_at)}</p>
              </div>
              <button
                type="button"
                onClick={() => void run(() => api.removeWatchlistItem(watchlist.id, item.ticker))}
                disabled={busy}
                className="rounded p-1 text-ink-faint hover:text-negative"
                aria-label={`Remove ${item.ticker}`}
              >
                <X className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
