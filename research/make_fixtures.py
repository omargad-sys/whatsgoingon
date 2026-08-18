"""Generate SYNTHETIC fixtures so the whole pipeline runs without credentials.

    python make_fixtures.py

Writes:
  fixtures/events_sample.csv   ~180 days of fake events, ACLED column shape
  fixtures/panel_sample.csv    2018-01 -> now country-month panel
  fixtures/prices_sample.csv   daily closes for the ticker universe

These are NOT ACLED data. Volumes and seasonality are calibrated against the
real 5-country panel that already lives in this repo so the artifacts are
realistically sized, but every row is generated. Nothing here may be presented
as a finding, and the manifest marks any build made from fixtures as synthetic.

The prices fixture plants a known relationship (oil-supply conflict -> XLE/USO
up, VIXY up, VOO flat) so that `python -m unittest` can assert the regression
recovers the right sign and correctly reports nothing for VOO.
"""

import datetime as dt

import numpy as np
import pandas as pd

from geo import CENTROIDS
from paths import FIXTURE_DIR, RESEARCH_DIR, ensure_dirs
from universe import COUNTRIES, THEMES, TICKERS

SEED = 20260818
EVENT_TYPES = [
    ("Battles", ["Armed clash", "Government regains territory"]),
    ("Explosions/Remote violence", ["Air/drone strike", "Shelling/artillery/missile attack", "Remote explosive/landmine/IED"]),
    ("Violence against civilians", ["Attack", "Abduction/forced disappearance"]),
    ("Protests", ["Peaceful protest", "Protest with intervention"]),
    ("Riots", ["Violent demonstration", "Mob violence"]),
    ("Strategic developments", ["Arrests", "Looting/property destruction"]),
]
TYPE_WEIGHTS = [0.22, 0.16, 0.18, 0.28, 0.10, 0.06]


def _country_scale():
    """Per-country monthly event volume, anchored on the real panel where we
    have it and drawn from a plausible spread where we do not."""
    real = pd.read_csv(RESEARCH_DIR / "monthly_panel_full.csv")
    anchors = real.groupby("country")["num_events"].mean().to_dict()

    rng = np.random.default_rng(SEED)
    scale = {}
    for c in COUNTRIES:
        if c in anchors:
            scale[c] = float(anchors[c])
        else:
            # Log-uniform between ~40 and ~1500 events/month.
            scale[c] = float(np.exp(rng.uniform(np.log(40), np.log(1500))))
    return scale


def make_panel(scale, start="2018-01-01"):
    rng = np.random.default_rng(SEED + 1)
    months = pd.date_range(start, pd.Timestamp(dt.date.today()).to_period("M").to_timestamp(), freq="MS")

    rows = []
    for c in COUNTRIES:
        base = scale[c]
        # Slow-moving regime component so the intensity index has real
        # persistence rather than being white noise.
        regime = np.cumsum(rng.normal(0, 0.09, len(months)))
        regime -= regime.mean()
        level = base * np.exp(regime)
        events = rng.poisson(np.maximum(level, 1))

        lethality = np.exp(rng.normal(-0.6, 0.5))
        fatal = rng.poisson(np.maximum(events * lethality, 0.1))

        for i, m in enumerate(months):
            n = int(events[i])
            b = int(n * 0.22)
            p = int(n * 0.28)
            v = int(n * 0.18)
            rows.append(
                {
                    "country": c,
                    "year_month": m.strftime("%Y-%m-%d"),
                    "num_events": n,
                    "total_fatalities": int(fatal[i]),
                    "battles": b,
                    "protests": p,
                    "violence_civilians": v,
                }
            )
    return pd.DataFrame(rows)


def make_events(scale, days=180):
    rng = np.random.default_rng(SEED + 2)
    end = pd.Timestamp(dt.date.today())
    start = end - pd.Timedelta(days=days)
    span_days = (end - start).days

    rows = []
    for c in COUNTRIES:
        lon0, lat0, spread = CENTROIDS[c]
        n = int(scale[c] * days / 30.0)
        n = max(5, min(n, 6000))

        # Cluster events around a handful of hotspots per country instead of a
        # uniform blob, so the heatmap looks like conflict rather than fog.
        k = max(1, int(np.sqrt(n) / 6))
        hot_lon = lon0 + rng.normal(0, spread * 0.6, k)
        hot_lat = lat0 + rng.normal(0, spread * 0.6, k)
        pick = rng.integers(0, k, n)

        lons = np.clip(hot_lon[pick] + rng.normal(0, spread * 0.25, n), -179.9, 179.9)
        lats = np.clip(hot_lat[pick] + rng.normal(0, spread * 0.25, n), -85.0, 85.0)

        offsets = rng.integers(0, span_days + 1, n)
        ti = rng.choice(len(EVENT_TYPES), n, p=TYPE_WEIGHTS)
        fat = rng.poisson(0.7, n) * (rng.random(n) < 0.45)

        for i in range(n):
            etype, subs = EVENT_TYPES[ti[i]]
            d = (start + pd.Timedelta(days=int(offsets[i]))).strftime("%Y-%m-%d")
            rows.append(
                {
                    "event_id_cnty": f"SYN{c[:3].upper()}{i}",
                    "event_date": d,
                    "year": int(d[:4]),
                    "disorder_type": "Political violence" if ti[i] < 3 else "Demonstrations",
                    "event_type": etype,
                    "sub_event_type": subs[rng.integers(0, len(subs))],
                    "actor1": "Synthetic Actor A",
                    "actor2": "Synthetic Actor B",
                    "country": c,
                    "admin1": "Synthetic Region",
                    "location": "Synthetic Location",
                    "latitude": round(float(lats[i]), 4),
                    "longitude": round(float(lons[i]), 4),
                    "fatalities": int(fat[i]),
                }
            )
    return pd.DataFrame(rows)


def make_prices(panel):
    """Daily closes with a planted conflict sensitivity.

    Monthly oil-supply intensity shocks are pushed into XLE/USO/VIXY (positive)
    and GLD (positive, weaker). VOO/VTI/SPY get market noise only, so the
    regression must report 'no detectable relationship' for them. If a future
    change breaks that, the unit test fails loudly.
    """
    rng = np.random.default_rng(SEED + 3)

    p = panel.copy()
    p["year_month"] = pd.to_datetime(p["year_month"])
    oil = p[p["country"].isin(THEMES["oil_supply"]["countries"])]
    idx = oil.groupby("year_month")["num_events"].sum()
    shock = np.log1p(idx).diff().fillna(0.0)
    shock = (shock - shock.mean()) / (shock.std() or 1.0)

    days = pd.bdate_range(p["year_month"].min(), pd.Timestamp(dt.date.today()))
    month_of = days.to_period("M").to_timestamp()
    shock_daily = pd.Series(month_of, index=days).map(shock).fillna(0.0).to_numpy()

    market = rng.normal(0.0004, 0.010, len(days))

    planted = {
        "VOO": (0.000, 1.00), "VTI": (0.000, 1.02), "SPY": (0.000, 1.00),
        "XLE": (0.0060, 1.10), "USO": (0.0090, 0.80),
        "ITA": (0.0035, 0.95), "XAR": (0.0032, 1.00),
        "GLD": (0.0025, 0.05), "UUP": (0.0008, -0.10),
        "VIXY": (0.0140, -3.00),
    }

    frames = []
    for ticker in TICKERS:
        beta_shock, beta_mkt = planted[ticker]
        # The monthly shock is spread across ~21 trading days.
        r = beta_mkt * market + (beta_shock / 21.0) * shock_daily + rng.normal(0, 0.006, len(days))
        close = 100.0 * np.exp(np.cumsum(r))
        frames.append(
            pd.DataFrame({"date": days.strftime("%Y-%m-%d"), "ticker": ticker, "close": close.round(4)})
        )
    return pd.concat(frames, ignore_index=True)


def main():
    ensure_dirs()
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    scale = _country_scale()

    panel = make_panel(scale)
    panel.to_csv(FIXTURE_DIR / "panel_sample.csv", index=False)
    print(f"  panel_sample.csv   {len(panel):,} rows")

    events = make_events(scale)
    events.to_csv(FIXTURE_DIR / "events_sample.csv", index=False)
    print(f"  events_sample.csv  {len(events):,} rows")

    prices = make_prices(panel)
    prices.to_csv(FIXTURE_DIR / "prices_sample.csv", index=False)
    print(f"  prices_sample.csv  {len(prices):,} rows")

    (FIXTURE_DIR / "README.md").write_text(
        "# Synthetic fixtures\n\n"
        "Generated by `make_fixtures.py`. These are NOT ACLED data and NOT real\n"
        "market prices. They exist so the pipeline, the regression and the web app\n"
        "can be built and tested without credentials. Any artifact built from them\n"
        "is stamped `\"synthetic\": true` in data/generated/manifest.json.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
