"""Estimate how each ticker responds to a 1-sigma conflict shock, per theme.

    python build_sensitivities.py            # uses data/generated/
    python build_sensitivities.py --fixture  # uses research/fixtures/

Specification, per (ticker, theme):

    r_k(t) = a + b0 * z_T(t) + b1 * z_T(t-1) [ + c * r_SPY(t) ] + e(t)

r is the simple monthly return. z_T is the rolling-z-scored conflict shock from
intensity.py. The SPY control is included for every non-broad ticker so that
`b0` measures the conflict response net of "the whole market moved", which is
the only version of the number that means anything for a portfolio decision.
Standard errors are Newey-West.

The headline number the app shows is b0: the expected same-month return impact
of a 1-sigma escalation. Anything with |t| < 2 is written out with
significant=false and the front end refuses to render a number for it.
"""

import argparse
import datetime as dt

import numpy as np
import pandas as pd

from aggregate import fill_missing_months
from intensity import theme_shocks
from ols import ols_hac
from paths import (
    COUNTRY_MONTHLY,
    FIXTURE_DIR,
    PRICES,
    SENSITIVITIES,
    ensure_dirs,
    read_json,
    write_json,
)
from universe import BROAD_TICKERS, THEMES, TICKERS, TSTAT_THRESHOLD

MIN_MONTHS = 48

# 10 tickers x 5 themes = 50 hypothesis tests. At a naive 5% level you expect
# 2-3 "significant" results from pure noise, and on the synthetic fixture that is
# exactly what happens: VOO clears |t| > 2 on a theme whose true beta is zero.
# Benjamini-Hochberg controls the false discovery rate across the whole family,
# so a pair has to survive both the |t| gate and the FDR gate to print a number.
FDR_Q = 0.10


def benjamini_hochberg(pvalues, q=FDR_Q):
    """Return a boolean mask of discoveries controlling FDR at level q."""
    p = np.asarray(pvalues, dtype=float)
    n = len(p)
    if n == 0:
        return np.zeros(0, dtype=bool)

    order = np.argsort(p)
    ranked = p[order]
    thresholds = q * (np.arange(1, n + 1) / n)
    passed = ranked <= thresholds

    keep = np.zeros(n, dtype=bool)
    if passed.any():
        cutoff = np.max(np.where(passed)[0])
        keep[order[: cutoff + 1]] = True
    return keep


def load_panel(fixture):
    if fixture:
        return pd.read_csv(FIXTURE_DIR / "panel_sample.csv")

    blob = read_json(COUNTRY_MONTHLY)
    months = blob["months"]
    rows = []
    for country, series in blob["countries"].items():
        for i, m in enumerate(months):
            rows.append(
                {
                    "country": country,
                    "year_month": m,
                    "num_events": series["events"][i],
                    "total_fatalities": series["fatalities"][i],
                    "battles": series["battles"][i],
                    "protests": series["protests"][i],
                    "violence_civilians": series["violence_civilians"][i],
                }
            )
    return pd.DataFrame(rows)


def load_monthly_returns(fixture):
    if fixture:
        raw = pd.read_csv(FIXTURE_DIR / "prices_sample.csv")
        raw["date"] = pd.to_datetime(raw["date"])
        wide = raw.pivot(index="date", columns="ticker", values="close")
    else:
        blob = read_json(PRICES)
        wide = pd.DataFrame(blob["tickers"], index=pd.to_datetime(blob["dates"]))

    # Last observed close in each calendar month.
    monthly = wide.resample("MS").last()
    return monthly.pct_change(fill_method=None)


def run(panel, returns):
    shocks = theme_shocks(fill_missing_months(panel))

    idx = shocks.index.intersection(returns.index)
    shocks = shocks.loc[idx]
    returns = returns.loc[idx]

    pairs = []
    for ticker in TICKERS:
        if ticker not in returns.columns:
            print(f"  ! {ticker} missing from price data, skipped")
            continue
        is_broad = ticker in BROAD_TICKERS

        for theme_id in THEMES:
            z = shocks[theme_id]
            frame = pd.DataFrame(
                {
                    "y": returns[ticker],
                    "z0": z,
                    "z1": z.shift(1),
                    "mkt": returns["SPY"] if "SPY" in returns.columns else np.nan,
                }
            ).dropna(subset=["y", "z0", "z1"] + ([] if is_broad else ["mkt"]))

            if len(frame) < MIN_MONTHS:
                print(f"  ! {ticker}/{theme_id}: only {len(frame)} months, skipped")
                continue

            names = ["z0", "z1"] if is_broad else ["z0", "z1", "mkt"]
            fit = ols_hac(frame["y"].to_numpy(), frame[names].to_numpy(), names)

            b0 = fit.get("z0")
            b1 = fit.get("z1")

            pairs.append(
                {
                    "ticker": ticker,
                    "theme": theme_id,
                    "beta": round(b0["beta"], 6),
                    "se": round(b0["se"], 6),
                    "tstat": round(b0["tstat"], 3),
                    "pvalue": round(b0["pvalue"], 4),
                    "beta_lag": round(b1["beta"], 6),
                    "tstat_lag": round(b1["tstat"], 3),
                    "r2": round(fit.r2, 4),
                    "n": int(fit.nobs),
                    "controlled": not is_broad,
                    "passes_tstat": bool(abs(b0["tstat"]) >= TSTAT_THRESHOLD),
                }
            )

    # Family-wide FDR control, applied once across every ticker-theme pair.
    discoveries = benjamini_hochberg([p["pvalue"] for p in pairs])
    for pair, keep in zip(pairs, discoveries):
        pair["passes_fdr"] = bool(keep)
        pair["significant"] = bool(pair["passes_tstat"] and keep)

    return pairs, shocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--print", dest="show", action="store_true", help="print the table")
    args = ap.parse_args()

    ensure_dirs()
    panel = load_panel(args.fixture)
    returns = load_monthly_returns(args.fixture)

    pairs, shocks = run(panel, returns)

    latest = shocks.dropna(how="all")
    current = {} if latest.empty else {
        k: (None if pd.isna(v) else round(float(v), 3))
        for k, v in latest.iloc[-1].items()
    }

    sig = sum(1 for p in pairs if p["significant"])
    raw = sum(1 for p in pairs if p["passes_tstat"])
    print(
        f"\n{raw} of {len(pairs)} pairs clear |t| >= {TSTAT_THRESHOLD}; "
        f"{sig} survive Benjamini-Hochberg at q={FDR_Q}"
    )

    if args.show:
        df = pd.DataFrame(pairs)
        cols = ["ticker", "theme", "beta", "tstat", "pvalue", "r2", "n", "passes_tstat", "significant"]
        with pd.option_context("display.width", 180, "display.max_rows", 200):
            print(df[cols].to_string(index=False))

    write_json(
        SENSITIVITIES,
        {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "tstat_threshold": TSTAT_THRESHOLD,
            "fdr_q": FDR_Q,
            "spec": "r_k(t) = a + b0*z_T(t) + b1*z_T(t-1) [+ c*r_SPY(t)], Newey-West SEs",
            "gate": "significant = |t(b0)| >= tstat_threshold AND survives Benjamini-Hochberg at fdr_q",
            "sample": {
                "start": str(shocks.dropna(how="all").index.min().date()) if len(shocks.dropna(how="all")) else None,
                "end": str(shocks.dropna(how="all").index.max().date()) if len(shocks.dropna(how="all")) else None,
                "n_pairs": len(pairs),
                "n_significant": sig,
            },
            "current_shock": current,
            "pairs": pairs,
        },
        compact=False,
    )


if __name__ == "__main__":
    main()
