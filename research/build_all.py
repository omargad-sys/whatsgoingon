"""Run the whole pipeline and stamp a manifest.

    python build_all.py              # live: needs ACLED credentials
    python build_all.py --fixture    # synthetic, no network, no credentials

This is what the GitHub Action calls. Order matters: the panel feeds the
sensitivities, so a failure part-way leaves data/generated/ internally
consistent rather than half-updated.
"""

import argparse
import datetime as dt
import subprocess
import sys

from paths import (
    COUNTRY_MONTHLY,
    EVENTS_TOP,
    FORECAST,
    LINK,
    RESEARCH_DIR,
    MANIFEST,
    PRICES,
    SENSITIVITIES,
    WORLD_HEAT,
    ensure_dirs,
    read_json,
    write_json,
)


def step(name, argv):
    print(f"\n=== {name} ===")
    result = subprocess.run([sys.executable, *argv], cwd=str(RESEARCH_DIR))
    if result.returncode != 0:
        raise SystemExit(f"{name} failed with exit code {result.returncode}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--skip-panel", action="store_true", help="reuse the existing panel")
    args = ap.parse_args()

    ensure_dirs()
    flag = ["--fixture"] if args.fixture else []

    if args.fixture:
        step("fixtures", ["make_fixtures.py"])

    if not args.skip_panel:
        step("panel", ["build_panel.py", *flag])
    step("snapshot", ["build_snapshot.py", "--days", str(args.days), *flag])
    step("prices", ["build_prices.py", *flag])
    step("sensitivities", ["build_sensitivities.py", *flag])
    step("forecast", ["forecast.py", *flag])
    step("link", ["build_link.py", *flag])
    # Power analysis after the sensitivities it describes. Skipped on fixture
    # builds: measuring the detectable effect size of synthetic data would be a
    # number about the random number generator.
    if not args.fixture:
        step("power", ["power.py", "--write"])
    # Last, so the share card reflects everything above it.
    step("share card", ["build_og.py"])

    heat = read_json(WORLD_HEAT)
    events = read_json(EVENTS_TOP)
    panel = read_json(COUNTRY_MONTHLY)
    sens = read_json(SENSITIVITIES)
    prices = read_json(PRICES)
    fc = read_json(FORECAST)
    lk = read_json(LINK)

    write_json(
        MANIFEST,
        {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "synthetic": bool(args.fixture),
            "window_days": args.days,
            "acled": {
                "weeks": len(heat["weeks"]),
                "first_week": heat["weeks"][0] if heat["weeks"] else None,
                "last_week": heat["weeks"][-1] if heat["weeks"] else None,
                "grid_cells": len(heat["cells"]),
                "detail_events": len(events["features"]),
                "panel_months": len(panel["months"]),
                "panel_countries": len(panel["countries"]),
            },
            "prices": {
                "tickers": sorted(prices["tickers"].keys()),
                "first_date": prices["dates"][0] if prices["dates"] else None,
                "last_date": prices["dates"][-1] if prices["dates"] else None,
            },
            "forecast": {
                "as_of_month": fc["as_of_month"],
                "target_month": fc["target_month"],
                "source": fc["source"],
                "backend": fc["backend"],
                "model_roc_auc": fc["evaluation"]["model_roc_auc"],
                "baseline_roc_auc": fc["evaluation"]["baseline_roc_auc"],
                "countries": len(fc["countries"]),
            },
            "link": {
                "themes": len(lk["themes"]),
                "significant": sum(1 for v in lk["themes"].values() if v["significant"]),
            },
            "model": {
                "pairs": len(sens["pairs"]),
                "significant": sens["sample"]["n_significant"],
                "tstat_threshold": sens["tstat_threshold"],
                "fdr_q": sens["fdr_q"],
            },
        },
        compact=False,
    )
    print("\nDone.")


if __name__ == "__main__":
    main()
