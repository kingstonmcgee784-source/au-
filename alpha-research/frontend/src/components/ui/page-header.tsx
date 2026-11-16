import type { ReactNode } from "react";

import type { NavItem } from "@/lib/navigation";

import { StageBadge } from "./badge";

export function PageHeader({ item, actions }: { item: NavItem; actions?: ReactNode }) {
  const Icon = item.icon;
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-1">
        <div className="flex items-center gap-3">
          <Icon className="size-5 text-accent" aria-hidden />
          <h1 className="text-xl font-semibold tracking-tight text-ink">{item.label}</h1>
          <StageBadge stage={item.stage} />
        </div>
        <p className="text-sm text-ink-muted">{item.description}</p>
      </div>
      {actions}
    </div>
  );
}
