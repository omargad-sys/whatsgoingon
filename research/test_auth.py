"""Smoke-test ACLED credentials. Run this first after setting up .env.

    cd research && python test_auth.py

If this fails with 401, the account is real but the password is wrong.
If it succeeds but `fetch_events` returns zero rows for every country, the
account is on the Open tier: register with an institutional (.edu) email to get
event-level API access.
"""

import os

import requests
from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in (os.path.join(_HERE, ".env"), os.path.join(_HERE, os.pardir, ".env")):
    if os.path.exists(_candidate):
        load_dotenv(_candidate)
        break
else:
    load_dotenv()

TOKEN_URL = "https://acleddata.com/oauth/token"

email = os.getenv("ACLED_EMAIL")
password = os.getenv("ACLED_PASSWORD")

if not (email and password):
    raise RuntimeError(
        "Missing ACLED_EMAIL / ACLED_PASSWORD. Copy .env.example to .env and fill it in."
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
payload = response.json()
token = payload["access_token"]
print(f"Auth worked. Token starts with {token[:12]}...")
print(f"Expires in {payload.get('expires_in', '?')}s; refresh token issued: {'refresh_token' in payload}")

probe = requests.get(
    "https://acleddata.com/api/acled/read",
    params={"country": "Yemen", "year": 2024, "limit": 1, "_format": "json"},
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
probe.raise_for_status()
body = probe.json()
rows = body.get("data", body) if isinstance(body, dict) else body
if rows:
    print(f"Event-level access confirmed. Sample event_date: {rows[0].get('event_date')}")
else:
    print(
        "Auth works but the event endpoint returned no rows.\n"
        "That usually means Open-tier access (aggregated only). "
        "Re-register with your .edu address to get the Research tier."
    )
