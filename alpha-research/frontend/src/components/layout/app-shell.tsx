"use client";

import { type ReactNode, useState } from "react";

import { Sidebar } from "./sidebar";
import { TopBar } from "./top-bar";

export function AppShell({ children }: { children: ReactNode }) {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onOpenNavigation={() => setNavOpen(true)} />
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 lg:px-6">{children}</main>
      </div>
    </div>
  );
}
