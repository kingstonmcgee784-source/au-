"use client";

import { ArrowRight } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useState } from "react";

import { isValidTicker, normalizeTicker } from "@/lib/ticker";

/** The active ticker from `?ticker=`, or null if missing or malformed. */
export function useTickerParam(): string | null {
  const raw = useSearchParams().get("ticker");
  if (!raw) return null;
  const ticker = normalizeTicker(raw);
  return isValidTicker(ticker) ? ticker : null;
}

/** Ticker input that stores the choice in the URL, so pages are linkable. */
export function TickerForm({ current }: { current: string | null }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [value, setValue] = useState(current ?? "");
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    const ticker = normalizeTicker(value);
    if (!isValidTicker(ticker)) {
      setError("Enter a valid ticker symbol, e.g. MSFT or BRK.B");
      return;
    }
    setError(null);
    const params = new URLSearchParams(searchParams);
    params.set("ticker", ticker);
    router.replace(`${pathname}?${params}`);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-1.5">
      <div className="flex gap-2">
        <label htmlFor="ticker-input" className="sr-only">
          Ticker symbol
        </label>
        <input
          id="ticker-input"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Ticker, e.g. MSFT"
          autoComplete="off"
          spellCheck={false}
          aria-invalid={error !== null}
          aria-describedby={error ? "ticker-error" : undefined}
          className="h-9 w-48 rounded-md border border-line bg-surface px-3 font-mono text-sm uppercase text-ink placeholder:font-sans placeholder:normal-case placeholder:text-ink-faint focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <button
          type="submit"
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-accent px-3 text-sm font-medium text-canvas hover:bg-accent/90"
        >
          Load
          <ArrowRight className="size-3.5" aria-hidden />
        </button>
      </div>
      {error && (
        <p id="ticker-error" className="text-xs text-negative">
          {error}
        </p>
      )}
    </form>
  );
}
