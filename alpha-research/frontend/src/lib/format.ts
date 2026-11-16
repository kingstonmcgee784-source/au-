/** Display formatting. Missing values render as an em dash, never as zero. */

const MISSING = "—";

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return MISSING;
  return value.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return MISSING;
  return value.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 2 });
}

export function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return MISSING;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return MISSING;
  // Plain dates ("2026-11-16") are calendar dates, not instants: avoid a timezone shift.
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date(value);
  return date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export function changeTone(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return "text-ink-muted";
  return value > 0 ? "text-positive" : "text-negative";
}

/** "sma_200" -> "SMA 200", "macd_signal" -> "MACD signal". */
export function indicatorLabel(name: string): string {
  const [head, ...rest] = name.split("_");
  return [head.toUpperCase(), ...rest].join(" ");
}

export function humanize(key: string): string {
  const spaced = key.replace(/_/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
