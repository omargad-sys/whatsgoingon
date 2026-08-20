"""How large would a conflict effect have to be for this design to see it?

    cd research && python power.py
    cd research && python power.py --data-dir /path/to/public/data

On real data, zero of 80 ticker-theme pairs cleared the significance gates.
That is either a finding about markets or a finding about the test, and those
are very different claims. Reporting the first when the truth is the second is
the most consequential mistake this project could make, because "conflict does
not move ETFs" sounds like a result while "my sample is too small to tell"
sounds like an excuse, and only one of them is honest.

Method: take the real fitted model for each pair, plant an effect of known
size, resample the real residuals in blocks so their volatility and
autocorrelation survive, rebuild the return series, and push it back through
the exact same regression and the exact same two gates. Repeat, and count how
often the planted effect is found. That is power, measured on the real design
rather than assumed from a textbook formula.

Two numbers come out of it:

  MDE     the minimum effect, in basis points of monthly return per 1-sigma
          conflict shock, that this design detects 80% of the time.
  power   the detection rate at effect sizes that are actually plausible.

Residual block bootstrap rather than normal draws, because monthly ETF returns
are fat-tailed and serially dependent, and Newey-West standard errors are
precisely the thing that responds to that. Simulating clean Gaussian noise
would flatter the design.
"""

import argparse
import json
import pathlib

import numpy as np
import pandas as pd

from aggregate import fill_missing_months
from build_sensitivities import MIN_MONTHS, benjamini_hochberg, FDR_Q
from intensity import theme_shocks
from ols import ols_hac
from paths import GENERATED_DIR, write_json
from universe import BROAD_TICKERS, THEMES, TICKERS, TSTAT_THRESHOLD

# Published reference points for how large a real geopolitical-risk effect on
# equities actually is, so the power numbers can be read against something
# rather than judged by feel. Source: IMF Global Financial Stability Report,
# April 2025, chapter 2 annex.
REFERENCE_EFFECTS = [
    {"label": "Average country-specific geopolitical risk shock", "bps": 30},
    {"label": "Firm-level, major event in home country (monthly)", "bps": 70},
    {"label": "Firm-level, major event, excess USD terms", "bps": 100},
    {"label": "Large country-specific shock", "bps": 200},
]

# Effect sizes to sweep, in basis points of monthly return per 1-sigma shock.
# Includes the published reference magnitudes (30, 70, 100, 200 bps) so power
# at a plausible effect size is measured rather than eyeballed off a curve.
GRID_BPS = [0, 10, 25, 30, 50, 70, 100, 150, 200, 300, 400, 600, 800]

# Where a real effect would plausibly live. Broad index funds are deliberately
# excluded: the whole premise of the project is that they barely respond, so
# planting an effect in VOO would measure a scenario nobody believes.
PLANTED = [
    ("XLE", "mena"), ("XLE", "oil_supply"),
    ("USO", "mena"), ("USO", "oil_supply"),
    ("GLD", "mena"), ("GLD", "eastern_europe"),
    ("VIXY", "mena"), ("VIXY", "eastern_europe"),
    ("ITA", "eastern_europe"), ("XAR", "eastern_europe"),
]

BLOCK = 3       # months per bootstrap block
REPLICATIONS = 300


def load(data_dir):
    blob = json.loads((data_dir / "country-monthly.json").read_text())
    months = blob["months"]
    rows = []
    for country, series in blob["countries"].items():
        for i, m in enumerate(months):
            rows.append({
                "country": country,
                "year_month": m,
                "num_events": series["events"][i],
                "total_fatalities": series["fatalities"][i],
                "battles": series["battles"][i],
                "protests": series["protests"][i],
                "violence_civilians": series["violence_civilians"][i],
            })
    panel = pd.DataFrame(rows)

    prices = json.loads((data_dir / "prices.json").read_text())
    wide = pd.DataFrame(prices["tickers"], index=pd.to_datetime(prices["dates"]))
    returns = wide.resample("MS").last().pct_change(fill_method=None)
    return panel, returns


def design_matrices(panel, returns):
    """The exact frames build_sensitivities.py fits, one per (ticker, theme)."""
    shocks = theme_shocks(fill_missing_months(panel))
    idx = shocks.index.intersection(returns.index)
    shocks, returns = shocks.loc[idx], returns.loc[idx]

    out = {}
    for ticker in TICKERS:
        if ticker not in returns.columns:
            continue
        is_broad = ticker in BROAD_TICKERS
        for theme_id in THEMES:
            z = shocks[theme_id]
            frame = pd.DataFrame({
                "y": returns[ticker],
                "z0": z,
                "z1": z.shift(1),
                "mkt": returns["SPY"] if "SPY" in returns.columns else np.nan,
            }).dropna(subset=["y", "z0", "z1"] + ([] if is_broad else ["mkt"]))
            if len(frame) < MIN_MONTHS:
                continue
            names = ["z0", "z1"] if is_broad else ["z0", "z1", "mkt"]
            out[(ticker, theme_id)] = (frame, names)
    return out


def baseline_fits(designs):
    """Real fit per pair: coefficients to rebuild from, residuals to resample."""
    fits = {}
    for key, (frame, names) in designs.items():
        X = frame[names].to_numpy()
        y = frame["y"].to_numpy()
        fit = ols_hac(y, X, names)
        # ols_hac prepends the constant, so beta[0] is the intercept.
        intercept = float(fit.beta[0])
        beta = np.array([fit.get(n)["beta"] for n in names])
        resid = y - (intercept + X @ beta)
        fits[key] = {
            "names": names, "X": X, "intercept": intercept,
            "beta": beta, "resid": resid, "se0": fit.get("z0")["se"], "n": len(y),
        }
    return fits


def block_resample(resid, rng, block=BLOCK):
    """Circular block bootstrap: keeps volatility clustering and serial
    dependence, which is what Newey-West is there to handle."""
    n = len(resid)
    starts = rng.integers(0, n, size=int(np.ceil(n / block)))
    return np.concatenate([np.take(resid, range(s, s + block), mode="wrap") for s in starts])[:n]


def simulate(fits, planted_bps, rng):
    """One replication. Returns (detected_by_t, detected_by_both) for planted pairs."""
    pairs = []
    for key, f in fits.items():
        names, X = f["names"], f["X"]
        # Rebuild y from the real fit, but with z0's coefficient replaced by the
        # planted effect for the pairs that are supposed to have one, and by
        # zero everywhere else so the null pairs are genuinely null.
        beta = f["beta"].copy()
        beta[names.index("z0")] = (planted_bps / 10000.0) if key in PLANTED else 0.0
        y = f["intercept"] + X @ beta + block_resample(f["resid"], rng)

        fit = ols_hac(y, X, names)
        b0 = fit.get("z0")
        pairs.append({
            "key": key,
            "tstat": b0["tstat"],
            "pvalue": b0["pvalue"],
            "passes_tstat": abs(b0["tstat"]) >= TSTAT_THRESHOLD,
        })

    keep = benjamini_hochberg([p["pvalue"] for p in pairs])
    by_t, by_both = {}, {}
    for p, k in zip(pairs, keep):
        if p["key"] in PLANTED:
            by_t[p["key"]] = p["passes_tstat"]
            by_both[p["key"]] = bool(p["passes_tstat"] and k)
    return by_t, by_both


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--reps", type=int, default=REPLICATIONS)
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--write", action="store_true", help="emit public/data/power.json")
    args = ap.parse_args()

    data_dir = pathlib.Path(args.data_dir) if args.data_dir else (
        pathlib.Path(__file__).resolve().parent.parent / "public" / "data"
    )

    panel, returns = load(data_dir)
    designs = design_matrices(panel, returns)
    fits = baseline_fits(designs)

    n_months = fits[next(iter(fits))]["n"]
    print(f"{len(fits)} pairs, {n_months} months each, {len(PLANTED)} pairs carry a planted effect")
    print(f"{args.reps} replications per effect size, block bootstrap (block={BLOCK})")
    print(f"Gates: |t| >= {TSTAT_THRESHOLD} AND Benjamini-Hochberg at q={FDR_Q} across all {len(fits)}\n")

    rng = np.random.default_rng(args.seed)
    rows = []
    for bps in GRID_BPS:
        t_hits, both_hits, total = 0, 0, 0
        for _ in range(args.reps):
            by_t, by_both = simulate(fits, bps, rng)
            t_hits += sum(by_t.values())
            both_hits += sum(by_both.values())
            total += len(by_t)
        rows.append({
            "effect_bps": bps,
            "power_tstat": t_hits / total,
            "power_both": both_hits / total,
        })
        label = "false positive rate" if bps == 0 else "power"
        print(f"  {bps:>4} bps/sigma   |t| gate {t_hits/total:6.1%}   both gates {both_hits/total:6.1%}   ({label})")

    df = pd.DataFrame(rows)

    print("\nMinimum detectable effect (80% power), by gate:")
    for col, label in [("power_tstat", "|t| >= 2 alone"), ("power_both", "|t| >= 2 AND FDR")]:
        hit = df[df[col] >= 0.80]
        if len(hit):
            print(f"  {label:<20} {hit.effect_bps.iloc[0]:>4} bps per 1-sigma shock")
        else:
            print(f"  {label:<20} not reached even at {GRID_BPS[-1]} bps")

    print("\nPer-ticker back-of-envelope, from the real standard errors:")
    print("  (effect needed for 80% power at the FDR-adjusted threshold)")
    crit = 3.35   # two-sided z for p = q/n = 0.10/80 = 0.00125
    per_ticker = {}
    for (ticker, _theme), f in fits.items():
        per_ticker.setdefault(ticker, []).append(f["se0"])
    for ticker, ses in sorted(per_ticker.items(), key=lambda kv: np.median(kv[1])):
        need = (crit + 0.84) * float(np.median(ses))
        print(f"  {ticker:<5} {need * 100:6.2f}% monthly return per 1-sigma conflict shock")

    if args.write:
        def mde(col):
            hit = df[df[col] >= 0.80]
            return int(hit.effect_bps.iloc[0]) if len(hit) else None

        def power_at(bps):
            row = df[df.effect_bps == bps]
            return float(row.power_both.iloc[0]) if len(row) else None

        write_json(GENERATED_DIR / "power.json", {
            "n_months": int(n_months),
            "n_pairs": len(fits),
            "n_planted": len(PLANTED),
            "replications": int(args.reps),
            "tstat_threshold": float(TSTAT_THRESHOLD),
            "fdr_q": float(FDR_Q),
            "false_positive_rate": float(df[df.effect_bps == 0].power_both.iloc[0]),
            "mde_tstat_bps": mde("power_tstat"),
            "mde_both_bps": mde("power_both"),
            "curve": [
                {"bps": int(r.effect_bps), "power_tstat": round(float(r.power_tstat), 4),
                 "power_both": round(float(r.power_both), 4)}
                for r in df.itertuples()
            ],
            "reference_effects": [
                {**ref, "power": power_at(ref["bps"])} for ref in REFERENCE_EFFECTS
            ],
            "reference_source": (
                "IMF Global Financial Stability Report, April 2025, chapter 2 annex"
            ),
        })
        print(f"\n  wrote {GENERATED_DIR / 'power.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
