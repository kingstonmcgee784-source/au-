"use client";

import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";

import { findNavItem } from "@/lib/navigation";

import { BackendStatus } from "./backend-status";
import { TickerSearch } from "./ticker-search";

export function TopBar({ onOpenNavigation }: { onOpenNavigation: () => void }) {
  const pathname = usePathname();
  const current = findNavItem(pathname);

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-canvas/90 px-4 backdrop-blur lg:px-6">
      <button
        type="button"
        onClick={onOpenNavigation}
        className="rounded p-1.5 text-ink-muted hover:text-ink lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="size-5" />
      </button>
      <p className="hidden truncate text-sm text-ink-muted md:block">
        {current?.label ?? "Alpha Research"}
      </p>
      <div className="ml-auto flex min-w-0 items-center gap-3">
        <TickerSearch />
        <div className="hidden sm:block">
          <BackendStatus />
        </div>
      </div>
    </header>
  );
}
