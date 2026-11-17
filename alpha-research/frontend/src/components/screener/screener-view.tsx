"use client";

import { useCallback } from "react";

import { ErrorState, LoadingState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { useApi } from "@/lib/hooks/use-api";

import { ResultsTable } from "./results-table";
import { ScanPanel } from "./scan-panel";

export function ScreenerView() {
  const { state, reload } = useApi("screener-rows", api.screener);
  const onFinished = useCallback(() => reload(), [reload]);
  return (
    <div className="space-y-4">
      <ScanPanel onFinished={onFinished} />
      {state.kind === "loading" && <LoadingState label="Loading scored stocks" />}
      {state.kind === "error" && <ErrorState error={state.error} onRetry={reload} />}
      {state.kind === "success" && <ResultsTable rows={state.data} />}
    </div>
  );
}
