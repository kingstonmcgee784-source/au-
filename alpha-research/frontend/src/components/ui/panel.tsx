import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface PanelProps {
  title: string;
  icon?: LucideIcon;
  actions?: ReactNode;
  footer?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** The standard bordered card used for every dashboard section. */
export function Panel({ title, icon: Icon, actions, footer, className = "", children }: PanelProps) {
  return (
    <section
      className={`flex min-w-0 flex-col rounded-lg border border-line bg-surface ${className}`}
    >
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
        <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-muted">
          {Icon && <Icon className="size-3.5 text-accent" aria-hidden />}
          {title}
        </h2>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      <div className="flex-1 p-4">{children}</div>
      {footer && <footer className="border-t border-line px-4 py-2 text-xs text-ink-faint">{footer}</footer>}
    </section>
  );
}
