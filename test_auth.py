import os
import requests
from dotenv import load_dotenv

load_dotenv()

email = os.getenv("ACLED_EMAIL")
password = os.getenv("ACLED_PASSWORD")

if not (email and password):
    raise RuntimeError("Missing credentials in emv file")

response = requests.post(
    "    ""https://acleddata.com/oauth/token",
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
token = response.json()["access_token"]
print(f"Auth worked. Token starts with {token[:12]}...")
