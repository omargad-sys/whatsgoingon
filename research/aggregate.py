"""Collapse event-level ACLED rows into a country-month panel."""

import pandas as pd

EVENT_TYPES = [
    "Battles",
    "Explosions/Remote violence",
    "Violence against civilians",
    "Protests",
    "Riots",
    "Strategic developments",
]


def to_monthly(events):
    """One row per country-month.

    Robust to the two things ACLED actually does in practice: returning
    `fatalities` as a string, and returning rows whose event_date is null.
    """
    df = events.copy()

    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df = df[df["event_date"].notna()]

    df["year_month"] = df["event_date"].dt.to_period("M").dt.to_timestamp()
    df["fatalities"] = pd.to_numeric(df["fatalities"], errors="coerce").fillna(0)

    monthly = (
        df.groupby(["country", "year_month"])
        .agg(
            num_events=("event_date", "count"),
            total_fatalities=("fatalities", "sum"),
            battles=("event_type", lambda s: (s == "Battles").sum()),
            protests=("event_type", lambda s: (s == "Protests").sum()),
            violence_civilians=(
                "event_type",
                lambda s: (s == "Violence against civilians").sum(),
            ),
        )
        .reset_index()
    )

    monthly["total_fatalities"] = monthly["total_fatalities"].astype(int)
    monthly["year_month"] = monthly["year_month"].dt.strftime("%Y-%m-%d")
    return monthly


def fill_missing_months(panel):
    """Insert explicit zero rows for country-months with no recorded events.

    Without this, a quiet month is absent rather than zero, and the rolling
    z-score silently computes over the wrong window.
    """
    panel = panel.copy()
    panel["year_month"] = pd.to_datetime(panel["year_month"])
    months = pd.date_range(panel["year_month"].min(), panel["year_month"].max(), freq="MS")
    countries = sorted(panel["country"].unique())

    grid = pd.MultiIndex.from_product([countries, months], names=["country", "year_month"])
    out = (
        panel.set_index(["country", "year_month"])
        .reindex(grid)
        .fillna(0)
        .reset_index()
    )
    for col in out.columns:
        if col not in ("country", "year_month"):
            out[col] = out[col].astype(int)
    out["year_month"] = out["year_month"].dt.strftime("%Y-%m-%d")
    return out


if __name__ == "__main__":
    from fetch_events import fetch_events, get_token

    events = fetch_events(get_token(), country="Yemen", year=2024)
    print(to_monthly(events))
