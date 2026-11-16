"use client";

import { Activity, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV_ITEMS, type FeatureStage } from "@/lib/navigation";

const STAGE_DOT: Record<FeatureStage, string> = {
  live: "bg-positive",
  partial: "bg-info",
  planned: "bg-warning",
};

const STAGE_TITLE: Record<FeatureStage, string> = {
  live: "Live",
  partial: "Built, needs data integrations",
  planned: "Planned, not built yet",
};

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();

  return (
    <>
      {/* Backdrop for the mobile drawer. */}
      <div
        className={`fixed inset-0 z-30 bg-black/60 lg:hidden ${open ? "block" : "hidden"}`}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-line bg-surface transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Main navigation"
      >
        <div className="flex h-14 items-center justify-between border-b border-line px-4">
          <Link href="/" className="flex items-center gap-2" onClick={onClose}>
            <span className="flex size-7 items-center justify-center rounded bg-accent text-canvas">
              <Activity className="size-4" aria-hidden />
            </span>
            <span className="text-sm font-semibold tracking-tight">
              Alpha <span className="text-accent">Research</span>
            </span>
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-ink-muted hover:text-ink lg:hidden"
            aria-label="Close navigation"
          >
            <X className="size-4" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3">
          <ul className="space-y-0.5">
            {NAV_ITEMS.map(({ href, label, icon: Icon, stage }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    onClick={onClose}
                    aria-current={active ? "page" : undefined}
                    className={`group flex items-center gap-3 rounded-md px-2.5 py-2 text-sm transition-colors ${
                      active
                        ? "bg-surface-raised text-ink"
                        : "text-ink-muted hover:bg-surface-raised/60 hover:text-ink"
                    }`}
                  >
                    <Icon
                      className={`size-4 shrink-0 ${active ? "text-accent" : "text-ink-faint group-hover:text-ink-muted"}`}
                      aria-hidden
                    />
                    <span className="flex-1 truncate">{label}</span>
                    <span
                      className={`size-1.5 rounded-full ${STAGE_DOT[stage]}`}
                      title={STAGE_TITLE[stage]}
                    />
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="space-y-1.5 border-t border-line px-4 py-3 text-[11px] text-ink-faint">
          {(Object.keys(STAGE_DOT) as FeatureStage[]).map((stage) => (
            <div key={stage} className="flex items-center gap-2">
              <span className={`size-1.5 rounded-full ${STAGE_DOT[stage]}`} />
              {STAGE_TITLE[stage]}
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}
