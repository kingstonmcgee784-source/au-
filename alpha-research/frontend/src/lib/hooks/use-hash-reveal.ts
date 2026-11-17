"use client";

import { useEffect } from "react";

/**
 * Opens a collapsed section when an in-page link points into it.
 *
 * `targets` are element ids or id prefixes (ending in "-"). When a link to
 * "#<id>" is clicked (or the hash changes) and the id matches, `reveal(id)` is
 * called, and the element is scrolled into view once it has rendered.
 */
export function useHashReveal(targets: string[], reveal: (id: string) => void): void {
  const key = targets.join("|");
  useEffect(() => {
    const list = key ? key.split("|") : [];
    const matches = (id: string) =>
      list.some((t) => (t.endsWith("-") ? id.startsWith(t) : id === t));
    const handle = (id: string) => {
      if (!id || !matches(id)) return;
      reveal(id);
      window.setTimeout(
        () => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }),
        60,
      );
    };
    const onClick = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest?.('a[href^="#"]');
      const href = link?.getAttribute("href");
      if (href) handle(href.slice(1));
    };
    const onHash = () => handle(window.location.hash.slice(1));
    document.addEventListener("click", onClick);
    window.addEventListener("hashchange", onHash);
    return () => {
      document.removeEventListener("click", onClick);
      window.removeEventListener("hashchange", onHash);
    };
  }, [key, reveal]);
}
