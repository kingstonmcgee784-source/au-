"use client";

import { Server } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import type { IntegrationState } from "@/lib/api/types";
import { useApi } from "@/lib/hooks/use-api";

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}

function IntegrationBadge({ state }: { state: IntegrationState }) {
  return state === "configured" ? (
    <Badge tone="positive">Connected</Badge>
  ) : (
    <Badge tone="warning">Not connected</Badge>
  );
}

/** Live status from GET /health: API, database schema and integrations. */
export function SystemStatusPanel() {
  const { state, reload } = useApi("health-panel", api.health);

  return (
    <Panel title="System status" icon={Server}>
      {state.kind === "loading" && <LoadingState label="Checking backend" />}
      {state.kind === "error" && <ErrorState error={state.error} onRetry={reload} />}
      {state.kind === "success" && (
        <dl className="divide-y divide-line/60">
          <Row label="API">
            <Badge tone={state.data.status === "ok" ? "positive" : "warning"}>
              {state.data.status}
            </Badge>{" "}
            <span className="ml-1 font-mono text-xs text-ink-faint">v{state.data.version}</span>
          </Row>
          <Row label="Database">
            <Badge tone={state.data.database.connected ? "positive" : "negative"}>
              {state.data.database.connected ? "Connected" : "Unreachable"}
            </Badge>
          </Row>
          <Row label="Schema">
            <span className="font-mono text-xs text-ink-muted">
              {state.data.database.revision ?? "none"}
              {state.data.database.up_to_date ? " (current)" : ` (head ${state.data.database.head_revision})`}
            </span>
          </Row>
          <Row label="Market data">
            <IntegrationBadge state={state.data.integrations.market_data} />
          </Row>
          <Row label="Fundamentals (SEC)">
            <IntegrationBadge state={state.data.integrations.fundamentals} />
          </Row>
          <Row label="AI research">
            <IntegrationBadge state={state.data.integrations.ai_research} />
          </Row>
          <Row label="Environment">
            <span className="font-mono text-xs text-ink-muted">{state.data.environment}</span>
          </Row>
        </dl>
      )}
    </Panel>
  );
}
