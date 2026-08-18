"""Fetch daily closes for the ticker universe.

    python build_prices.py                 # stooq, falls back to yahoo
    python build_prices.py --provider yahoo
    python build_prices.py --fixture       # no network

Neither provider needs an API key. Both are best-effort public endpoints, so
the script fails loudly rather than silently shipping a short series: a ticker
with fewer than MIN_DAYS observations aborts the build.
"""

import argparse
import datetime as dt
import io
import time

import pandas as pd
import requests

from paths import FIXTURE_DIR, PRICES, ensure_dirs, write_json
from universe import TICKERS

MIN_DAYS = 500  # ~2 trading years; below this the monthly regression is hopeless
START = "2017-06-01"

UA = {"User-Agent": "whatsgoingon/1.0 (github.com/omargad-sys/whatsgoingon)"}


def from_stooq(ticker):
    url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
    r = requests.get(url, headers=UA, timeout=45)
    r.raise_for_status()
    text = r.text.strip()
    if not text.lower().startswith("date"):
        raise RuntimeError(f"stooq returned no data for {ticker}: {text[:80]!r}")
    df = pd.read_csv(io.StringIO(text))
    return pd.DataFrame({"date": pd.to_datetime(df["Date"]), "close": pd.to_numeric(df["Close"])})


def from_yahoo(ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    r = requests.get(
        url,
        params={"range": "10y", "interval": "1d", "events": "div,split"},
        headers=UA,
        timeout=45,
    )
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    stamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]["close"]
    adj = result["indicators"].get("adjclose", [{}])[0].get("adjclose")
    closes = adj if adj else quote
    return pd.DataFrame(
        {
            "date": pd.to_datetime(pd.Series(stamps), unit="s").dt.normalize(),
            "close": pd.to_numeric(pd.Series(closes)),
        }
    )


PROVIDERS = {"stooq": from_stooq, "yahoo": from_yahoo}


def fetch_one(ticker, provider):
    order = [provider] + [p for p in PROVIDERS if p != provider]
    errors = []
    for name in order:
        try:
            df = PROVIDERS[name](ticker)
            df = df.dropna().sort_values("date")
            df = df[df["date"] >= START]
            if len(df) >= MIN_DAYS:
                print(f"  {ticker:<5} {len(df):>5} rows via {name}")
                return df
            errors.append(f"{name}: only {len(df)} rows")
        except Exception as exc:  # noqa: BLE001 - provider failures are expected
            errors.append(f"{name}: {exc}")
    raise SystemExit(f"Could not fetch {ticker}. Tried -> " + "; ".join(errors))


def to_json(frames):
    """Columnar, forward-filled onto a shared date axis. Missing leading values
    stay null so the front end can tell 'not listed yet' from 'flat'."""
    dates = sorted(set().union(*[set(df["date"]) for df in frames.values()]))
    axis = pd.DatetimeIndex(dates)

    out = {}
    for ticker, df in frames.items():
        s = df.set_index("date")["close"].reindex(axis).ffill()
        out[ticker] = [None if pd.isna(v) else round(float(v), 4) for v in s]

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in axis],
        "tickers": out,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS), default="stooq")
    ap.add_argument("--fixture", action="store_true")
    args = ap.parse_args()

    ensure_dirs()

    if args.fixture:
        raw = pd.read_csv(FIXTURE_DIR / "prices_sample.csv")
        raw["date"] = pd.to_datetime(raw["date"])
        frames = {t: g[["date", "close"]].reset_index(drop=True) for t, g in raw.groupby("ticker")}
    else:
        frames = {}
        for ticker in TICKERS:
            frames[ticker] = fetch_one(ticker, args.provider)
            time.sleep(0.6)

    write_json(PRICES, to_json(frames))


if __name__ == "__main__":
    main()
