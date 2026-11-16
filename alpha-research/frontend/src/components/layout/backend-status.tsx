"use client";

import { useEffect } from "react";

import { api } from "@/lib/api/client";
import { useApi } from "@/lib/hooks/use-api";

const POLL_MS = 30_000;

/** Small indicator showing whether the frontend can reach the backend. */
export function BackendStatus() {
  const { state, reload } = useApi("health", api.health);

  useEffect(() => {
    const id = window.setInterval(reload, POLL_MS);
    return () => window.clearInterval(id);
  }, [reload]);

  let dot = "bg-ink-faint";
  let label = "Checking API";
  if (state.kind === "error") {
    dot = "bg-negative";
    label = "API offline";
  } else if (state.kind === "success") {
    const healthy = state.data.status === "ok";
    dot = healthy ? "bg-positive" : "bg-warning";
    label = healthy ? "API online" : "API degraded";
  }

  return (
    <span
      className="inline-flex items-center gap-2 rounded-md border border-line px-2.5 py-1 text-xs text-ink-muted"
      role="status"
    >
      <span className={`size-2 rounded-full ${dot}`} aria-hidden />
      {label}
    </span>
  );
}
