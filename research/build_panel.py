"""Build the country-month conflict panel over the full universe.

    python build_panel.py              # all universe countries, 2018 -> now
    python build_panel.py --countries Yemen Sudan
    python build_panel.py --fixture    # no network, uses research/fixtures/

Every (country, year) pull is cached to research/data/raw/. The first full run
is slow and burns API calls; every run after that is nearly free. Do not delete
the cache casually.
"""

import argparse
import datetime as dt
import time
from pathlib import Path

import pandas as pd

from aggregate import to_monthly
from paths import COUNTRY_MONTHLY, INTERIM_DIR, RAW_DIR, ensure_dirs, write_json
from universe import COUNTRIES, YEARS


def pull_with_cache(token, country, year):
    """Pull events for (country, year). If already on disk, skip the API call."""
    cache_path = RAW_DIR / f"{country.replace(' ', '_')}_{year}.csv"
    if cache_path.exists():
        print(f" [cached] {country} {year}")
        return pd.read_csv(cache_path)

    from fetch_events import fetch_events  # imported late so --fixture needs no creds

    print(f" Fetching {country} {year}...")
    df = fetch_events(token, country=country, year=year)
    print(f"  -> {len(df)} events, saved")
    df.to_csv(cache_path, index=False)
    return df


def build_panel(countries, years):
    from fetch_events import get_token

    token = get_token()
    frames = []
    for country in countries:
        for year in years:
            frames.append(pull_with_cache(token, country, year))
            time.sleep(0.4)
    return pd.concat(frames, ignore_index=True)


def panel_from_cache(countries, years):
    """Rebuild the panel from whatever is already in data/raw/, no network."""
    frames = []
    for country in countries:
        for year in years:
            p = RAW_DIR / f"{country.replace(' ', '_')}_{year}.csv"
            if p.exists():
                frames.append(pd.read_csv(p))
    if not frames:
        raise SystemExit("data/raw/ is empty. Run without --cache-only first.")
    return pd.concat(frames, ignore_index=True)


def panel_to_json(panel):
    """Columnar JSON: ~60% smaller than an array of objects, and the front end
    reads it straight into typed arrays."""
    panel = panel.sort_values(["country", "year_month"])
    months = sorted(panel["year_month"].astype(str).unique())
    month_index = {m: i for i, m in enumerate(months)}

    by_country = {}
    for country, grp in panel.groupby("country", sort=True):
        n = len(months)
        events = [0] * n
        fatalities = [0] * n
        battles = [0] * n
        protests = [0] * n
        vac = [0] * n
        for row in grp.itertuples(index=False):
            i = month_index[str(row.year_month)]
            events[i] = int(row.num_events)
            fatalities[i] = int(row.total_fatalities)
            battles[i] = int(row.battles)
            protests[i] = int(row.protests)
            vac[i] = int(row.violence_civilians)
        by_country[country] = {
            "events": events,
            "fatalities": fatalities,
            "battles": battles,
            "protests": protests,
            "violence_civilians": vac,
        }

    return {
        "months": months,
        "countries": by_country,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", nargs="*", default=None)
    ap.add_argument("--years", nargs="*", type=int, default=None)
    ap.add_argument("--cache-only", action="store_true", help="no network, use data/raw/")
    ap.add_argument("--fixture", action="store_true", help="no network, use fixtures/")
    args = ap.parse_args()

    ensure_dirs()
    countries = args.countries or COUNTRIES
    years = args.years or [y for y in YEARS if y <= dt.date.today().year]

    if args.fixture:
        # panel_sample.csv, not events_sample.csv: the events fixture only spans
        # the 180-day map window, while the panel needs years of history for the
        # rolling z-score and the regression to have anything to work with.
        from paths import FIXTURE_DIR

        panel = pd.read_csv(FIXTURE_DIR / "panel_sample.csv")
        print(f"Fixture panel: {panel.shape[0]} rows x {panel.shape[1]} columns")
        INTERIM_DIR.mkdir(parents=True, exist_ok=True)
        panel.to_csv(INTERIM_DIR / "country_monthly.csv", index=False)
        write_json(COUNTRY_MONTHLY, panel_to_json(panel))
        return

    if args.cache_only:
        events = panel_from_cache(countries, years)
    else:
        print(f"Building panel: {len(countries)} countries x {len(years)} years.\n")
        events = build_panel(countries, years)

    print(f"\nTotal events: {len(events):,}")
    panel = to_monthly(events)
    print(f"Panel shape: {panel.shape[0]} rows x {panel.shape[1]} columns")

    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = INTERIM_DIR / "country_monthly.csv"
    panel.to_csv(csv_path, index=False)
    print(f"  wrote {csv_path}")

    write_json(COUNTRY_MONTHLY, panel_to_json(panel))


if __name__ == "__main__":
    main()
