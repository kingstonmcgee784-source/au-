"use client";

import { ChevronDown, ChevronRight, type LucideIcon } from "lucide-react";
import { type ReactNode, useCallback, useState } from "react";

import { useHashReveal } from "@/lib/hooks/use-hash-reveal";

interface PanelProps {
  title: string;
  id?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
  footer?: ReactNode;
  className?: string;
  /** Start closed; the title opens and closes it. */
  collapsible?: boolean;
  /** Extra element ids (or id prefixes ending in "-") whose links open the panel. */
  opensFor?: string[];
  children: ReactNode;
}

/** The standard bordered card used for every dashboard section. */
export function Panel({
  title,
  id,
  icon: Icon,
  actions,
  footer,
  className = "",
  collapsible = false,
  opensFor = [],
  children,
}: PanelProps) {
  const [open, setOpen] = useState(!collapsible);
  const reveal = useCallback(() => setOpen(true), []);
  useHashReveal(collapsible ? [...(id ? [id] : []), ...opensFor] : [], reveal);
  const Chevron = open ? ChevronDown : ChevronRight;

  const heading = (
    <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-muted">
      {collapsible && <Chevron className="size-3.5 text-ink-faint" aria-hidden />}
      {Icon && <Icon className="size-3.5 text-accent" aria-hidden />}
      {title}
      {collapsible && !open && (
        <span className="font-normal normal-case tracking-normal text-ink-faint">· click to show</span>
      )}
    </h2>
  );

  return (
    <section
      id={id}
      className={`flex min-w-0 scroll-mt-20 flex-col rounded-lg border border-line bg-surface ${className}`}
    >
      <header
        className={`flex items-center justify-between gap-3 px-4 py-2.5 ${open ? "border-b border-line" : ""}`}
      >
        {collapsible ? (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className="-my-1 flex-1 py-1 text-left hover:[&_h2]:text-ink"
          >
            {heading}
          </button>
        ) : (
          heading
        )}
        {actions && open && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      {open && <div className="flex-1 p-4">{children}</div>}
      {open && footer && (
        <footer className="border-t border-line px-4 py-2 text-xs text-ink-faint">{footer}</footer>
      )}
    </section>
  );
}
