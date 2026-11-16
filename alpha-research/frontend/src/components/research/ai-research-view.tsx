"use client";

import { Bot, Sparkles } from "lucide-react";
import { type FormEvent, useState } from "react";

import { RecentResearchPanel } from "@/components/dashboard/recent-research";
import { Panel } from "@/components/ui/panel";
import { ErrorState, UnavailableState } from "@/components/ui/states";
import { ApiError, api } from "@/lib/api/client";
import type { DataResponse, ResearchReport } from "@/lib/api/types";
import { isValidTicker, normalizeTicker } from "@/lib/ticker";

type Outcome =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "done"; response: DataResponse<ResearchReport> }
  | { kind: "error"; error: ApiError };

export function AiResearchView() {
  const [ticker, setTicker] = useState("");
  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });
  const [inputError, setInputError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const symbol = normalizeTicker(ticker);
    if (!isValidTicker(symbol)) {
      setInputError("Enter a valid ticker symbol, e.g. MSFT or BRK.B");
      return;
    }
    setInputError(null);
    setOutcome({ kind: "pending" });
    try {
      setOutcome({ kind: "done", response: await api.generateReport(symbol) });
    } catch (error) {
      setOutcome({
        kind: "error",
        error: error instanceof ApiError ? error : new ApiError(String(error), null),
      });
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Panel title="Generate a report" icon={Sparkles}>
          <form onSubmit={submit} className="flex flex-wrap gap-2">
            <label htmlFor="ai-ticker" className="sr-only">
              Ticker
            </label>
            <input
              id="ai-ticker"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="Ticker, e.g. MSFT"
              autoComplete="off"
              spellCheck={false}
              className="h-9 w-48 rounded-md border border-line bg-canvas px-3 font-mono text-sm uppercase text-ink placeholder:font-sans placeholder:normal-case placeholder:text-ink-faint focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <button
              type="submit"
              disabled={outcome.kind === "pending" || !ticker.trim()}
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-accent px-3 text-sm font-medium text-canvas hover:bg-accent/90 disabled:opacity-50"
            >
              <Bot className="size-3.5" aria-hidden />
              {outcome.kind === "pending" ? "Requesting…" : "Generate"}
            </button>
          </form>
          {inputError && <p className="mt-2 text-xs text-negative">{inputError}</p>}
          <div className="mt-4">
            {outcome.kind === "error" && <ErrorState error={outcome.error} />}
            {outcome.kind === "done" &&
              (outcome.response.status === "ok" && outcome.response.data ? (
                <article className="whitespace-pre-wrap text-sm text-ink">
                  {outcome.response.data.body_markdown}
                </article>
              ) : (
                <UnavailableState
                  reason={outcome.response.reason}
                  message={outcome.response.message}
                />
              ))}
          </div>
          <p className="mt-4 text-xs text-ink-faint">
            Reports will be written only from data the platform has retrieved and calculated, and
            will always be labelled as AI-generated.
          </p>
        </Panel>
      </div>
      <RecentResearchPanel limit={20} />
    </div>
  );
}
