"""ACLED API client: OAuth password grant + paginated event fetch.

Public surface kept backwards-compatible with the original prototype, so
build_panel.py / aggregate.py / pull_countries.py still work unchanged:

    get_token() -> str
    fetch_events(token, country, year) -> DataFrame

Added since: field selection (payload is ~4x smaller), retry with backoff,
a max_pages guard, and fetch_events_between() for date-range pulls.
"""

import datetime as dt
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv

# Look for .env in research/ first, then the repo root, so an existing .env at
# either level keeps working after the merge.
_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (os.path.join(_HERE, ".env"), os.path.join(_HERE, os.pardir, ".env")):
    if os.path.exists(_candidate):
        load_dotenv(_candidate)
        break
else:
    load_dotenv()

TOKEN_URL = "https://acleddata.com/oauth/token"
READ_URL = "https://acleddata.com/api/acled/read"

# ACLED caps a single response at 5000 rows regardless of `limit`.
PAGE_SIZE = 5000
# A country-year has never exceeded ~120k events. 60 pages is a generous ceiling
# that still stops a bad filter from looping forever against a paying quota.
MAX_PAGES = 60

# Only what the panel and the map actually consume. Notably excludes `notes`,
# which is the single largest field and is not rendered anywhere.
FIELDS = [
    "event_id_cnty",
    "event_date",
    "year",
    "disorder_type",
    "event_type",
    "sub_event_type",
    "actor1",
    "actor2",
    "country",
    "admin1",
    "location",
    "latitude",
    "longitude",
    "fatalities",
]


class AcledError(RuntimeError):
    pass


def get_token():
    """Exchange username/password for a 24h access token."""
    email = os.getenv("ACLED_EMAIL")
    password = os.getenv("ACLED_PASSWORD")
    if not (email and password):
        raise AcledError(
            "Missing ACLED_EMAIL / ACLED_PASSWORD. "
            "Locally: copy .env.example to .env. In CI: set repository secrets."
        )

    response = requests.post(
        TOKEN_URL,
        data={
            "username": email,
            "password": password,
            "grant_type": "password",
            "client_id": "acled",
            "scope": "authenticated",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _get_with_retry(params, token, attempts=4):
    """GET with exponential backoff on 429 and 5xx. Other 4xx fail immediately."""
    delay = 2.0
    last = None
    for attempt in range(attempts):
        response = requests.get(
            READ_URL,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=90,
        )
        if response.status_code == 200:
            return response
        last = response
        if response.status_code == 429 or response.status_code >= 500:
            time.sleep(delay)
            delay *= 2
            continue
        response.raise_for_status()
    last.raise_for_status()
    raise AcledError("unreachable")


def _paginate(base_params, token, label):
    frames = []
    for page in range(1, MAX_PAGES + 1):
        params = dict(base_params)
        params.update(
            {
                "limit": PAGE_SIZE,
                "page": page,
                "_format": "json",
                "fields": "|".join(FIELDS),
            }
        )
        payload = _get_with_retry(params, token).json()
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload

        if not rows:
            break

        frames.append(pd.DataFrame(rows))
        print(f"  {label} page {page}: {len(rows)} rows")

        if len(rows) < PAGE_SIZE:
            break
    else:
        print(f"  {label}: hit MAX_PAGES={MAX_PAGES}, results may be truncated")

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=FIELDS)


def _probe(token, country, start, end, limit=1):
    """One tiny request: does `country` have any event in [start, end]?

    Asks for a single row and a single field, so the response is a few hundred
    bytes instead of a few megabytes. Returns the rows the API sent back.
    """
    params = {
        "country": country,
        "event_date": f"{start}|{end}",
        "event_date_where": "BETWEEN",
        "limit": limit,
        "page": 1,
        "_format": "json",
        "fields": "event_date",
    }
    payload = _get_with_retry(params, token).json()
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    return rows or []


def _latest_day_in(token, country, start, end):
    """Binary search the last day inside [start, end] that has an event.

    Every probe asks for one row, so this is ~5 tiny requests for a month. The
    alternative, pulling the month and taking the max date, silently truncates
    at the 5000-row cap: Ukraine clears that in a single month, and the answer
    would then depend on whatever order the API happened to return.
    """
    lo, hi = start, end
    best = start
    while lo <= hi:
        mid = lo + (hi - lo) / 2
        mid = pd.Timestamp(mid.date())
        if _probe(token, country, mid.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")):
            best = mid
            lo = mid + pd.Timedelta(days=1)
        else:
            hi = mid - pd.Timedelta(days=1)
    return best


def latest_event_date(token, country, months_back=36):
    """Most recent event date this account can read for `country`, or None.

    Walks backwards a month at a time from the current month, stops at the
    first month that has anything, then binary searches that month for the
    exact day. Every request asks for one row and one field.

    The obvious implementation, pulling a whole country-year and taking the max
    date, costs tens of thousands of rows to answer a one-row question. On
    Ukraine that is minutes per probe, and it is why `check_coverage.py` looked
    like it had hung.
    """
    cursor = pd.Timestamp(dt.date.today()).to_period("M")

    for _ in range(months_back):
        start = cursor.start_time
        end = cursor.end_time.normalize()
        if _probe(token, country, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")):
            return _latest_day_in(token, country, start, end)
        cursor -= 1

    return None


def fetch_events(token, country, year, page_size=PAGE_SIZE):
    """Pull all events for a country-year. `page_size` kept for compatibility."""
    return _paginate({"country": country, "year": year}, token, f"{country} {year}")


def fetch_events_between(token, country, start, end):
    """Pull all events for a country between two YYYY-MM-DD dates, inclusive."""
    return _paginate(
        {
            "country": country,
            "event_date": f"{start}|{end}",
            "event_date_where": "BETWEEN",
        },
        token,
        f"{country} {start}..{end}",
    )


if __name__ == "__main__":
    df = fetch_events(get_token(), country="Yemen", year=2024)
    print(f"Got {len(df)} events total.")
