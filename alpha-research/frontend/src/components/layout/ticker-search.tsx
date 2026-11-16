"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { isValidTicker, normalizeTicker } from "@/lib/ticker";

/** Jump to the Stock Analysis page for a ticker. */
export function TickerSearch() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    const ticker = normalizeTicker(value);
    if (!isValidTicker(ticker)) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    setValue("");
    router.push(`/analysis?ticker=${encodeURIComponent(ticker)}`);
  }

  return (
    <form onSubmit={submit} role="search" className="relative w-40 sm:w-64">
      <Search
        className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-faint"
        aria-hidden
      />
      <label htmlFor="global-ticker-search" className="sr-only">
        Analyze a ticker
      </label>
      <input
        id="global-ticker-search"
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          setInvalid(false);
        }}
        placeholder="Analyze ticker…"
        autoComplete="off"
        spellCheck={false}
        aria-invalid={invalid}
        className={`h-8 w-full rounded-md border bg-surface pl-8 pr-2 font-mono text-xs uppercase text-ink placeholder:font-sans placeholder:normal-case placeholder:text-ink-faint focus:outline-none focus:ring-1 ${
          invalid ? "border-negative focus:ring-negative" : "border-line focus:ring-accent"
        }`}
      />
    </form>
  );
}
