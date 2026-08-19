"""Build the map artifacts: a binned density grid and a detail-event layer.

    python build_snapshot.py --days 180
    python build_snapshot.py --fixture      # no network

Why two artifacts instead of one GeoJSON of everything: 180 days of global ACLED
is roughly 150k events. Shipping that as GeoJSON is ~30 MB and the map stutters.
Instead:

  world-heat.json    every event, but binned to a 0.5-degree cell and a week.
                     Drives the heatmap. Lossy in position, complete in count.
  events-top.geojson the most severe individual events only, full detail.
                     Drives the clickable dots.

Both are stored columnar/compact and are typically well under 2 MB together.
"""

import argparse
import datetime as dt

import numpy as np
import pandas as pd

from paths import EVENTS_TOP, FIXTURE_DIR, RAW_DIR, WORLD_HEAT, ensure_dirs, write_json
from universe import COUNTRIES

CELL = 0.5           # degrees
TOP_EVENTS = 3000    # individually rendered events
COORD_DP = 3         # ~110 m; more precision than the map can show


def _load_fixture():
    return pd.read_csv(FIXTURE_DIR / "events_sample.csv")


# Countries with enough activity that any month they serve will contain events.
# Used only to find where the data actually ends.
PROBE = ("Ukraine", "Mexico", "Yemen", "Myanmar")


def discover_latest(token, max_years_back=4):
    """Find the most recent event date this account can actually see.

    ACLED's Research tier serves lagged data, so "today minus 180 days" can sit
    entirely past the end of what the account is allowed to read. The first
    production run of this pipeline requested 2026-02-19..2026-08-18, got zero
    rows for all 51 countries, and exited 1 after 50 minutes of fetching. The
    window has to come from the data, not from the calendar.
    """
    from fetch_events import fetch_events

    today = pd.Timestamp(dt.date.today())
    for back in range(max_years_back):
        year = today.year - back
        latest = None
        for country in PROBE:
            df = fetch_events(token, country, year)
            if not len(df):
                continue
            d = pd.to_datetime(df["event_date"], errors="coerce").max()
            if pd.notna(d) and (latest is None or d > latest):
                latest = d
        if latest is not None:
            if back > 0:
                print(f"  note: no data for {today.year}; latest available is {latest:%Y-%m-%d}")
            return latest
    raise SystemExit(
        "Could not find any events in the last "
        f"{max_years_back} years for {', '.join(PROBE)}.\n"
        "Credentials work but the account appears to have no event-level access."
    )


def _load_from_api(countries, start, end):
    from fetch_events import fetch_events_between, get_token

    token = get_token()
    frames = []
    for country in countries:
        print(f" Fetching {country} {start}..{end}")
        df = fetch_events_between(token, country, start, end)
        if len(df):
            frames.append(df)
    if not frames:
        raise SystemExit(
            f"No events returned for {start}..{end} across {len(countries)} countries.\n"
            "That window is almost certainly past the end of what this account can\n"
            "read. Run `python check_coverage.py` to see the real cutoff."
        )
    return pd.concat(frames, ignore_index=True)


def _load_from_cache(start, end):
    """Reuse whatever full-year pulls already exist, then filter by date."""
    frames = [pd.read_csv(p) for p in sorted(RAW_DIR.glob("*.csv"))]
    if not frames:
        raise SystemExit("data/raw/ is empty. Run build_panel.py first, or use --fixture.")
    df = pd.concat(frames, ignore_index=True)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    return df[(df["event_date"] >= start) & (df["event_date"] <= end)]


def clean(df):
    df = df.copy()
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["fatalities"] = pd.to_numeric(df["fatalities"], errors="coerce").fillna(0).astype(int)

    df = df[df["event_date"].notna() & df["latitude"].notna() & df["longitude"].notna()]
    df = df[df["latitude"].between(-90, 90) & df["longitude"].between(-180, 180)]
    # ACLED uses 0,0 as a placeholder for unlocatable events. Dropping them
    # avoids a permanent hotspot in the Gulf of Guinea.
    df = df[~((df["latitude"].abs() < 1e-6) & (df["longitude"].abs() < 1e-6))]
    return df


def week_starts(df):
    """Monday-anchored ISO weeks covering the window, plus each row's index."""
    mondays = df["event_date"] - pd.to_timedelta(df["event_date"].dt.dayofweek, unit="D")
    mondays = mondays.dt.normalize()
    labels = sorted(mondays.unique())
    lookup = {d: i for i, d in enumerate(labels)}
    return [pd.Timestamp(d).strftime("%Y-%m-%d") for d in labels], mondays.map(lookup)


def build_heat(df, weeks, week_idx):
    """Bin to (cell, week). Emitted as a flat int array to keep the file small."""
    lon_bin = np.floor(df["longitude"] / CELL).astype(int)
    lat_bin = np.floor(df["latitude"] / CELL).astype(int)

    binned = pd.DataFrame(
        {
            "lon_bin": lon_bin,
            "lat_bin": lat_bin,
            "week": week_idx.to_numpy(),
            "fatalities": df["fatalities"].to_numpy(),
        }
    )
    agg = (
        binned.groupby(["week", "lon_bin", "lat_bin"], sort=True)
        .agg(events=("fatalities", "size"), fatalities=("fatalities", "sum"))
        .reset_index()
    )

    cells = []
    for row in agg.itertuples(index=False):
        cells.append(
            [
                int(row.week),
                round(row.lon_bin * CELL + CELL / 2, 3),
                round(row.lat_bin * CELL + CELL / 2, 3),
                int(row.events),
                int(row.fatalities),
            ]
        )

    return {
        "cell_size": CELL,
        "weeks": weeks,
        "schema": ["week", "lon", "lat", "events", "fatalities"],
        "cells": cells,
    }


def build_top_events(df, week_idx, limit=TOP_EVENTS):
    """Most severe events, with a recency tiebreak so a quiet recent week still
    has dots on the map."""
    d = df.copy()
    d["week"] = week_idx.to_numpy()

    # Rank within week so every week contributes, rather than one bad month
    # consuming the entire budget.
    d["rank_in_week"] = d.groupby("week")["fatalities"].rank(ascending=False, method="first")
    per_week = max(10, limit // max(1, d["week"].nunique()))
    picked = d[d["rank_in_week"] <= per_week]
    if len(picked) > limit:
        picked = picked.nlargest(limit, "fatalities")

    features = []
    for row in picked.itertuples(index=False):
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        round(float(row.longitude), COORD_DP),
                        round(float(row.latitude), COORD_DP),
                    ],
                },
                "properties": {
                    "d": pd.Timestamp(row.event_date).strftime("%Y-%m-%d"),
                    "w": int(row.week),
                    "t": str(getattr(row, "event_type", "") or ""),
                    "s": str(getattr(row, "sub_event_type", "") or ""),
                    "c": str(getattr(row, "country", "") or ""),
                    "l": str(getattr(row, "location", "") or ""),
                    # admin1 is the province/state. ACLED's `location` is often a
                    # village nobody outside the country recognises, so without
                    # this the popup reads "Kafr Nabl, Syria" and means nothing.
                    "a": str(getattr(row, "admin1", "") or ""),
                    "f": int(row.fatalities),
                },
            }
        )

    features.sort(key=lambda f: (f["properties"]["w"], -f["properties"]["f"]))
    return {"type": "FeatureCollection", "features": features}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--fixture", action="store_true")
    ap.add_argument("--cache-only", action="store_true")
    args = ap.parse_args()

    ensure_dirs()

    if args.fixture:
        end = pd.Timestamp(dt.date.today())
        start = end - pd.Timedelta(days=args.days)
        raw = _load_fixture()
    elif args.cache_only:
        end = pd.Timestamp(dt.date.today())
        start = end - pd.Timedelta(days=args.days)
        raw = _load_from_cache(start, end)
    else:
        from fetch_events import get_token

        # Anchor the window on the newest event the account can see, not on
        # today. Costs a handful of probe requests and saves the whole run.
        token = get_token()
        end = discover_latest(token)
        start = end - pd.Timedelta(days=args.days)
        print(f"\nWindow: {start:%Y-%m-%d} to {end:%Y-%m-%d}")
        raw = _load_from_api(COUNTRIES, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    df = clean(raw)
    if df.empty:
        raise SystemExit("No usable events after cleaning.")

    weeks, week_idx = week_starts(df)
    print(f"\n{len(df):,} events across {len(weeks)} weeks")

    write_json(WORLD_HEAT, build_heat(df, weeks, week_idx))
    write_json(EVENTS_TOP, build_top_events(df, week_idx))


if __name__ == "__main__":
    main()
