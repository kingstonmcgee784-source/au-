/** Mirrors the backend's ticker rule in app/schemas/common.py. */
const TICKER_PATTERN = /^[A-Z][A-Z0-9]{0,9}([.-][A-Z0-9]{1,4})?$/;

export function normalizeTicker(value: string): string {
  return value.trim().toUpperCase();
}

export function isValidTicker(value: string): boolean {
  return TICKER_PATTERN.test(value);
}
