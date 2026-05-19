import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def get_token():
    response = requests.post(
        "https://acleddata.com/oauth/token",
        data={
            "username": os.getenv("ACLED_EMAIL"),
            "password": os.getenv("ACLED_PASSWORD"),
            "grant_type": "password",
            "client_id": "acled",
            "scope": "authenticated",
        },
        headers ={"Content-Type": "application/x-www-form-urlencoded"},
        timeout = 30,
    )
    response.raise_for_status()
    return response.json()["access_token"]

def fetch_events(token, country, year, page_size=5000):
    """Pull ALL events for a country-year by paginating."""
    all_pages = []
    page = 1
    while True:
        response = requests.get(
            "https://acleddata.com/api/acled/read",
            params={
                "country": country,
                "year": year,
                "limit": page_size,
                "page": page,
                "_format": "json",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", payload) if isinstance(payload, dict) else payload

        if not rows:
            break

        all_pages.append(pd.DataFrame(rows))
        print(f"  page {page}: got {len(rows)} rows")

        if len(rows) < page_size:
            break

        page += 1

    return pd.concat(all_pages, ignore_index=True) if all_pages else pd.DataFrame()


if __name__ == "__main__":
       token = get_token()
       df = fetch_events(token, country="Yemen", year=2024)
       print(f"Got {len(df)} events total.")
