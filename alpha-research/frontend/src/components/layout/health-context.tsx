"use client";

import { createContext, type ReactNode, useContext, useEffect } from "react";

import { api } from "@/lib/api/client";
import type { HealthResponse } from "@/lib/api/types";
import { type ApiState, useApi } from "@/lib/hooks/use-api";
import { featureStatus, type FeatureStatus, navItem } from "@/lib/navigation";

const POLL_MS = 30_000;

interface HealthContextValue {
  state: ApiState<HealthResponse>;
  reload: () => void;
}

const HealthContext = createContext<HealthContextValue | null>(null);

/** Polls GET /health once for the whole app and shares the result. */
export function HealthProvider({ children }: { children: ReactNode }) {
  const { state, reload } = useApi("health", api.health);

  useEffect(() => {
    const id = window.setInterval(reload, POLL_MS);
    return () => window.clearInterval(id);
  }, [reload]);

  return <HealthContext.Provider value={{ state, reload }}>{children}</HealthContext.Provider>;
}

export function useHealth(): HealthContextValue {
  const value = useContext(HealthContext);
  if (!value) throw new Error("useHealth must be used inside HealthProvider");
  return value;
}

/** Live status of the section at `href`, based on which integrations are configured. */
export function useFeatureStatus(href: string): FeatureStatus {
  const { state } = useHealth();
  const health = state.kind === "success" ? state.data : null;
  return featureStatus(navItem(href), health);
}
