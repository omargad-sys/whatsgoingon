import type { Holding } from "./types";

export function bps(value: number, opts: { sign?: boolean } = {}): string {
  const v = value * 10000;
  const shown = Math.abs(v) < 0.5 ? 0 : Math.round(v);
  const sign = opts.sign !== false && shown > 0 ? "+" : "";
  return `${sign}${shown} bps`;
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number, digits = 2): string {
  const s = value > 0 ? "+" : "";
  return `${s}${(value * 100).toFixed(digits)}%`;
}

export function shortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
}

export function monthLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return d.toLocaleDateString(undefined, { month: "short", year: "2-digit", timeZone: "UTC" });
}

export function relativeAge(iso: string): string {
  const days = (Date.now() - Date.parse(iso)) / 86_400_000;
  if (!Number.isFinite(days)) return "unknown";
  if (days < 1) return "today";
  if (days < 2) return "yesterday";
  if (days < 30) return `${Math.round(days)} days ago`;
  return `${Math.round(days / 30)} months ago`;
}

export function describeShock(z: number | null | undefined): string {
  if (z === null || z === undefined || !Number.isFinite(z)) return "no reading";
  const a = Math.abs(z);
  const dir = z > 0 ? "above" : "below";
  if (a < 0.5) return "near normal";
  if (a < 1) return `mildly ${dir} normal`;
  if (a < 2) return `${dir} normal`;
  if (a < 3) return `well ${dir} normal`;
  return `extreme, ${dir} normal`;
}

/* ------------------------------------------------------------ URL state */

/** Encode holdings as `VOO:50,XLE:30,GLD:20` so a portfolio is a shareable link. */
export function encodeHoldings(holdings: Holding[]): string {
  return holdings
    .filter((h) => h.ticker && h.weight > 0)
    .map((h) => `${h.ticker}:${Math.round(h.weight * 1000) / 10}`)
    .join(",");
}

export function decodeHoldings(raw: string | null, allowed: string[]): Holding[] | null {
  if (!raw) return null;
  const allow = new Set(allowed);
  const out: Holding[] = [];
  const seen = new Set<string>();

  for (const part of raw.split(",")) {
    const [ticker, weightRaw] = part.split(":");
    const t = (ticker ?? "").trim().toUpperCase();
    if (!allow.has(t) || seen.has(t)) continue;
    const w = Number.parseFloat(weightRaw ?? "");
    if (!Number.isFinite(w) || w <= 0) continue;
    seen.add(t);
    out.push({ ticker: t, weight: w / 100 });
  }
  return out.length ? out : null;
}

/* --------------------------------------------------------------- data lag */

export interface DataLag {
  /** last day of ACLED coverage in this build, YYYY-MM-DD */
  cutoff: string;
  days: number;
  /** true once the gap is wide enough that calling the map "current" misleads */
  material: boolean;
  /** human phrasing, e.g. "about 12 months" */
  phrase: string;
}

/**
 * How far behind today the underlying events actually are.
 *
 * This is not cosmetic. ACLED's Research tier serves event data on a rolling
 * delay, measured at 364 days on the account this site runs on. A map built
 * from that data is a picture of last year, and a site that renders it under
 * the word "live" is lying about the one thing a conflict map is for. The
 * number comes from the artifacts rather than a hardcoded constant, so it
 * self-corrects if the account is ever upgraded to a weekly tier.
 */
export function dataLag(lastWeek: string | null): DataLag | null {
  if (!lastWeek) return null;
  const t = Date.parse(lastWeek);
  if (!Number.isFinite(t)) return null;

  const days = Math.max(0, Math.round((Date.now() - t) / 86_400_000));
  const months = days / 30.44;
  const phrase =
    days < 45
      ? `${days} days`
      : months < 22
        ? `about ${Math.round(months)} months`
        : `about ${(months / 12).toFixed(1)} years`;

  return { cutoff: lastWeek, days, material: days >= 45, phrase };
}
