/**
 * Chain math tests.
 *
 *   bun test lib/chain.test.ts
 *
 * Uses bun's built-in runner so it needs no dependency install. If you'd rather
 * use vitest later, the assertions are plain and will port unchanged.
 */

import { expect, test } from "bun:test";

import { chainAll, chainTheme, chainedTotal, rankedRisk, themeForecast } from "./chain";
import { buildLookup } from "./exposure";
import type { Forecast, Link, Sensitivities, ThemeId } from "./types";

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
      ticker: "XLE", theme: "oil_supply" as ThemeId, beta: 0.01, se: 0.002,
      tstat: 5, pvalue: 0, beta_lag: 0, tstat_lag: 0, r2: 0.3, n: 80,
      controlled: true, passes_tstat: true, passes_fdr: true, significant: true,
      ...p,
    })),
  };
}

test("expected fraction is the mean probability over covered members", () => {
  const f = forecast({ Iran: 0.8, Iraq: 0.4, "Saudi Arabia": 0.0 });
  const tf = themeForecast(f, link({ oil_supply: {} }), "oil_supply", ALL);
  expect(tf.covered).toBe(3);
  expect(tf.expectedFraction).toBeCloseTo(0.4, 10);
});

test("countries missing from the forecast are excluded, not treated as zero", () => {
  const withAll = themeForecast(
    forecast({ Iran: 0.9, Iraq: 0.9, "Saudi Arabia": 0.9 }),
    link({ oil_supply: {} }), "oil_supply", ALL,
  );
  const withOne = themeForecast(
    forecast({ Iran: 0.9 }), link({ oil_supply: {} }), "oil_supply", ALL,
  );
  // Dropping members must not dilute the mean toward zero.
  expect(withOne.expectedFraction).toBeCloseTo(withAll.expectedFraction, 10);
  expect(withOne.covered).toBe(1);
});

test("expected shock applies intercept and slope", () => {
  const tf = themeForecast(
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ oil_supply: { intercept: -0.2, slope: 3 } }),
    "oil_supply", ALL,
  );
  expect(tf.expectedShock).toBeCloseTo(-0.2 + 3 * 0.5, 10);
});

test("an insignificant link breaks the chain and yields no number", () => {
  const im = chainTheme(
    [{ ticker: "XLE", weight: 1 }], "oil_supply",
    buildLookup(sens([{}])),
    forecast({ Iran: 0.6 }),
    link({ oil_supply: { significant: false, tstat: 1.1 } }),
    ALL,
  );
  expect(im.empty).toBe(true);
  expect(im.holdings[0].blockedAt).toBe("link");
  expect(im.holdings[0].expectedReturn).toBeUndefined();
});

test("an insignificant sensitivity breaks the chain even when the link holds", () => {
  const im = chainTheme(
    [{ ticker: "XLE", weight: 1 }], "oil_supply",
    buildLookup(sens([{ significant: false, tstat: 1.2 }])),
    forecast({ Iran: 0.6 }),
    link({ oil_supply: {} }),
    ALL,
  );
  expect(im.empty).toBe(true);
  expect(im.holdings[0].blockedAt).toBe("sensitivity");
});

test("expected return is beta times expected shock", () => {
  const im = chainTheme(
    [{ ticker: "XLE", weight: 1 }], "oil_supply",
    buildLookup(sens([{ beta: 0.02 }])),
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ oil_supply: { intercept: 0, slope: 2 } }),
    ALL,
  );
  // shock = 0 + 2 * 0.5 = 1.0 sigma; return = 0.02 * 1.0
  expect(im.expectedReturn).toBeCloseTo(0.02, 10);
});

test("sign is preserved: a negative beta gives a negative expected return", () => {
  const im = chainTheme(
    [{ ticker: "VOO", weight: 1 }], "oil_supply",
    buildLookup(sens([{ ticker: "VOO", beta: -0.015 }])),
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ oil_supply: { intercept: 0, slope: 2 } }),
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
    "oil_supply", lookup,
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ oil_supply: { intercept: 0, slope: 2 } }),
    ALL,
  );
  // 0.75 * 0.02 + 0.25 * 0.04 = 0.025, regardless of the raw weights summing to 40
  expect(im.expectedReturn).toBeCloseTo(0.025, 10);
  expect(im.coverage).toBeCloseTo(1, 10);
});

test("chained error is larger than either layer's error alone", () => {
  const im = chainTheme(
    [{ ticker: "XLE", weight: 1 }], "oil_supply",
    buildLookup(sens([{ beta: 0.02, se: 0.005 }])),
    forecast({ Iran: 0.5, Iraq: 0.5 }),
    link({ oil_supply: { intercept: 0, slope: 2, se: 0.5 } }),
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
      { ticker: "XLE", theme: "oil_supply", beta: 0.02 },
      { ticker: "XLE", theme: "global", beta: 0.09 },
    ]),
  );
  const impacts = chainAll(
    [{ ticker: "XLE", weight: 1 }],
    ["oil_supply", "global"], lookup,
    forecast({ Iran: 0.5, Iraq: 0.5, Ukraine: 0.5, Russia: 0.5, "Saudi Arabia": 0.5 }),
    link({ oil_supply: { intercept: 0, slope: 2 }, global: { intercept: 0, slope: 2 } }),
    ALL,
  );
  const total = chainedTotal(impacts);
  expect(total.themesCounted).toBe(1);
  expect(total.value).toBeCloseTo(0.02, 10); // global's 0.09 must not appear
});

test("an empty portfolio produces no numbers rather than zeroes", () => {
  const im = chainTheme(
    [], "oil_supply", buildLookup(sens([{}])),
    forecast({ Iran: 0.5 }), link({ oil_supply: {} }), ALL,
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
