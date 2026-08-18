"""Layer 2 of the chain: escalation fraction -> theme conflict shock.

    python build_link.py --fixture

Writes public/data/link.json.

The forecaster says how likely each country is to escalate. The sensitivity
model says how each ticker responds to a 1-sigma theme shock. Neither speaks
the other's language, so this is the translator:

    z_T(t+1) = a_T + b_T * frac_esc(T, t) + e

`frac_esc(T,t)` is the share of theme T's countries whose escalation label is
set at month t. Because that label is a statement about month t+1, the shock it
is regressed against is also at t+1. Getting that offset wrong by one month
would let next month's violence predict itself, so the alignment is asserted in
the tests rather than trusted.

At forecast time the realised fraction is unknown, so the model's mean predicted
probability stands in for it. That substitution is only valid if the forecaster
is calibrated, which is why forecast.py computes a calibration slope and writes
it out. A ranking-accurate but badly calibrated forecaster would systematically
bias every number downstream.

This link has its own significance gate. If b_T is not distinguishable from
zero, escalation in that theme tells you nothing about the theme's shock, the
chain is broken there, and the app shows no number for it.
"""

import argparse
import datetime as dt

import numpy as np
import pandas as pd

from aggregate import fill_missing_months
from features import add_rolling_features, add_target
from forecast import load_panel
from intensity import theme_shocks
from ols import ols_hac
from paths import LINK, ensure_dirs, write_json
from universe import THEMES, TSTAT_THRESHOLD

MIN_MONTHS = 36


def escalation_fractions(labelled):
    """Share of each theme's countries with the escalation label set, by month."""
    d = labelled.copy()
    d["year_month"] = pd.to_datetime(d["year_month"])

    out = {}
    for theme_id, meta in THEMES.items():
        members = d[d["country"].isin(meta["countries"])]
        if members.empty:
            continue
        out[theme_id] = members.groupby("year_month")["escalated"].mean()
    return pd.DataFrame(out).sort_index()


def fit_links(panel, labelled):
    shocks = theme_shocks(fill_missing_months(panel))
    fracs = escalation_fractions(labelled)

    links = {}
    for theme_id in THEMES:
        if theme_id not in fracs.columns or theme_id not in shocks.columns:
            continue

        # escalated(t) describes month t+1, so pair it with the shock at t+1.
        y = shocks[theme_id].shift(-1)
        x = fracs[theme_id]

        frame = pd.DataFrame({"y": y, "x": x}).dropna()
        if len(frame) < MIN_MONTHS:
            print(f"  ! {theme_id}: only {len(frame)} months, skipped")
            continue

        fit = ols_hac(frame["y"].to_numpy(), frame[["x"]].to_numpy(), ["x"])
        b = fit.get("x")
        const = fit.get("const")

        links[theme_id] = {
            "intercept": round(const["beta"], 6),
            "slope": round(b["beta"], 6),
            "se": round(b["se"], 6),
            "tstat": round(b["tstat"], 3),
            "pvalue": round(b["pvalue"], 4),
            "r2": round(fit.r2, 4),
            "n": int(fit.nobs),
            "mean_frac": round(float(frame["x"].mean()), 4),
            "significant": bool(abs(b["tstat"]) >= TSTAT_THRESHOLD),
        }

    return links


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--lookahead", type=int, default=1)
    ap.add_argument("--quantile", type=float, default=0.75)
    args = ap.parse_args()

    ensure_dirs()
    panel = load_panel(args.fixture)
    panel["year_month"] = pd.to_datetime(panel["year_month"])

    labelled = add_target(
        add_rolling_features(panel), lookahead=args.lookahead, threshold_quantile=args.quantile
    )

    links = fit_links(panel, labelled)
    ok = sum(1 for v in links.values() if v["significant"])
    print(f"\n{ok} of {len(links)} theme links are significant at |t| >= {TSTAT_THRESHOLD}")
    for theme_id, v in links.items():
        mark = "  " if v["significant"] else " x"
        print(f"{mark} {theme_id:<16} slope={v['slope']:+.3f}  t={v['tstat']:+.2f}  "
              f"r2={v['r2']:.3f}  n={v['n']}")

    write_json(
        LINK,
        {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "spec": "z_T(t+1) = a_T + b_T * frac_escalating(T, t), Newey-West SEs",
            "tstat_threshold": TSTAT_THRESHOLD,
            "themes": links,
        },
        compact=False,
    )


if __name__ == "__main__":
    main()
