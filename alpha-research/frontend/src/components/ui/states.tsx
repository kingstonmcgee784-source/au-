import { AlertTriangle, CircleSlash, Inbox, Loader2, RotateCw } from "lucide-react";
import type { ReactNode } from "react";

import type { ApiError } from "@/lib/api/client";
import type { UnavailableReason } from "@/lib/api/types";

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-6 text-sm text-ink-muted" role="status">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label}…
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div
      className="flex flex-col items-start gap-3 rounded-md border border-negative/30 bg-negative/5 p-3 text-sm"
      role="alert"
    >
      <div className="flex items-start gap-2 text-negative">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>{error.message}</span>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded border border-line-strong px-2 py-1 text-xs text-ink-muted hover:border-ink-faint hover:text-ink"
        >
          <RotateCw className="size-3" aria-hidden />
          Retry
        </button>
      )}
    </div>
  );
}

const REASON_TITLE: Record<UnavailableReason, string> = {
  provider_not_configured: "Data provider not connected",
  ai_not_configured: "AI research not connected",
  no_stored_data: "No data stored yet",
  insufficient_history: "Not enough price history",
  unknown_ticker: "Ticker not recognized",
  provider_error: "Data provider error",
  rate_limited: "Request limit reached",
};

/** Shown when the backend answers `status: "unavailable"`. Never shows numbers. */
export function UnavailableState({
  reason,
  message,
}: {
  reason: UnavailableReason | null;
  message: string | null;
}) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-dashed border-line-strong p-3 text-sm">
      <CircleSlash className="mt-0.5 size-4 shrink-0 text-ink-faint" aria-hidden />
      <div className="space-y-0.5">
        <p className="font-medium text-ink">{reason ? REASON_TITLE[reason] : "Data unavailable"}</p>
        {message && <p className="text-ink-muted">{message}</p>}
      </div>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 py-6 text-center text-sm">
      <Inbox className="size-5 text-ink-faint" aria-hidden />
      <p className="font-medium text-ink">{title}</p>
      {children && <div className="max-w-sm text-ink-muted">{children}</div>}
    </div>
  );
}
