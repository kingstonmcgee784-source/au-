"use client";

import type { ReactNode } from "react";

import type { DataResponse } from "@/lib/api/types";
import type { ApiState } from "@/lib/hooks/use-api";

import { ErrorState, LoadingState, UnavailableState } from "./states";

interface DataViewProps<T> {
  state: ApiState<DataResponse<T>>;
  onRetry?: () => void;
  loadingLabel?: string;
  idle?: ReactNode;
  children: (data: T, response: DataResponse<T>) => ReactNode;
}

/**
 * Renders a `DataResponse` request in every state: idle, loading, network or
 * HTTP error, data unavailable, and success. Children only ever receive real
 * data from the backend.
 */
export function DataView<T>({ state, onRetry, loadingLabel, idle, children }: DataViewProps<T>) {
  switch (state.kind) {
    case "idle":
      return <>{idle ?? null}</>;
    case "loading":
      return <LoadingState label={loadingLabel} />;
    case "error":
      return <ErrorState error={state.error} onRetry={onRetry} />;
    case "success": {
      const response = state.data;
      if (response.status === "unavailable" || response.data === null) {
        return <UnavailableState reason={response.reason} message={response.message} />;
      }
      return <>{children(response.data, response)}</>;
    }
  }
}

export function SourceNote({ source, asOf }: { source: string | null; asOf: string | null }) {
  if (!source) return null;
  return (
    <p className="mt-3 text-[11px] text-ink-faint">
      Source: <span className="font-mono">{source}</span>
      {asOf && <> · as of {new Date(asOf).toLocaleString()}</>}
    </p>
  );
}
