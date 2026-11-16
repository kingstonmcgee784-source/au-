import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center gap-3 py-20 text-center">
      <p className="font-mono text-sm text-accent">404</p>
      <h1 className="text-lg font-semibold text-ink">Page not found</h1>
      <Link href="/" className="text-sm text-ink-muted hover:text-accent">
        Back to Overview
      </Link>
    </div>
  );
}
