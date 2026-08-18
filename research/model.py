"""Escalation forecaster, evaluated honestly.

    python model.py
    python model.py --lookahead 3 --quantile 0.9

Read this before trusting any number it prints:

The first draft scored ROC-AUC 1.000. It did that because `train` and `test`
were the same slice, so the model was graded on rows it had memorised. That is
the most common way a forecasting project goes wrong, and it is invisible
unless you look for it, because a perfect score feels like success.

This version does three things the first draft did not:

1. Trains and tests on disjoint time periods, with the test period strictly
   after the training period.
2. Walks the split forward across several origins instead of trusting one
   arbitrary cut, because with a few hundred rows a single split is mostly luck.
3. Prints a dumb baseline next to the model, every time, and refuses to let you
   read the model's score without it.

That third one matters most here. On the 5-country panel, the baseline
`this month's fatalities / this country's historical 75th percentile` scores
about 0.96 ROC-AUC, and the gradient-boosted model does not beat it. The target
is dominated by persistence: fatalities are strongly autocorrelated, so "was
last month bad" already answers "will next month be bad". Until the model beats
the baseline, the model is decoration.
"""

import argparse
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from features import FEATURE_COLS, build

warnings.filterwarnings("ignore", category=FutureWarning)

# Origins to walk forward through. Each one trains on everything before the
# date and tests on the 12 months after it.
ORIGINS = ["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"]
TEST_MONTHS = 12
MIN_TRAIN_ROWS = 120


def make_model(seed=42):
    """XGBoost if available, sklearn's gradient booster otherwise. The fallback
    exists so this script runs in CI and on a fresh clone without xgboost."""
    try:
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.05,  # was `learing_rate`, which XGBoost silently ignored
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=2.0,
            random_state=seed,
            eval_metric="logloss",
        ), "xgboost"
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(
            max_iter=200, max_depth=3, learning_rate=0.05, random_state=seed
        ), "sklearn"


def score(y_true, p):
    if len(np.unique(y_true)) < 2:
        return None
    return {
        "roc_auc": roc_auc_score(y_true, p),
        "pr_auc": average_precision_score(y_true, p),
        "brier": brier_score_loss(y_true, np.clip(p, 0, 1)),
        "base_rate": float(np.mean(y_true)),
        "n": len(y_true),
    }


def walk_forward(panel, seed=42):
    """Rolling-origin evaluation. Returns one row per origin."""
    rows = []
    for origin in ORIGINS:
        cut = pd.Timestamp(origin)
        end = cut + pd.DateOffset(months=TEST_MONTHS)

        train = panel[panel["year_month"] < cut]
        test = panel[(panel["year_month"] >= cut) & (panel["year_month"] < end)]

        if len(train) < MIN_TRAIN_ROWS or len(test) == 0:
            continue
        if test["escalated"].nunique() < 2:
            print(f"  {origin}: test window has one class only, skipped")
            continue

        model, backend = make_model(seed)
        model.fit(train[FEATURE_COLS], train["escalated"])
        p_model = model.predict_proba(test[FEATURE_COLS])[:, 1]

        # The baseline. One column, no training, no hyperparameters.
        p_base = test["ratio_to_threshold"].to_numpy()

        m, b = score(test["escalated"], p_model), score(test["escalated"], p_base)
        rows.append(
            {
                "origin": origin,
                "backend": backend,
                "n_train": len(train),
                "n_test": len(test),
                "base_rate": m["base_rate"],
                "model_roc": m["roc_auc"],
                "base_roc": b["roc_auc"],
                "model_pr": m["pr_auc"],
                "base_pr": b["pr_auc"],
                "model_brier": m["brier"],
                "beats_baseline": m["roc_auc"] > b["roc_auc"],
            }
        )
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="monthly_panel_full.csv")
    ap.add_argument("--lookahead", type=int, default=1)
    ap.add_argument("--quantile", type=float, default=0.75)
    args = ap.parse_args()

    from features import add_rolling_features, add_target

    raw = pd.read_csv(args.panel)
    raw["year_month"] = pd.to_datetime(raw["year_month"])
    panel = add_target(
        add_rolling_features(raw), lookahead=args.lookahead, threshold_quantile=args.quantile
    )

    print(f"Panel: {len(panel)} rows, {panel['country'].nunique()} countries, "
          f"{panel['year_month'].min():%Y-%m} to {panel['year_month'].max():%Y-%m}")
    print(f"Target: fatalities {args.lookahead} month(s) ahead above the country's "
          f"expanding {args.quantile:.0%} quantile")
    print(f"Base rate: {panel['escalated'].mean():.3f}\n")

    results = walk_forward(panel)
    if results.empty:
        raise SystemExit("No usable evaluation windows. Widen the panel or move the origins.")

    print("Rolling-origin evaluation (train on everything before the origin, "
          f"test on the next {TEST_MONTHS} months):\n")
    show = results[["origin", "n_train", "n_test", "base_rate",
                    "model_roc", "base_roc", "model_pr", "base_pr"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    wins = int(results["beats_baseline"].sum())
    margin = results["model_roc"].mean() - results["base_roc"].mean()
    print(f"\nModel mean ROC-AUC:    {results['model_roc'].mean():.3f}")
    print(f"Baseline mean ROC-AUC: {results['base_roc'].mean():.3f}")
    print(f"Margin: {margin:+.3f}  ·  model wins {wins} of {len(results)} windows")

    # A win has to be big enough and consistent enough to be a win. Across five
    # windows of ~60 rows, a mean margin under 0.02 is noise, and calling it a
    # result is how a project talks itself into shipping a model that does
    # nothing. MIN_MARGIN is deliberately strict.
    MIN_MARGIN = 0.02
    if margin >= MIN_MARGIN and wins >= len(results) - 1:
        print("\n  Model clears the baseline. Now check it on a country it never trained on.")
    elif margin > -MIN_MARGIN:
        print(
            "\n  TIE. The model matches `fatalities / threshold` and does not beat it.\n"
            "  A tie means the machine learning is buying you nothing: report the\n"
            "  baseline instead, it is one line and needs no training.\n"
            "  The target is dominated by persistence, because fatalities are\n"
            "  strongly autocorrelated. To make this a real modelling problem:\n"
            "    - widen the panel well past 5 countries (the biggest lever)\n"
            "    - predict a harder target, e.g. escalation beyond what persistence\n"
            "      already implies, or a jump of a given size\n"
            "    - lengthen the horizon: --lookahead 3 is much harder than 1"
        )
    else:
        print(
            "\n  The model LOSES to `fatalities / threshold`.\n"
            "  Do not report the model's score as a result. With this little data a\n"
            "  gradient booster overfits; the baseline cannot."
        )

    print(f"\nBackend: {results['backend'].iloc[0]}")


if __name__ == "__main__":
    main()
