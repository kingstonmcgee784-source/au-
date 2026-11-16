"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/lib/api/client";

export type ApiState<T> =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; data: T }
  | { kind: "error"; error: ApiError };

/**
 * Run an API call when `key` changes (pass null to skip) and expose its state.
 * `reload` runs it again, e.g. after a mutation.
 */
export function useApi<T>(
  key: string | null,
  fetcher: () => Promise<T>,
): { state: ApiState<T>; reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ kind: key ? "loading" : "idle" });
  const [attempt, setAttempt] = useState(0);
  const [trackedKey, setTrackedKey] = useState(key);

  // Reset to loading when the request changes, without an extra render pass.
  if (key !== trackedKey) {
    setTrackedKey(key);
    setState({ kind: key ? "loading" : "idle" });
  }

  useEffect(() => {
    if (key === null) return;
    let cancelled = false;
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ kind: "success", data });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({
          kind: "error",
          error: error instanceof ApiError ? error : new ApiError(String(error), null),
        });
      });
    return () => {
      cancelled = true;
    };
    // `fetcher` is intentionally excluded: callers pass inline closures and
    // `key` already identifies the request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, reload };
}
