"""Report how far forward this ACLED account's data actually goes.

    cd research && python check_coverage.py

Answers the question that cost a 51-minute CI run: the Research tier serves
lagged data, so "the last 180 days" can land entirely past the end of what the
account can read, and every request comes back empty without any error to
explain why.

Costs a handful of tiny requests and finishes in seconds. The earlier version
pulled entire country-years to find one date, which on Ukraine meant tens of
thousands of rows per probe and looked to the caller like a hang.

Run this before changing --days or debugging an empty snapshot.
"""

import datetime as dt

import pandas as pd

from fetch_events import get_token, latest_event_date

PROBE = ["Ukraine", "Mexico", "Yemen", "Myanmar", "Sudan"]
MONTHS_BACK = 36


def main():
    token = get_token()
    today = pd.Timestamp(dt.date.today())
    print(f"Today is {today:%Y-%m-%d}. Probing {len(PROBE)} countries.\n")

    rows = []
    overall = None

    for country in PROBE:
        latest = latest_event_date(token, country, months_back=MONTHS_BACK)
        lag = None if latest is None else (today - latest).days
        rows.append(
            {
                "country": country,
                "latest": "none found" if latest is None else f"{latest:%Y-%m-%d}",
                "lag_days": "" if lag is None else lag,
            }
        )
        print(f"  {country:<10} {rows[-1]['latest']}")
        if latest is not None and (overall is None or latest > overall):
            overall = latest

    print()
    print(pd.DataFrame(rows).to_string(index=False))

    if overall is None:
        print(
            f"\nNo events found in the last {MONTHS_BACK} months.\n"
            "Credentials work but this account has no event-level access.\n"
            "That is a tier problem, not a code problem: re-register with the\n"
            "njit.edu address to get Research tier."
        )
        return

    lag_days = (today - overall).days
    print(f"\nLatest event this account can read: {overall:%Y-%m-%d}")
    print(f"Lag behind today: {lag_days} days (~{lag_days / 30:.1f} months)")
    print(
        f"\nA 180-day map window should therefore run "
        f"{(overall - pd.Timedelta(days=180)):%Y-%m-%d} to {overall:%Y-%m-%d}.\n"
        "build_snapshot.py derives this automatically; you do not pass it by hand."
    )


if __name__ == "__main__":
    main()
