"""Layer 1 of the chain: per-country escalation probability for next month.

    python forecast.py
    python forecast.py --fixture

Writes public/data/forecast.json.

This wraps model.py's forecaster with one rule: it will not ship a model that
fails to beat the persistence baseline. Walk-forward evaluation picks the
better of the two, and whichever wins is recorded in the output as `source`,
so the app and the methodology page can say which one is actually driving the
numbers. Shipping a gradient booster that loses to arithmetic, and not
mentioning it, is the failure mode this guards against.

Calibration matters more than ranking here. The next layer converts these
probabilities into an expected escalation fraction, and a mean of
probabilities is only an unbiased estimate of that fraction if the
probabilities are calibrated. So Brier score and a calibration slope are
computed and written out alongside.
"""

import argparse
import datetime as dt

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from features import FEATURE_COLS, add_rolling_features, add_target
from geo import CENTROIDS
from model import ORIGINS, TEST_MONTHS, make_model
from paths import COUNTRY_MONTHLY, FIXTURE_DIR, FORECAST, ensure_dirs, read_json, write_json

MIN_TRAIN_ROWS = 120


def carry_previous(new_as_of):
    """Keep the last run's probabilities so the app can show what moved.

    Only carried when the previous file covers a DIFFERENT month. Re-running the
    pipeline twice in one week must not produce a comparison of a month against
    itself, which would silently report that nothing ever changes; in that case
    the older comparison is preserved instead.
    """
    if not FORECAST.exists():
        return None
    try:
        old = read_json(FORECAST)
    except Exception:  # noqa: BLE001 - a corrupt previous file must not stop a build
        return None

    old_as_of = old.get("as_of_month")
    if old_as_of and old_as_of != new_as_of:
        return {
            "as_of_month": old_as_of,
            "countries": {
                name: v["p"] for name, v in old.get("countries", {}).items() if "p" in v
            },
        }
    return old.get("previous")


def load_panel(fixture):
    if fixture:
        return pd.read_csv(FIXTURE_DIR / "panel_sample.csv")

    blob = read_json(COUNTRY_MONTHLY)
    months = blob["months"]
    rows = []
    for country, s in blob["countries"].items():
        for i, m in enumerate(months):
            rows.append(
                {
                    "country": country,
                    "year_month": m,
                    "num_events": s["events"][i],
                    "total_fatalities": s["fatalities"][i],
                    "battles": s["battles"][i],
                    "protests": s["protests"][i],
                    "violence_civilians": s["violence_civilians"][i],
                }
            )
    return pd.DataFrame(rows)


def calibration_slope(y, p):
    """Slope of observed frequency on predicted probability across deciles.

    1.0 is perfect. Below 1 means the model is overconfident, which would make
    the downstream expected-shock estimate too large in both directions.
    """
    d = pd.DataFrame({"y": np.asarray(y, dtype=float), "p": np.asarray(p, dtype=float)})
    d["bin"] = pd.qcut(d["p"], q=min(10, d["p"].nunique()), duplicates="drop")
    g = d.groupby("bin", observed=True).agg(obs=("y", "mean"), pred=("p", "mean")).dropna()
    if len(g) < 3 or g["pred"].std() == 0:
        return float("nan")
    return float(np.polyfit(g["pred"], g["obs"], 1)[0])


def choose_source(panel, seed=42):
    """Walk forward, score model against baseline, return the winner and stats."""
    rows = []
    for origin in ORIGINS:
        cut = pd.Timestamp(origin)
        end = cut + pd.DateOffset(months=TEST_MONTHS)
        train = panel[panel["year_month"] < cut]
        test = panel[(panel["year_month"] >= cut) & (panel["year_month"] < end)]

        if len(train) < MIN_TRAIN_ROWS or len(test) == 0 or test["escalated"].nunique() < 2:
            continue

        est, backend = make_model(seed)
        est.fit(train[FEATURE_COLS], train["escalated"])
        p_model = est.predict_proba(test[FEATURE_COLS])[:, 1]

        # The baseline is a ratio, not a probability. Map it through the
        # historical relationship between ratio and outcome so the two are
        # scored on the same footing.
        p_base = np.clip(
            train["escalated"].mean()
            * (test["ratio_to_threshold"] / max(train["ratio_to_threshold"].mean(), 1e-9)),
            0.001,
            0.999,
        )

        rows.append(
            {
                "origin": origin,
                "backend": backend,
                "model_roc": roc_auc_score(test["escalated"], p_model),
                "base_roc": roc_auc_score(test["escalated"], test["ratio_to_threshold"]),
                "model_brier": brier_score_loss(test["escalated"], p_model),
                "base_brier": brier_score_loss(test["escalated"], p_base),
                "model_cal": calibration_slope(test["escalated"], p_model),
            }
        )

    if not rows:
        raise SystemExit("No usable evaluation windows. Widen the panel.")

    ev = pd.DataFrame(rows)
    margin = ev["model_roc"].mean() - ev["base_roc"].mean()
    # Same strictness as model.py: a sub-0.02 margin is noise, and on a tie the
    # simpler thing wins.
    source = "model" if margin >= 0.02 else "baseline"

    return source, ev, margin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--lookahead", type=int, default=1)
    ap.add_argument("--quantile", type=float, default=0.75)
    args = ap.parse_args()

    ensure_dirs()
    raw = load_panel(args.fixture)
    raw["year_month"] = pd.to_datetime(raw["year_month"])

    featured = add_rolling_features(raw)
    labelled = add_target(featured, lookahead=args.lookahead, threshold_quantile=args.quantile)

    source, ev, margin = choose_source(labelled)
    print(f"\nmodel {ev['model_roc'].mean():.3f} vs baseline {ev['base_roc'].mean():.3f} "
          f"ROC-AUC (margin {margin:+.3f}) -> using the {source}")

    # Forecast rows are the most recent month per country. They are absent from
    # `labelled` because their future value does not exist yet, which is the
    # entire point: those are the ones worth predicting.
    latest = featured["year_month"].max()
    live = featured[featured["year_month"] == latest].copy()

    # The threshold column only exists on the labelled frame; recompute it for
    # the live rows from history up to and including the latest month.
    hist = featured.sort_values(["country", "year_month"])
    thresh = (
        hist.groupby("country")["total_fatalities"]
        .apply(lambda s: s.expanding(min_periods=12).quantile(args.quantile).iloc[-1])
        .rename("threshold")
    )
    live = live.merge(thresh, left_on="country", right_index=True, how="left")
    live["ratio_to_threshold"] = live["total_fatalities"] / live["threshold"].replace(0, np.nan)
    live = live.dropna(subset=["threshold", "ratio_to_threshold"])

    if source == "model":
        est, backend = make_model()
        est.fit(labelled[FEATURE_COLS], labelled["escalated"])
        probs = est.predict_proba(live[FEATURE_COLS])[:, 1]
    else:
        backend = "baseline"
        base_rate = labelled["escalated"].mean()
        probs = np.clip(
            base_rate * live["ratio_to_threshold"] / max(labelled["ratio_to_threshold"].mean(), 1e-9),
            0.001,
            0.999,
        ).to_numpy()

    live["p_escalation"] = probs
    target_month = (pd.Timestamp(latest) + pd.DateOffset(months=args.lookahead)).strftime("%Y-%m-%d")

    countries = {
        row.country: {
            "p": round(float(row.p_escalation), 4),
            "fatalities": int(row.total_fatalities),
            "events": int(row.num_events),
            "threshold": round(float(row.threshold), 1),
            "ratio": round(float(row.ratio_to_threshold), 3),
            # Centroid travels with the forecast so the web app can fly the map
            # to a country without shipping a second lookup table.
            "centroid": list(CENTROIDS[row.country]) if row.country in CENTROIDS else None,
        }
        for row in live.itertuples(index=False)
    }

    ranked = sorted(countries.items(), key=lambda kv: -kv[1]["p"])
    print(f"\nTop escalation risk for {target_month}:")
    for name, v in ranked[:10]:
        print(f"  {name:<32} p={v['p']:.3f}  ratio={v['ratio']:.2f}")

    write_json(
        FORECAST,
        {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "as_of_month": pd.Timestamp(latest).strftime("%Y-%m-%d"),
            "target_month": target_month,
            "lookahead_months": args.lookahead,
            "threshold_quantile": args.quantile,
            "source": source,
            "backend": backend,
            "previous": carry_previous(pd.Timestamp(latest).strftime("%Y-%m-%d")),
            "evaluation": {
                "model_roc_auc": round(float(ev["model_roc"].mean()), 4),
                "baseline_roc_auc": round(float(ev["base_roc"].mean()), 4),
                "margin": round(float(margin), 4),
                "model_brier": round(float(ev["model_brier"].mean()), 4),
                "baseline_brier": round(float(ev["base_brier"].mean()), 4),
                "calibration_slope": (
                    None if np.isnan(ev["model_cal"].mean()) else round(float(ev["model_cal"].mean()), 3)
                ),
                "windows": len(ev),
                "base_rate": round(float(labelled["escalated"].mean()), 4),
            },
            "countries": countries,
        },
        compact=False,
    )


if __name__ == "__main__":
    main()
