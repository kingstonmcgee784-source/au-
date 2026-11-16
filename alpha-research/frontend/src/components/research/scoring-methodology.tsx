"use client";

import { Scale } from "lucide-react";

import { Panel } from "@/components/ui/panel";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { useApi } from "@/lib/hooks/use-api";

/** The weights and score bands, served by the backend's scoring module. */
export function ScoringMethodologyPanel() {
  const { state, reload } = useApi("scoring-methodology", api.scoringMethodology);

  return (
    <Panel title="Scoring methodology" icon={Scale}>
      {state.kind === "loading" && <LoadingState />}
      {state.kind === "error" && <ErrorState error={state.error} onRetry={reload} />}
      {state.kind === "success" && (
        <div className="space-y-4 text-sm">
          <ul className="space-y-2">
            {state.data.categories.map((category) => (
              <li key={category.key}>
                <div className="flex justify-between text-ink-muted">
                  <span>{category.label}</span>
                  <span className="font-mono text-ink">{category.weight}</span>
                </div>
                <div className="mt-1 h-1 rounded bg-surface-raised">
                  <div
                    className="h-1 rounded bg-accent"
                    style={{
                      width: `${(category.weight / Math.max(...state.data.categories.map((c) => c.weight))) * 100}%`,
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-faint">
              Score bands
            </h3>
            <ul className="mt-2 space-y-1">
              {state.data.bands.map((band) => (
                <li key={band.min_score} className="flex justify-between text-ink-muted">
                  <span>{band.label}</span>
                  <span className="font-mono text-ink">{band.min_score}+</span>
                </li>
              ))}
            </ul>
          </div>
          <p className="text-xs text-ink-faint">Methodology v{state.data.version}</p>
        </div>
      )}
    </Panel>
  );
}
