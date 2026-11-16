"use client";

import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Panel } from "@/components/ui/panel";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { formatDate } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";

export function RecentResearchPanel({ limit = 5 }: { limit?: number }) {
  const { state, reload } = useApi(`reports-${limit}`, () => api.reports(limit));

  return (
    <Panel title="Recent research" icon={FileText}>
      {state.kind === "loading" && <LoadingState label="Loading reports" />}
      {state.kind === "error" && <ErrorState error={state.error} onRetry={reload} />}
      {state.kind === "success" &&
        (state.data.length === 0 ? (
          <EmptyState title="No research reports yet">
            Reports appear here once they are saved. AI report generation is not connected yet.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line/60">
            {state.data.map((report) => (
              <li key={report.id} className="py-2.5 first:pt-0 last:pb-0">
                <div className="flex items-center justify-between gap-3">
                  <p className="truncate text-sm text-ink">{report.title}</p>
                  <Badge tone={report.origin === "ai_generated" ? "info" : "neutral"}>
                    {report.origin === "ai_generated" ? "AI" : "Manual"}
                  </Badge>
                </div>
                <p className="mt-0.5 text-xs text-ink-faint">
                  {formatDate(report.report_date)} · {report.status}
                </p>
              </li>
            ))}
          </ul>
        ))}
    </Panel>
  );
}
