"""Turn the country-month panel into per-theme conflict intensity shocks.

Definitions, in one place because the methodology page quotes them verbatim:

    raw_t    = sum over member countries of (events + FATALITY_WEIGHT * fatalities)
    level_t  = log1p(raw_t)
    shock_t  = level_t - level_{t-1}
    z_t      = (shock_t - rolling_mean(shock, 36)) / rolling_std(shock, 36)

The log is what stops Ukraine 2022 and Sudan 2023 from defining the entire
scale. The rolling z-score is what makes a shock mean "unusual relative to the
recent past" rather than "unusual relative to 2018", which matters because the
underlying ACLED coverage has widened over time and a raw count trends upward
for reasons that have nothing to do with conflict.
"""

import numpy as np
import pandas as pd

from universe import FATALITY_WEIGHT, THEMES, ZSCORE_WINDOW

MIN_PERIODS = 24


def theme_levels(panel):
    """DataFrame indexed by month, one column per theme, of log1p severity."""
    p = panel.copy()
    p["year_month"] = pd.to_datetime(p["year_month"])
    p["severity"] = p["num_events"] + FATALITY_WEIGHT * p["total_fatalities"]

    out = {}
    for theme_id, meta in THEMES.items():
        members = p[p["country"].isin(meta["countries"])]
        raw = members.groupby("year_month")["severity"].sum().sort_index()
        out[theme_id] = np.log1p(raw)

    return pd.DataFrame(out).sort_index()


def theme_shocks(panel, window=ZSCORE_WINDOW, min_periods=MIN_PERIODS):
    """Rolling-z-scored month-over-month change in each theme's severity."""
    levels = theme_levels(panel)
    shocks = levels.diff()

    mean = shocks.rolling(window, min_periods=min_periods).mean()
    std = shocks.rolling(window, min_periods=min_periods).std()
    z = (shocks - mean) / std.replace(0.0, np.nan)

    # Cap at +/-4 sigma. Uncapped, a single coverage-methodology change in the
    # source data can produce a 12-sigma month that dominates every regression.
    return z.clip(-4.0, 4.0)


def latest_shocks(panel, n=1):
    """Most recent n months of z-scores, for the live overlay."""
    z = theme_shocks(panel).dropna(how="all")
    return z.tail(n)
