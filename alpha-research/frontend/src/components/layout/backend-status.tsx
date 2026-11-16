"use client";

import { useHealth } from "./health-context";

/** Small indicator showing whether the frontend can reach the backend. */
export function BackendStatus() {
  const { state } = useHealth();

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
