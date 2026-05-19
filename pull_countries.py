import time
import pandas as pd
from fetch_events import get_token, fetch_events
from aggregate import to_monthly

COUNTRIES = ["Yemen", "Sudan", "Ukraine", "Myanmar", "Mexico"]
YEAR = 2024    

def pull_many(token,countries, year):
    """Pull event data for multiple countries and aggregate to monthly."""
    all_events = []
    for country in countries:
        print(f"Fetching {country} {year}...")
        df = fetch_events (token, country=country, year=year)
        print(f" ->{len(df)} events")
        all_events.append(df)
        time.sleep(1)

    return pd.concat(all_events,ignore_index=True)

if __name__ == "__main__":
    token = get_token()
    events = pull_many(token, COUNTRIES, YEAR)
    print(f"\n Total events across {len(COUNTRIES)} countries: {len(events)}")

    monthly = to_monthly(events)
    print("\nMonthly Panel:")
    print(monthly.to_string())

    monthly.to_csv("monthly_panel_5countries_2024.csv", index=False)
    print("\nSaved to monthly_panel_5countries_2024.csv")
