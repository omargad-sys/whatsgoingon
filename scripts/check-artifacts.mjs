#!/usr/bin/env node
/**
 * Validate everything in public/data/ before it can reach the map.
 *
 *   node scripts/check-artifacts.mjs
 *
 * This runs in CI immediately after the Python build and again in `prebuild`,
 * so a bad refresh fails the workflow instead of shipping a blank world.
 * Node builtins only, no dependencies.
 */

import { readFileSync, existsSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dir = join(root, "public", "data");

const errors = [];
const warnings = [];

const fail = (m) => errors.push(m);
const warn = (m) => warnings.push(m);

function load(name) {
  const path = join(dir, name);
  if (!existsSync(path)) {
    fail(`${name}: missing`);
    return null;
  }
  try {
    const raw = readFileSync(path, "utf8");
    const kb = statSync(path).size / 1024;
    if (kb > 8192) warn(`${name}: ${kb.toFixed(0)} KB is large for a static asset`);
    return JSON.parse(raw);
  } catch (err) {
    fail(`${name}: not valid JSON (${err.message})`);
    return null;
  }
}

const isFiniteNum = (v) => typeof v === "number" && Number.isFinite(v);

/* ---------------------------------------------------------------- manifest */
const manifest = load("manifest.json");
if (manifest) {
  if (!manifest.generated_at) fail("manifest.json: no generated_at");
  else {
    const ageDays = (Date.now() - Date.parse(manifest.generated_at)) / 86_400_000;
    if (Number.isNaN(ageDays)) fail("manifest.json: generated_at is not a date");
    else if (ageDays > 45) warn(`manifest.json: data is ${ageDays.toFixed(0)} days old`);
  }
  if (manifest.synthetic) {
    warn("manifest.json: synthetic=true. Fine for local dev, wrong for production.");
  }
}

/* -------------------------------------------------------------- world heat */
const heat = load("world-heat.json");
if (heat) {
  if (!Array.isArray(heat.weeks) || heat.weeks.length === 0) fail("world-heat: no weeks");
  if (!Array.isArray(heat.cells) || heat.cells.length === 0) fail("world-heat: no cells");
  if (!isFiniteNum(heat.cell_size)) fail("world-heat: cell_size must be a number");

  const nWeeks = heat.weeks?.length ?? 0;
  let bad = 0;
  let totalEvents = 0;
  for (const cell of heat.cells ?? []) {
    if (!Array.isArray(cell) || cell.length !== 5) { bad++; continue; }
    const [w, lon, lat, events, fatalities] = cell;
    if (!Number.isInteger(w) || w < 0 || w >= nWeeks) { bad++; continue; }
    if (!isFiniteNum(lon) || lon < -180 || lon > 180) { bad++; continue; }
    if (!isFiniteNum(lat) || lat < -90 || lat > 90) { bad++; continue; }
    if (!Number.isInteger(events) || events < 0) { bad++; continue; }
    if (!Number.isInteger(fatalities) || fatalities < 0) { bad++; continue; }
    totalEvents += events;
  }
  if (bad > 0) fail(`world-heat: ${bad} malformed cells`);
  if (totalEvents === 0) fail("world-heat: zero total events");

  const sorted = [...(heat.weeks ?? [])].sort();
  if (JSON.stringify(sorted) !== JSON.stringify(heat.weeks)) {
    fail("world-heat: weeks are not in ascending order");
  }
}

/* ------------------------------------------------------------- top events */
const events = load("events-top.geojson");
if (events) {
  if (events.type !== "FeatureCollection") fail("events-top: not a FeatureCollection");
  const feats = events.features ?? [];
  if (feats.length === 0) fail("events-top: no features");

  const nWeeks = heat?.weeks?.length ?? Infinity;
  let bad = 0;
  for (const f of feats) {
    const c = f?.geometry?.coordinates;
    if (!Array.isArray(c) || c.length !== 2 || !isFiniteNum(c[0]) || !isFiniteNum(c[1])) { bad++; continue; }
    if (c[0] < -180 || c[0] > 180 || c[1] < -90 || c[1] > 90) { bad++; continue; }
    const p = f.properties ?? {};
    if (!Number.isInteger(p.f) || p.f < 0) { bad++; continue; }
    if (!Number.isInteger(p.w) || p.w < 0 || p.w >= nWeeks) { bad++; continue; }
    if (typeof p.d !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(p.d)) { bad++; continue; }
  }
  if (bad > 0) fail(`events-top: ${bad} malformed features`);
}

/* ----------------------------------------------------------------- panel */
const panel = load("country-monthly.json");
if (panel) {
  const months = panel.months ?? [];
  if (months.length < 24) fail(`country-monthly: only ${months.length} months, need 24+`);
  const countries = Object.entries(panel.countries ?? {});
  if (countries.length === 0) fail("country-monthly: no countries");

  for (const [name, series] of countries) {
    for (const key of ["events", "fatalities", "battles", "protests", "violence_civilians"]) {
      const arr = series?.[key];
      if (!Array.isArray(arr)) { fail(`country-monthly: ${name}.${key} missing`); continue; }
      if (arr.length !== months.length) {
        fail(`country-monthly: ${name}.${key} has ${arr.length} values, expected ${months.length}`);
      }
      if (arr.some((v) => !Number.isInteger(v) || v < 0)) {
        fail(`country-monthly: ${name}.${key} has negative or non-integer values`);
      }
    }
  }
}

/* ---------------------------------------------------------------- prices */
const prices = load("prices.json");
if (prices) {
  const dates = prices.dates ?? [];
  if (dates.length < 400) fail(`prices: only ${dates.length} days, need 400+`);
  for (const [ticker, series] of Object.entries(prices.tickers ?? {})) {
    if (!Array.isArray(series) || series.length !== dates.length) {
      fail(`prices: ${ticker} length ${series?.length} != ${dates.length}`);
      continue;
    }
    const observed = series.filter((v) => v !== null);
    if (observed.length < 400) fail(`prices: ${ticker} has only ${observed.length} observations`);
    if (observed.some((v) => !isFiniteNum(v) || v <= 0)) {
      fail(`prices: ${ticker} contains non-positive or non-finite closes`);
    }
    // A real ETF does not move 60% in a day. This catches a provider handing
    // back a split-unadjusted series, which would silently poison the betas.
    for (let i = 1; i < series.length; i++) {
      const a = series[i - 1];
      const b = series[i];
      if (a && b && Math.abs(b / a - 1) > 0.6) {
        warn(`prices: ${ticker} jumps ${(100 * (b / a - 1)).toFixed(0)}% on ${dates[i]}`);
        break;
      }
    }
  }
}

/* --------------------------------------------------------- sensitivities */
const sens = load("sensitivities.json");
if (sens) {
  if (!isFiniteNum(sens.tstat_threshold)) fail("sensitivities: no tstat_threshold");
  const pairs = sens.pairs ?? [];
  if (pairs.length === 0) fail("sensitivities: no pairs");

  const priceTickers = new Set(Object.keys(prices?.tickers ?? {}));
  for (const p of pairs) {
    for (const k of ["beta", "se", "tstat", "pvalue", "r2"]) {
      if (!isFiniteNum(p[k])) fail(`sensitivities: ${p.ticker}/${p.theme} has non-finite ${k}`);
    }
    if (typeof p.significant !== "boolean") {
      fail(`sensitivities: ${p.ticker}/${p.theme} missing significant flag`);
    }
    // The whole credibility of the app rests on this invariant: nothing may be
    // marked significant unless it clears the |t| gate.
    if (p.significant && Math.abs(p.tstat) < sens.tstat_threshold) {
      fail(`sensitivities: ${p.ticker}/${p.theme} marked significant at |t|=${Math.abs(p.tstat)}`);
    }
    if (p.significant && p.passes_fdr === false) {
      fail(`sensitivities: ${p.ticker}/${p.theme} marked significant but failed FDR`);
    }
    if (p.n < 24) fail(`sensitivities: ${p.ticker}/${p.theme} fit on only ${p.n} months`);
    if (priceTickers.size && !priceTickers.has(p.ticker)) {
      fail(`sensitivities: ${p.ticker} has no price series`);
    }
  }

  const sig = pairs.filter((p) => p.significant).length;
  if (sig === 0) warn("sensitivities: nothing is significant. The overlay will be entirely empty.");
  if (sig / pairs.length > 0.5) {
    warn(`sensitivities: ${sig}/${pairs.length} pairs significant. Suspiciously many; check the SEs.`);
  }
}


/* --------------------------------------------------------------- forecast */
const fc = load("forecast.json");
if (fc) {
  if (!["model", "baseline"].includes(fc.source)) {
    fail(`forecast: source must be "model" or "baseline", got ${JSON.stringify(fc.source)}`);
  }
  const entries = Object.entries(fc.countries ?? {});
  if (entries.length === 0) fail("forecast: no countries");
  for (const [name, v] of entries) {
    if (!isFiniteNum(v.p) || v.p < 0 || v.p > 1) {
      fail(`forecast: ${name} has probability ${v.p}, must be in [0,1]`);
    }
    if (v.centroid && (Math.abs(v.centroid[0]) > 180 || Math.abs(v.centroid[1]) > 90)) {
      fail(`forecast: ${name} has an out-of-range centroid`);
    }
  }
  const ev = fc.evaluation ?? {};
  // The gate that keeps a losing model from shipping as if it had won.
  if (fc.source === "model" && ev.margin < 0.02) {
    fail(`forecast: shipping the model at a margin of ${ev.margin}, below the 0.02 gate`);
  }
  if (fc.source === "baseline" && ev.margin >= 0.02) {
    warn(`forecast: model beat the baseline by ${ev.margin} but the baseline is being used`);
  }
  if (ev.calibration_slope !== null && isFiniteNum(ev.calibration_slope)) {
    if (ev.calibration_slope < 0.5 || ev.calibration_slope > 1.6) {
      warn(
        `forecast: calibration slope ${ev.calibration_slope} is far from 1. ` +
          "Expected-shock estimates downstream will be biased.",
      );
    }
  }
  if (Date.parse(fc.target_month) <= Date.parse(fc.as_of_month)) {
    fail("forecast: target_month must be after as_of_month");
  }
}

/* ------------------------------------------------------------------- link */
const lk = load("link.json");
if (lk) {
  const themes = Object.entries(lk.themes ?? {});
  if (themes.length === 0) fail("link: no themes");
  for (const [name, v] of themes) {
    for (const k of ["intercept", "slope", "se", "tstat", "r2"]) {
      if (!isFiniteNum(v[k])) fail(`link: ${name} has non-finite ${k}`);
    }
    if (v.significant && Math.abs(v.tstat) < lk.tstat_threshold) {
      fail(`link: ${name} marked significant at |t|=${Math.abs(v.tstat)}`);
    }
    if (v.n < 24) fail(`link: ${name} fit on only ${v.n} months`);
  }
  if (themes.every(([, v]) => !v.significant)) {
    warn("link: no theme link is significant. The chained overlay will be entirely empty.");
  }
}

/* ---------------------------------------------------------------- report */
for (const w of warnings) console.warn(`warn  ${w}`);
for (const e of errors) console.error(`FAIL  ${e}`);

if (errors.length) {
  console.error(`\n${errors.length} error(s) in ${relative(root, dir)}`);
  process.exit(1);
}
console.log(`OK  ${relative(root, dir)} passed ${warnings.length ? `with ${warnings.length} warning(s)` : "clean"}`);
