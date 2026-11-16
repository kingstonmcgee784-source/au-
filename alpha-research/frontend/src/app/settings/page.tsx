import type { Metadata } from "next";

import { SystemStatusPanel } from "@/components/dashboard/system-status";
import { Panel } from "@/components/ui/panel";
import { PageHeader } from "@/components/ui/page-header";
import { navItem } from "@/lib/navigation";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <>
      <PageHeader item={navItem("/settings")} />
      <div className="grid gap-4 lg:grid-cols-2">
        <SystemStatusPanel />
        <Panel title="Configuration">
          <div className="space-y-3 text-sm text-ink-muted">
            <p>
              All configuration, including API keys, lives in the backend&apos;s environment
              (<code className="font-mono text-ink">backend/.env</code>). Keys are never stored in
              or sent to the browser.
            </p>
            <ul className="list-disc space-y-1 pl-5">
              <li>
                <code className="font-mono text-ink">MARKET_DATA_PROVIDER=tiingo</code> and{" "}
                <code className="font-mono text-ink">MARKET_DATA_API_KEY</code>: quotes, daily
                price history and the market overview
              </li>
              <li>
                <code className="font-mono text-ink">AI_PROVIDER</code> and{" "}
                <code className="font-mono text-ink">AI_API_KEY</code>: AI research reports
              </li>
              <li>
                <code className="font-mono text-ink">DATABASE_URL</code>: SQLite by default
              </li>
            </ul>
            <p className="rounded-md border border-dashed border-warning/40 p-3 text-xs">
              Editing settings from this page is not built yet. Change the environment file and
              restart the backend.
            </p>
          </div>
        </Panel>
      </div>
    </>
  );
}
