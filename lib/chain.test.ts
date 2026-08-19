/**
 * Chain math tests.
 *
 *   bun test lib/chain.test.ts
 *
 * Uses bun's built-in runner so it needs no dependency install. If you'd rather
 * use vitest later, the assertions are plain and will port unchanged.
 */

import { expect, test } from "bun:test";

import {
  chainAll,
  chainTheme,
  chainedTotal,
  holdingOutlooks,
  movers,
  portfolioOutlook,
  rankedRisk,
  themeForecast,
} from "./chain";
import { buildLookup } from "./exposure";
import { PARTITION_THEMES, THEMES } from "./themes";
import type { Forecast, Link, Sensitivities, ThemeId } from "./types";
import { dataLag } from "./format";

const ALL = ["Iran", "Iraq", "Saudi Arabia", "Ukraine", "Russia"];

function forecast(ps: Record<string, number>): Forecast {
  return {
    generated_at: "2026-08-01T00:00:00Z",
    as_of_month: "2026-07-01",
    target_month: "2026-08-01",
    lookahead_months: 1,
    threshold_quantile: 0.75,
    source: "model",
    backend: "xgboost",
    evaluation: {
      model_roc_auc: 0.8, baseline_roc_auc: 0.7, margin: 0.1,
      model_brier: 0.1, baseline_brier: 0.2, calibration_slope: 1,
      windows: 5, base_rate: 0.25,
    },
    countries: Object.fromEntries(
      Object.entries(ps).map(([c, p]) => [
        c,
        { p, fatalities: 10, events: 20, threshold: 5, ratio: 2, centroid: null },
      ]),
    ),
  };
}

function link(themes: Partial<Record<ThemeId, Partial<Link["themes"][ThemeId]>>>): Link {
  const full: Link["themes"] = {};
  for (const [k, v] of Object.entries(themes)) {
    full[k as ThemeId] = {
      intercept: 0, slope: 1, se: 0.1, tstat: 10, pvalue: 0,
      r2: 0.2, n: 80, mean_frac: 0.25, significant: true,
      ...(v as object),
    } as Link["themes"][ThemeId];
  }
  return { generated_at: "", spec: "", tstat_threshold: 2, themes: full };
}

function sens(pairs: Partial<Sensitivities["pairs"][number]>[]): Sensitivities {
  return {
    generated_at: "", tstat_threshold: 2, fdr_q: 0.1, spec: "", gate: "",
    sample: { start: null, end: null, n_pairs: pairs.length, n_significant: 0 },
    current_shock: {},
    pairs: pairs.map((p) => ({
      ticker: "XLE", theme: "mena" as ThemeId, beta: 0.01, se: 0.002,
      tstat: 5, pvalue: 0, beta_lag: 0, tstat_lag: 0, r2: 0.3, n: 80,
      controlled: true, passes_tstat: true, passes_fdr: true, significant: true,
      ...p,
    })),
  };
}

test("expected fraction is the mean probability over covered members", () => {
  const f = forecast({ Iran: 0.8, Iraq: 0.4, "Saudi Arabia": 0.0 });
  const tf = themeForecast(f, link({ mena: {} }), "mena", ALL);
  expect(tf.covered).toBe(3);
  expect(tf.expectedFraction).toBeCloseTo(0.4, 10);
});

test("countries missing from the forecast are excluded, not treated as zero", () => {
  const withAll = themeForecast(
    forecast({ Iran: 0.9, Iraq: 0.9, "Saudi Arabia": 0.9 }),
    link({ mena: {} }), "mena", ALL,
  );
  const withOne = themeForecast(
    forecast({ Iran: 0.9 }), link({ mena: {} }), "mena", ALL,
  );
  // Dropping members must not dilute the mean toward zero.
  expect(withOne.expectedFraction).toBeCloseTo(withAll.expectedFraction, 10);
  expect(withOne.covered).toBe(1);
});

test("expected shock applies intercept and slope", () => {
  const tf = themeForecast(
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ mena: { intercept: -0.2, slope: 3 } }),
    "mena", ALL,
  );
  expect(tf.expectedShock).toBeCloseTo(-0.2 + 3 * 0.5, 10);
});

test("an insignificant link breaks the chain and yields no number", () => {
  const im = chainTheme(
    [{ ticker: "XLE", weight: 1 }], "mena",
    buildLookup(sens([{}])),
    forecast({ Iran: 0.6 }),
    link({ mena: { significant: false, tstat: 1.1 } }),
    ALL,
  );
  expect(im.empty).toBe(true);
  expect(im.holdings[0].blockedAt).toBe("link");
  expect(im.holdings[0].expectedReturn).toBeUndefined();
});

test("an insignificant sensitivity breaks the chain even when the link holds", () => {
  const im = chainTheme(
    [{ ticker: "XLE", weight: 1 }], "mena",
    buildLookup(sens([{ significant: false, tstat: 1.2 }])),
    forecast({ Iran: 0.6 }),
    link({ mena: {} }),
    ALL,
  );
  expect(im.empty).toBe(true);
  expect(im.holdings[0].blockedAt).toBe("sensitivity");
});

test("expected return is beta times expected shock", () => {
  const im = chainTheme(
    [{ ticker: "XLE", weight: 1 }], "mena",
    buildLookup(sens([{ beta: 0.02 }])),
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ mena: { intercept: 0, slope: 2 } }),
    ALL,
  );
  // shock = 0 + 2 * 0.5 = 1.0 sigma; return = 0.02 * 1.0
  expect(im.expectedReturn).toBeCloseTo(0.02, 10);
});

test("sign is preserved: a negative beta gives a negative expected return", () => {
  const im = chainTheme(
    [{ ticker: "VOO", weight: 1 }], "mena",
    buildLookup(sens([{ ticker: "VOO", beta: -0.015 }])),
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ mena: { intercept: 0, slope: 2 } }),
    ALL,
  );
  expect(im.expectedReturn).toBeLessThan(0);
  expect(im.expectedReturn).toBeCloseTo(-0.015, 10);
});

test("weights are renormalised before contributions are summed", () => {
  const lookup = buildLookup(
    sens([{ ticker: "XLE", beta: 0.02 }, { ticker: "USO", beta: 0.04 }]),
  );
  const im = chainTheme(
    [{ ticker: "XLE", weight: 30 }, { ticker: "USO", weight: 10 }],
    "mena", lookup,
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ mena: { intercept: 0, slope: 2 } }),
    ALL,
  );
  // 0.75 * 0.02 + 0.25 * 0.04 = 0.025, regardless of the raw weights summing to 40
  expect(im.expectedReturn).toBeCloseTo(0.025, 10);
  expect(im.coverage).toBeCloseTo(1, 10);
});

test("chained error is larger than either layer's error alone", () => {
  const im = chainTheme(
    [{ ticker: "XLE", weight: 1 }], "mena",
    buildLookup(sens([{ beta: 0.02, se: 0.005 }])),
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ mena: { intercept: 0, slope: 2, se: 0.5 } }),
    ALL,
  );
  const shockSe = 0.5 * 0.5; // se * expectedFraction
  const betaOnly = 0.005 * 1.0;
  expect(im.se).toBeGreaterThan(betaOnly);
  expect(im.se).toBeCloseTo(Math.sqrt(1 * 0.005 ** 2 + 0.02 ** 2 * shockSe ** 2), 10);
});

test("the global theme is excluded from the portfolio total", () => {
  const lookup = buildLookup(
    sens([
      { ticker: "XLE", theme: "mena", beta: 0.02 },
      { ticker: "XLE", theme: "global", beta: 0.09 },
    ]),
  );
  const impacts = chainAll(
    [{ ticker: "XLE", weight: 1 }],
    ["mena", "global"], lookup,
    forecast({ Iran: 0.5, Iraq: 0.5, Ukraine: 0.5, Russia: 0.5, "Saudi Arabia": 0.5 }),
    link({ mena: { intercept: 0, slope: 2 }, global: { intercept: 0, slope: 2 } }),
    ALL,
  );
  const total = chainedTotal(impacts);
  expect(total.themesCounted).toBe(1);
  expect(total.value).toBeCloseTo(0.02, 10); // global's 0.09 must not appear
});

test("an empty portfolio produces no numbers rather than zeroes", () => {
  const im = chainTheme(
    [], "mena", buildLookup(sens([{}])),
    forecast({ Iran: 0.5 }), link({ mena: {} }), ALL,
  );
  expect(im.holdings).toHaveLength(0);
  expect(im.empty).toBe(true);
});

test("risk ranking is descending and respects the limit", () => {
  const r = rankedRisk(forecast({ Iran: 0.1, Iraq: 0.9, Russia: 0.5 }), 2);
  expect(r).toHaveLength(2);
  expect(r[0].country).toBe("Iraq");
  expect(r[1].country).toBe("Russia");
});

/* ------------------------------------------------- holdings-first view */

test("a holding sums across regional themes but never the global one", () => {
  const lookup = buildLookup(
    sens([
      { ticker: "XLE", theme: "mena", beta: 0.02 },
      { ticker: "XLE", theme: "eastern_europe", beta: 0.01 },
      { ticker: "XLE", theme: "global", beta: 0.09 },
    ]),
  );
  const [o] = holdingOutlooks(
    [{ ticker: "XLE", weight: 1 }],
    ["mena", "eastern_europe", "global"],
    lookup,
    forecast({ Iran: 0.5, Iraq: 0.5, Ukraine: 0.5, Russia: 0.5 }),
    link({
      mena: { intercept: 0, slope: 2 },
      eastern_europe: { intercept: 0, slope: 2 },
      global: { intercept: 0, slope: 2 },
    }),
    ALL,
  );
  // shock is 1.0 sigma for each region: 0.02 + 0.01, with global's 0.09 excluded
  expect(o.expected).toBeCloseTo(0.03, 10);
  expect(o.drivers.map((d) => d.theme)).toEqual(["mena", "eastern_europe"]);
});

test("drivers are ordered by absolute contribution, not signed", () => {
  const lookup = buildLookup(
    sens([
      { ticker: "XLE", theme: "mena", beta: 0.005 },
      { ticker: "XLE", theme: "eastern_europe", beta: -0.04 },
    ]),
  );
  const [o] = holdingOutlooks(
    [{ ticker: "XLE", weight: 1 }],
    ["mena", "eastern_europe"],
    lookup,
    forecast({ Iran: 0.5, Iraq: 0.5, Ukraine: 0.5, Russia: 0.5 }),
    link({ mena: { intercept: 0, slope: 2 }, eastern_europe: { intercept: 0, slope: 2 } }),
    ALL,
  );
  expect(o.drivers[0].theme).toBe("eastern_europe");
});

test("a holding with no identified sensitivity is blocked, not zeroed", () => {
  const [o] = holdingOutlooks(
    [{ ticker: "VOO", weight: 1 }],
    ["mena"],
    buildLookup(sens([{ ticker: "VOO", significant: false, tstat: 0.4 }])),
    forecast({ Iran: 0.5 }),
    link({ mena: {} }),
    ALL,
  );
  expect(o.expected).toBeUndefined();
  expect(o.blocked).toBe("no-sensitivity");
});

test("a broken link is reported as such, distinct from a missing sensitivity", () => {
  const [o] = holdingOutlooks(
    [{ ticker: "XLE", weight: 1 }],
    ["mena"],
    buildLookup(sens([{}])),
    forecast({ Iran: 0.5 }),
    link({ mena: { significant: false, tstat: 0.9 } }),
    ALL,
  );
  expect(o.blocked).toBe("no-link");
});

test("portfolio total weights holdings and reports its own coverage", () => {
  const lookup = buildLookup(
    sens([
      { ticker: "XLE", theme: "mena", beta: 0.02 },
      { ticker: "VOO", theme: "mena", significant: false, tstat: 0.3 },
    ]),
  );
  const outlooks = holdingOutlooks(
    [
      { ticker: "XLE", weight: 25 },
      { ticker: "VOO", weight: 75 },
    ],
    ["mena"],
    lookup,
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ mena: { intercept: 0, slope: 2 } }),
    ALL,
  );
  const total = portfolioOutlook(outlooks);
  // only XLE contributes, at its renormalised 25% weight
  expect(total.value).toBeCloseTo(0.25 * 0.02, 10);
  expect(total.measured).toBe(1);
  expect(total.total).toBe(2);
  expect(total.covered).toBeCloseTo(0.25, 10);
});

test("a portfolio with nothing identified reports zero measured, not a zero return", () => {
  const outlooks = holdingOutlooks(
    [{ ticker: "VOO", weight: 1 }],
    ["mena"],
    buildLookup(sens([{ ticker: "VOO", significant: false, tstat: 0.2 }])),
    forecast({ Iran: 0.5 }),
    link({ mena: {} }),
    ALL,
  );
  expect(portfolioOutlook(outlooks).measured).toBe(0);
  expect(outlooks[0].expected).toBeUndefined();
});

/* -------------------------------------------------------------- movers */

function withPrevious(now: Record<string, number>, then: Record<string, number>): Forecast {
  return { ...forecast(now), previous: { as_of_month: "2026-06-01", countries: then } };
}

test("no previous run means no movers, rather than an invented baseline", () => {
  expect(movers(forecast({ Iran: 0.9, Iraq: 0.1 }))).toHaveLength(0);
});

test("movers are ranked by absolute change and respect the limit", () => {
  const f = withPrevious(
    { Iran: 0.90, Iraq: 0.20, Russia: 0.50 },
    { Iran: 0.50, Iraq: 0.60, Russia: 0.48 },
  );
  const m = movers(f, 2);
  expect(m.map((x) => x.country)).toEqual(["Iran", "Iraq"]);
  expect(m[0].delta).toBeCloseTo(0.4, 10);
  expect(m[1].delta).toBeCloseTo(-0.4, 10);
});

test("small wobble is filtered out as model churn", () => {
  const f = withPrevious({ Iran: 0.51 }, { Iran: 0.50 });
  expect(movers(f)).toHaveLength(0);
});

test("a country absent from the previous run is skipped, not treated as zero", () => {
  const f = withPrevious({ Iran: 0.9, Taiwan: 0.8 }, { Iran: 0.85 });
  const m = movers(f, 5, 0.0);
  expect(m.map((x) => x.country)).toEqual(["Iran"]);
});

test("overlay themes are never added into the portfolio total", () => {
  const lookup = buildLookup(
    sens([
      { ticker: "XLE", theme: "mena", beta: 0.02 },
      { ticker: "XLE", theme: "oil_supply", beta: 0.05 },
    ]),
  );
  const [o] = holdingOutlooks(
    [{ ticker: "XLE", weight: 1 }],
    ["mena", "oil_supply"],
    lookup,
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ mena: { intercept: 0, slope: 2 }, oil_supply: { intercept: 0, slope: 2 } }),
    ALL,
  );
  // Iran and Iraq are in both baskets; counting oil_supply too would double them.
  expect(o.expected).toBeCloseTo(0.02, 10);
  expect(o.drivers.map((d) => d.theme)).toEqual(["mena"]);
});

test("the partition is disjoint and covers the universe", () => {
  const seen = new Map<string, number>();
  for (const t of PARTITION_THEMES) {
    for (const c of THEMES[t].countries) seen.set(c, (seen.get(c) ?? 0) + 1);
  }
  const doubled = [...seen.entries()].filter(([, n]) => n > 1);
  expect(doubled).toEqual([]);
  // Overlay members must all appear somewhere in the partition.
  for (const c of THEMES.oil_supply.countries) expect(seen.has(c)).toBe(true);
});

/* ------------------------------------------------------------- data lag */

test("the data lag is measured from the artifacts, not assumed", () => {
  const day = 86_400_000;
  const iso = (msAgo: number) => new Date(Date.now() - msAgo).toISOString().slice(0, 10);

  // A weekly-tier account: recent enough that the banner should stay hidden.
  const fresh = dataLag(iso(9 * day));
  expect(fresh).not.toBeNull();
  expect(fresh!.material).toBe(false);

  // The research tier this project actually runs on: ~12 months behind.
  const lagged = dataLag(iso(364 * day));
  expect(lagged).not.toBeNull();
  expect(lagged!.material).toBe(true);
  expect(lagged!.days).toBeGreaterThanOrEqual(363);
  expect(lagged!.phrase).toBe("about 12 months");

  // Right at the boundary the banner turns on rather than off, because
  // understating staleness is the failure that matters.
  expect(dataLag(iso(45 * day))!.material).toBe(true);
  expect(dataLag(iso(44 * day))!.material).toBe(false);
});

test("a build with no recorded coverage window reports nothing rather than zero", () => {
  // Zero days behind would render as "current", which is the one thing a
  // missing value must never be allowed to claim.
  expect(dataLag(null)).toBeNull();
  expect(dataLag("not a date")).toBeNull();
});
