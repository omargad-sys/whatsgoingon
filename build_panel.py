import time
from pathlib import Path
import pandas as pd
from fetch_events import get_token, fetch_events
from aggregate import to_monthly

COUNTRIES = ["Yemen", "Sudan", "Ukraine", "Myanmar", "Mexico"]
YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

def pull_with_cache(token,country,year):
    """Pull events for (country,year). IF already saved to disk, skip the API call."""
    cache_path = DATA_DIR / f"{country}_{year}.csv"
    if cache_path.exists():
        print(f" [cached] {country} {year}")
        return pd.read_csv(cache_path)
    print(f" Fetching {country} {year}...")
    df = fetch_events(token, country=country, year=year)
    print(f"  -> {len(df)} events,saved")
    df.to_csv(cache_path, index=False)
    return df

def build_panel():
    token = get_token()
    all_events = []
    for country in COUNTRIES:
        for year in YEARS:
            df = pull_with_cache(token,country, year)
            all_events.append(df)
            time.sleep(0.5)
    return pd.concat(all_events, ignore_index=True)

if __name__ == "__main__":
     print("Building panel — this will take a while on first run.\n")
     events = build_panel()
     print(f"\nTotal events: {len(events)}")

     panel = to_monthly(events)
     print(f"Panel shape: {panel.shape[0]} rows × {panel.shape[1]} columns")

     panel.to_csv("monthly_panel_full.csv", index=False)
     print("Saved to monthly_panel_full.csv")

