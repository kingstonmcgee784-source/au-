"use client";

import { DownloadCloud, Loader2 } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/lib/api/client";
import type { DataResponse } from "@/lib/api/types";

type Result = { kind: "ok" | "warning" | "error"; text: string } | null;

interface SyncButtonProps<T> {
  label: string;
  busyLabel: string;
  /** Runs the sync request. */
  run: () => Promise<DataResponse<T>>;
  /** Turns a successful result into a confirmation message. */
  describe: (data: T, response: DataResponse<T>) => string;
  /** Called after a successful sync so the page can reload its data. */
  onSynced: () => void;
  /** True when the request worked but only partly (shown as a warning). */
  isPartial?: (data: T) => boolean;
}

/** A button that loads data from a provider into the database. */
export function SyncButton<T>({
  label,
  busyLabel,
  run,
  describe,
  onSynced,
  isPartial,
}: SyncButtonProps<T>) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result>(null);

  async function sync() {
    setBusy(true);
    setResult(null);
    try {
      const response = await run();
      if (response.status === "ok" && response.data) {
        // A message on a successful response means it only partly worked.
        setResult({
          kind: isPartial?.(response.data) || response.message ? "warning" : "ok",
          text: describe(response.data, response),
        });
        onSynced();
      } else {
        setResult({ kind: "error", text: response.message ?? "The data could not be loaded." });
      }
    } catch (error) {
      setResult({
        kind: "error",
        text: error instanceof ApiError ? error.message : "The data could not be loaded.",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex max-w-md flex-col gap-1.5">
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
        {busy ? busyLabel : label}
      </button>
      {result && (
        <p
          className={`text-xs ${
            result.kind === "ok"
              ? "text-positive"
              : result.kind === "warning"
                ? "text-warning"
                : "text-negative"
          }`}
          role="status"
        >
          {result.text}
        </p>
      )}
    </div>
  );
}
