import { THEMES } from "./themes";
import type { PairLookup, ThemeImpact } from "./exposure";
import type { Forecast, Holding, Link, ThemeId } from "./types";

/**
 * The three-layer chain, and the three places it is allowed to break.
 *
 *   layer 1  forecaster   ->  P(escalation) per country next month
 *   layer 2  link         ->  expected theme shock, in sigma
 *   layer 3  sensitivity  ->  expected ticker return
 *
 *      E[frac_T]   = mean of P over the theme's member countries
 *      E[z_T]      = a_T + b_T * E[frac_T]
 *      E[r_k]      = beta_kT * E[z_T]
 *
 * Every layer has its own significance gate, and a number reaches the screen
 * only if all three hold. That is deliberately conservative: chaining two
 * noisy estimates multiplies their error, so a chain built from two barely
 * significant links deserves less confidence than either link alone, not more.
 */

export interface ThemeForecast {
  theme: ThemeId;
  /** expected share of the theme's countries escalating */
  expectedFraction: number;
  /** how many member countries the forecast actually covers */
  covered: number;
  members: number;
  /** expected shock in sigma, undefined when the link is not identified */
  expectedShock?: number;
  shockSe?: number;
  linkOk: boolean;
}

export function themeForecast(
  forecast: Forecast,
  link: Link,
  theme: ThemeId,
  allCountries: string[],
): ThemeForecast {
  const members =
    theme === "global" ? allCountries : THEMES[theme].countries;

  const ps: number[] = [];
  for (const c of members) {
    const row = forecast.countries[c];
    if (row && Number.isFinite(row.p)) ps.push(row.p);
  }

  const expectedFraction = ps.length ? ps.reduce((a, b) => a + b, 0) / ps.length : 0;
  const l = link.themes[theme];
  const linkOk = Boolean(l?.significant) && ps.length > 0;

  if (!l || !linkOk) {
    return { theme, expectedFraction, covered: ps.length, members: members.length, linkOk: false };
  }

  return {
    theme,
    expectedFraction,
    covered: ps.length,
    members: members.length,
    expectedShock: l.intercept + l.slope * expectedFraction,
    // Uncertainty in the slope only. The intercept's error and the
    // forecaster's own error are not propagated, so this band is a floor.
    shockSe: Math.abs(l.se * expectedFraction),
    linkOk: true,
  };
}

export interface ChainedHolding {
  ticker: string;
  weight: number;
  /** expected return over the forecast horizon, undefined when any layer breaks */
  expectedReturn?: number;
  se?: number;
  blockedAt?: "link" | "sensitivity" | "forecast";
}

export interface ChainedThemeImpact {
  theme: ThemeId;
  forecast: ThemeForecast;
  holdings: ChainedHolding[];
  /** weighted portfolio expected return for this theme */
  expectedReturn: number;
  se: number;
  coverage: number;
  empty: boolean;
}

export function chainTheme(
  holdings: Holding[],
  theme: ThemeId,
  lookup: PairLookup,
  forecast: Forecast,
  link: Link,
  allCountries: string[],
): ChainedThemeImpact {
  const tf = themeForecast(forecast, link, theme, allCountries);

  const total = holdings.reduce((s, h) => s + (h.weight > 0 ? h.weight : 0), 0);
  const weighted = holdings.map((h) => ({
    ...h,
    weight: total > 0 ? h.weight / total : 0,
  }));

  let expectedReturn = 0;
  let variance = 0;
  let coverage = 0;

  const rows: ChainedHolding[] = weighted.map((h) => {
    if (!tf.linkOk || tf.expectedShock === undefined) {
      return { ticker: h.ticker, weight: h.weight, blockedAt: "link" };
    }
    const pair = lookup.get(h.ticker, theme);
    if (!pair || !pair.significant) {
      return { ticker: h.ticker, weight: h.weight, blockedAt: "sensitivity" };
    }

    const z = tf.expectedShock;
    const expected = pair.beta * z;
    // First-order error propagation for a product of two estimates:
    // Var(b*z) ~ z^2 Var(b) + b^2 Var(z).
    const se = Math.sqrt(
      z * z * pair.se * pair.se + pair.beta * pair.beta * (tf.shockSe ?? 0) ** 2,
    );

    expectedReturn += h.weight * expected;
    variance += (h.weight * se) ** 2;
    coverage += h.weight;

    return { ticker: h.ticker, weight: h.weight, expectedReturn: expected, se };
  });

  return {
    theme,
    forecast: tf,
    holdings: rows,
    expectedReturn,
    se: Math.sqrt(variance),
    coverage,
    empty: rows.every((r) => r.expectedReturn === undefined),
  };
}

export function chainAll(
  holdings: Holding[],
  themes: ThemeId[],
  lookup: PairLookup,
  forecast: Forecast,
  link: Link,
  allCountries: string[],
): ChainedThemeImpact[] {
  return themes.map((t) => chainTheme(holdings, t, lookup, forecast, link, allCountries));
}

/** Portfolio total, excluding `global` because it double counts the regions. */
export function chainedTotal(impacts: ChainedThemeImpact[]): {
  value: number;
  themesCounted: number;
} {
  let value = 0;
  let themesCounted = 0;
  for (const im of impacts) {
    if (im.theme === "global" || im.empty) continue;
    value += im.expectedReturn;
    themesCounted += 1;
  }
  return { value, themesCounted };
}

/** Countries ranked by escalation probability, for the risk list. */
export function rankedRisk(forecast: Forecast, limit = 12) {
  return Object.entries(forecast.countries)
    .map(([country, v]) => ({ country, ...v }))
    .sort((a, b) => b.p - a.p)
    .slice(0, limit);
}

/** Where a theme's chain breaks, in words, for the empty state. */
export function explainBreak(im: ChainedThemeImpact, tstatThreshold: number): string {
  if (!im.forecast.linkOk) {
    return `Escalation in these countries has no measurable effect on the theme's own conflict intensity (link |t| below ${tstatThreshold}), so the chain stops here.`;
  }
  if (im.empty) {
    return "The theme shock is measurable, but none of your holdings has an identified response to it.";
  }
  return "";
}

/** Reused by both impact panels so the two never drift apart. */
export function toThemeImpactShape(im: ChainedThemeImpact): ThemeImpact {
  return {
    theme: im.theme,
    impact: im.expectedReturn,
    se: im.se,
    coverage: im.coverage,
    empty: im.empty,
    holdings: im.holdings.map((h) => ({
      ticker: h.ticker,
      weight: h.weight,
      contribution: h.expectedReturn,
      status: h.expectedReturn !== undefined ? "identified" : "not-identified",
    })),
  };
}

/* ------------------------------------------------------- holdings-first view */

export interface ThemeDriver {
  theme: ThemeId;
  contribution: number;
}

export interface HoldingOutlook {
  ticker: string;
  weight: number;
  /** Expected return for this ticker over the forecast horizon. */
  expected?: number;
  se?: number;
  /** Which themes drove it, largest absolute contribution first. */
  drivers: ThemeDriver[];
  /** Why there is no number, when there isn't one. */
  blocked: "none" | "no-link" | "no-sensitivity";
}

/**
 * Reorganises the chain by ticker instead of by theme.
 *
 * The theme-first view answers "what does Middle East conflict do to markets",
 * which is the analyst's question. Someone looking at their own portfolio is
 * asking "what happens to the things I own", and reorganising the same numbers
 * around that question is most of the difference between the tool feeling
 * legible and feeling like a stats dump.
 *
 * `global` is excluded because it overlaps every regional theme by construction
 * and would double count.
 */
export function holdingOutlooks(
  holdings: Holding[],
  themes: ThemeId[],
  lookup: PairLookup,
  forecast: Forecast,
  link: Link,
  allCountries: string[],
): HoldingOutlook[] {
  const regional = themes.filter((t) => t !== "global");
  const shocks = new Map<ThemeId, ThemeForecast>();
  for (const t of regional) {
    shocks.set(t, themeForecast(forecast, link, t, allCountries));
  }

  const total = holdings.reduce((s, h) => s + (h.weight > 0 ? h.weight : 0), 0);

  return holdings.map((h) => {
    const weight = total > 0 ? h.weight / total : 0;
    const drivers: ThemeDriver[] = [];
    let expected = 0;
    let variance = 0;
    let sawLink = false;
    let sawPair = false;

    for (const theme of regional) {
      const tf = shocks.get(theme);
      if (!tf?.linkOk || tf.expectedShock === undefined) continue;
      sawLink = true;

      const pair = lookup.get(h.ticker, theme);
      if (!pair || !pair.significant) continue;
      sawPair = true;

      const z = tf.expectedShock;
      const contribution = pair.beta * z;
      expected += contribution;
      variance +=
        z * z * pair.se * pair.se + pair.beta * pair.beta * (tf.shockSe ?? 0) ** 2;
      drivers.push({ theme, contribution });
    }

    drivers.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));

    if (!sawPair) {
      return {
        ticker: h.ticker,
        weight,
        drivers: [],
        blocked: sawLink ? "no-sensitivity" : "no-link",
      };
    }

    return {
      ticker: h.ticker,
      weight,
      expected,
      se: Math.sqrt(variance),
      drivers,
      blocked: "none",
    };
  });
}

/** Portfolio total from the holdings view, so the headline and the rows agree. */
export function portfolioOutlook(outlooks: HoldingOutlook[]) {
  let value = 0;
  let covered = 0;
  let measured = 0;
  for (const o of outlooks) {
    if (o.expected === undefined) continue;
    value += o.weight * o.expected;
    covered += o.weight;
    measured += 1;
  }
  return { value, covered, measured, total: outlooks.length };
}


/* ------------------------------------------------------------ what moved */

export interface Mover {
  country: string;
  now: number;
  then: number;
  delta: number;
}

/**
 * Countries whose escalation probability moved most since the previous run.
 *
 * Returns an empty list when there is no previous run rather than inventing a
 * baseline, so a first deploy shows nothing instead of claiming everything just
 * changed. `minDelta` filters out the churn that is really just the model
 * re-fitting on one more month of data.
 */
export function movers(forecast: Forecast, limit = 3, minDelta = 0.03): Mover[] {
  const prev = forecast.previous;
  if (!prev?.countries) return [];

  const out: Mover[] = [];
  for (const [country, row] of Object.entries(forecast.countries)) {
    const then = prev.countries[country];
    if (then === undefined || !Number.isFinite(then)) continue;
    const delta = row.p - then;
    if (Math.abs(delta) < minDelta) continue;
    out.push({ country, now: row.p, then, delta });
  }

  return out.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, limit);
}

/** Per-country lookup of movement, for annotating the risk list. */
export function moverMap(forecast: Forecast, minDelta = 0.03): Record<string, number> {
  return Object.fromEntries(movers(forecast, Number.MAX_SAFE_INTEGER, minDelta).map((m) => [m.country, m.delta]));
}
