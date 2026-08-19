"""Report how far forward this ACLED account's data actually goes.

    cd research && python check_coverage.py

Takes about a minute and answers the question that cost a 51-minute CI run:
the Research tier serves lagged data, so "the last 180 days" can land entirely
past the end of what the account can read, and every request comes back empty
without any error to explain why.

Run this before changing --days or debugging an empty snapshot.
"""

import datetime as dt

import pandas as pd

from fetch_events import fetch_events, get_token

PROBE = ["Ukraine", "Mexico", "Yemen", "Myanmar", "Sudan"]
YEARS_BACK = 4


def main():
    token = get_token()
    today = pd.Timestamp(dt.date.today())
    print(f"Today is {today:%Y-%m-%d}. Probing {len(PROBE)} countries.\n")

    overall = None
    rows = []

    for back in range(YEARS_BACK):
        year = today.year - back
        for country in PROBE:
            df = fetch_events(token, country, year)
            if not len(df):
                rows.append({"year": year, "country": country, "events": 0, "latest": None})
                continue
            latest = pd.to_datetime(df["event_date"], errors="coerce").max()
            rows.append(
                {
                    "year": year,
                    "country": country,
                    "events": len(df),
                    "latest": None if pd.isna(latest) else latest.strftime("%Y-%m-%d"),
                }
            )
            if pd.notna(latest) and (overall is None or latest > overall):
                overall = latest
        if overall is not None:
            break

    print(pd.DataFrame(rows).to_string(index=False))

    if overall is None:
        print(
            f"\nNo events found in the last {YEARS_BACK} years.\n"
            "Credentials work but this account has no event-level access."
        )
        return

    lag_days = (today - overall).days
    print(f"\nLatest event this account can read: {overall:%Y-%m-%d}")
    print(f"Lag behind today: {lag_days} days (~{lag_days / 30:.1f} months)")
    print(
        f"\nA 180-day map window should therefore run "
        f"{(overall - pd.Timedelta(days=180)):%Y-%m-%d} to {overall:%Y-%m-%d}.\n"
        "build_snapshot.py now derives this automatically; you do not need to\n"
        "pass it by hand."
    )


if __name__ == "__main__":
    main()
