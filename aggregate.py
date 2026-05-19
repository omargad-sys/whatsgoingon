import pandas as pd
from fetch_events import get_token, fetch_events


def to_monthly(events):
    """Collapse event-level rows to one row per country-month."""
    df = events.copy()

    # Make the date a real datetime, not a string
    df["event_date"] = pd.to_datetime(df["event_date"])

    # Bucket every event into the first day of its month
    df["year_month"] = df["event_date"].dt.to_period("M").dt.to_timestamp()

    # ACLED sometimes returns fatalities as strings — force to number
    df["fatalities"] = pd.to_numeric(df["fatalities"], errors="coerce").fillna(0)

    monthly = (
        df.groupby(["country", "year_month"])
        .agg(
            num_events=("event_date", "count"),
            total_fatalities=("fatalities", "sum"),
            battles=("event_type", lambda s: (s == "Battles").sum()),
            protests=("event_type", lambda s: (s == "Protests").sum()),
            violence_civilians=("event_type", lambda s: (s == "Violence against civilians").sum()),
        )
        .reset_index()
    )
    return monthly


if __name__ == "__main__":
    token = get_token()
    events = fetch_events(token, country="Yemen", year=2024)
    monthly = to_monthly(events)
    print(monthly)
