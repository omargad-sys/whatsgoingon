"""Feature engineering and target construction for the escalation forecaster.

    python features.py

Two rules govern everything in this file:

1. A feature for month t may only use information available at the end of
   month t. Rolling means are computed with .shift(1) so they never include
   the month being predicted.
2. The LABEL may only use information available at the end of month t too,
   apart from the future value it is asking about. This is the rule the
   original version broke: the escalation threshold was a quantile over the
   country's entire history, so the label for January 2019 depended on
   fatalities in 2024. The threshold is now an expanding quantile over the
   past only.
"""

import numpy as np
import pandas as pd

ROLL_COLS = ("num_events", "total_fatalities")
ROLL_WINDOWS = (3, 6, 12)

# Months of history required before a country gets a usable threshold. Below
# this, an expanding quantile is estimated off so few points it is noise.
MIN_HISTORY = 12


def add_rolling_features(panel, cols=ROLL_COLS, windows=ROLL_WINDOWS):
    """Trailing means, excluding the current month."""
    df = panel.sort_values(["country", "year_month"]).copy()

    for col in cols:
        grp = df.groupby("country")[col]
        for w in windows:
            df[f"{col}_roll{w}_mean"] = grp.transform(
                lambda s: s.shift(1).rolling(w, min_periods=1).mean()
            )
        # Momentum: this month against its own trailing year. This is the
        # single most informative thing in the feature set, and the original
        # version made the model reconstruct it from raw levels.
        df[f"{col}_vs_roll12"] = df[col] / df[f"{col}_roll12_mean"].replace(0, np.nan)

    return df


def add_target(panel, lookahead=1, threshold_quantile=0.75, min_history=MIN_HISTORY):
    """Label a country-month as escalating if fatalities `lookahead` months
    later exceed the country's own historical high-water mark.

    The threshold is an EXPANDING quantile over months strictly before t. Using
    the full-sample quantile, as the first draft did, leaks the future into the
    label and inflates every metric downstream.
    """
    df = panel.sort_values(["country", "year_month"]).copy()

    df["future_fatalities"] = df.groupby("country")["total_fatalities"].shift(-lookahead)
    df["threshold"] = df.groupby("country")["total_fatalities"].transform(
        lambda s: s.shift(1).expanding(min_periods=min_history).quantile(threshold_quantile)
    )

    # Give the model the same comparison the persistence baseline gets. Without
    # it the model has to infer a country-specific scale from raw levels, which
    # it cannot do well from a few hundred rows.
    df["ratio_to_threshold"] = df["total_fatalities"] / df["threshold"].replace(0, np.nan)

    df["escalated"] = (df["future_fatalities"] > df["threshold"]).astype(int)

    # Rows without a future value or without enough history are not examples.
    # Silently keeping them as escalated=0 is how you teach a model that the end
    # of the sample is always calm.
    return df.dropna(subset=["future_fatalities", "threshold", "ratio_to_threshold"])


FEATURE_COLS = [
    "num_events",
    "total_fatalities",
    "battles",
    "protests",
    "violence_civilians",
    "num_events_roll3_mean",
    "num_events_roll6_mean",
    "num_events_roll12_mean",
    "total_fatalities_roll3_mean",
    "total_fatalities_roll6_mean",
    "total_fatalities_roll12_mean",
    "num_events_vs_roll12",
    "total_fatalities_vs_roll12",
    "threshold",
    "ratio_to_threshold",
]


def build(path="monthly_panel_full.csv"):
    panel = pd.read_csv(path)
    panel["year_month"] = pd.to_datetime(panel["year_month"])
    return add_target(add_rolling_features(panel))


if __name__ == "__main__":
    panel = build()

    print(f"Shape: {panel.shape}")
    print(f"Countries: {panel['country'].nunique()}")
    print(f"Span: {panel['year_month'].min():%Y-%m} to {panel['year_month'].max():%Y-%m}")
    print(f"Escalation base rate: {panel['escalated'].mean():.3f}")
    print(f"\nFeatures ({len(FEATURE_COLS)}): {FEATURE_COLS}")

    panel.to_csv("panel_with_features.csv", index=False)
    print("\nSaved to panel_with_features.csv")
