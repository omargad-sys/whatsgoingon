import type { Holding, SensitivityPair, Sensitivities, ThemeId } from "./types";
import { PARTITION_THEMES } from "./themes";

/**
 * The overlay math, and the guardrail that gives it whatever credibility it has.
 *
 * A sensitivity `beta` is the estimated same-month return of one ticker for a
 * +1 sigma conflict shock in one theme, net of the market. Portfolio impact is
 * the weighted sum of those betas, but ONLY over pairs the model actually
 * identified. A pair that failed the |t| gate or the family-wide FDR gate
 * contributes nothing and is never rendered as a number: an unidentified
 * relationship is not a zero relationship, and pretending otherwise is the
 * single easiest way for a tool like this to start lying.
 */

export interface PairLookup {
  get(ticker: string, theme: ThemeId): SensitivityPair | undefined;
}

export function buildLookup(sens: Sensitivities): PairLookup {
  const map = new Map<string, SensitivityPair>();
  for (const p of sens.pairs) map.set(`${p.ticker}|${p.theme}`, p);
  return { get: (t, th) => map.get(`${t}|${th}`) };
}

export interface HoldingImpact {
  ticker: string;
  weight: number;
  pair?: SensitivityPair;
  /** weight * beta, in return units. Undefined when not identified. */
  contribution?: number;
  status: "identified" | "not-identified" | "no-estimate";
}

export interface ThemeImpact {
  theme: ThemeId;
  /** Sum of identified contributions, in return units. */
  impact: number;
  /** 1 standard error of the summed impact, treating pairs as independent. */
  se: number;
  /** Fraction of portfolio weight that had an identified relationship. */
  coverage: number;
  holdings: HoldingImpact[];
  /** True when no holding had an identified relationship to this theme. */
  empty: boolean;
}

export function normalizeWeights(holdings: Holding[]): Holding[] {
  const total = holdings.reduce((s, h) => s + (Number.isFinite(h.weight) ? h.weight : 0), 0);
  if (total <= 0) return holdings.map((h) => ({ ...h, weight: 0 }));
  return holdings.map((h) => ({ ...h, weight: h.weight / total }));
}

export function themeImpact(
  holdings: Holding[],
  theme: ThemeId,
  lookup: PairLookup,
): ThemeImpact {
  const weighted = normalizeWeights(holdings);

  let impact = 0;
  let variance = 0;
  let coverage = 0;

  const rows: HoldingImpact[] = weighted.map((h) => {
    const pair = lookup.get(h.ticker, theme);
    if (!pair) return { ticker: h.ticker, weight: h.weight, status: "no-estimate" };
    if (!pair.significant) {
      return { ticker: h.ticker, weight: h.weight, pair, status: "not-identified" };
    }
    const contribution = h.weight * pair.beta;
    impact += contribution;
    // Independence across holdings is optimistic (ETFs overlap), so this band
    // is a floor on the true uncertainty, not a confidence interval to trust.
    variance += (h.weight * pair.se) ** 2;
    coverage += h.weight;
    return { ticker: h.ticker, weight: h.weight, pair, contribution, status: "identified" };
  });

  return {
    theme,
    impact,
    se: Math.sqrt(variance),
    coverage,
    holdings: rows,
    empty: rows.every((r) => r.status !== "identified"),
  };
}

export function allThemeImpacts(
  holdings: Holding[],
  themes: ThemeId[],
  lookup: PairLookup,
): ThemeImpact[] {
  return themes.map((t) => themeImpact(holdings, t, lookup));
}

/**
 * Impact scaled by the shock that is actually happening right now, rather than
 * by a hypothetical 1 sigma. Returns undefined when the current shock is
 * unknown, so the UI shows "no reading" instead of implying zero.
 */
export function currentImpact(
  impact: ThemeImpact,
  currentShock: Partial<Record<ThemeId, number | null>>,
): number | undefined {
  const z = currentShock[impact.theme];
  if (z === null || z === undefined || !Number.isFinite(z)) return undefined;
  return impact.impact * z;
}

/** Portfolio-level impact across all themes, for a "shock everything" reading. */
export function totalCurrentImpact(
  impacts: ThemeImpact[],
  currentShock: Partial<Record<ThemeId, number | null>>,
): { value: number; themesCounted: number } {
  let value = 0;
  let themesCounted = 0;
  // Only the partition is summable. Overlay themes (`oil_supply`, `global`)
  // share countries with the regions, so adding them would count Iran once as
  // a Gulf producer and again as a MENA country.
  const summable = new Set<ThemeId>(PARTITION_THEMES);
  for (const im of impacts) {
    if (!summable.has(im.theme)) continue;
    const v = currentImpact(im, currentShock);
    if (v === undefined || im.empty) continue;
    value += v;
    themesCounted += 1;
  }
  return { value, themesCounted };
}
