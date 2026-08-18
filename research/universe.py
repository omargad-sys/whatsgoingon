"""Country universe and theme membership.

Country strings must match ACLED's `country` field exactly. If a name is wrong
the fetch silently returns zero rows, so `verify_universe.py` cross-checks these
against what the API actually returns before a full pull.
"""

# Market-relevant countries. Deliberately not all ~230: the ACLED pull is
# country-year paginated, so every extra country costs real API calls, and
# countries with no plausible transmission channel to a US-listed ETF only add
# noise to the intensity indices.
COUNTRIES = [
    # Gulf / oil
    "Saudi Arabia", "Iran", "Iraq", "United Arab Emirates", "Kuwait",
    "Qatar", "Oman", "Bahrain",
    # North Africa / oil
    "Libya", "Algeria", "Egypt", "Tunisia", "Morocco",
    # Other major producers
    "Nigeria", "Venezuela", "Kazakhstan", "Angola",
    # Levant
    "Israel", "Palestine", "Lebanon", "Syria", "Jordan", "Turkey",
    # Eastern Europe
    "Ukraine", "Russia", "Belarus", "Moldova",
    # South / Central Asia
    "Pakistan", "Afghanistan", "India", "Azerbaijan", "Armenia",
    # East Asia
    "China", "Taiwan", "North Korea", "South Korea", "Philippines", "Indonesia",
    # Sub-Saharan
    "Sudan", "Ethiopia", "Somalia", "Mali", "Niger", "Burkina Faso",
    "Chad", "Democratic Republic of Congo", "Mozambique",
    # Latin America
    "Mexico", "Colombia", "Brazil",
    # Southeast Asia
    "Myanmar",
]

# A theme is a basket of countries whose conflict intensity is summed into one
# index. Themes exist because no single country's violence moves a US ETF, but a
# region-wide supply shock plausibly does.
THEMES = {
    "oil_supply": {
        "label": "Oil supply",
        "blurb": "Producers and chokepoints whose disruption feeds through to crude.",
        "countries": [
            "Saudi Arabia", "Iran", "Iraq", "United Arab Emirates", "Kuwait",
            "Qatar", "Oman", "Libya", "Algeria", "Nigeria", "Venezuela",
            "Kazakhstan", "Angola", "Yemen",
        ],
    },
    "eastern_europe": {
        "label": "Eastern Europe",
        "blurb": "Russia/Ukraine theatre and its immediate neighbours.",
        "countries": ["Ukraine", "Russia", "Belarus", "Moldova"],
    },
    "mena": {
        "label": "Middle East & North Africa",
        "blurb": "Levant and Gulf political violence, broadly defined.",
        "countries": [
            "Israel", "Palestine", "Lebanon", "Syria", "Egypt", "Jordan",
            "Turkey", "Iran", "Iraq", "Yemen",
        ],
    },
    "east_asia": {
        "label": "East Asia",
        "blurb": "Taiwan Strait, Korean peninsula, South China Sea.",
        "countries": ["China", "Taiwan", "North Korea", "South Korea", "Philippines"],
    },
    "global": {
        "label": "Global",
        "blurb": "Every country in the universe, aggregated.",
        "countries": list(COUNTRIES),
    },
}

# "Yemen" sits in oil_supply for the Red Sea / Bab el-Mandeb channel even though
# its own production is negligible.
if "Yemen" not in COUNTRIES:
    COUNTRIES.append("Yemen")

TICKERS = {
    "VOO": {"label": "Vanguard S&P 500", "group": "broad"},
    "VTI": {"label": "Vanguard Total US Market", "group": "broad"},
    "SPY": {"label": "SPDR S&P 500", "group": "broad"},
    "XLE": {"label": "Energy Select Sector", "group": "energy"},
    "USO": {"label": "US Oil Fund", "group": "energy"},
    "ITA": {"label": "iShares Aerospace & Defense", "group": "defense"},
    "XAR": {"label": "SPDR Aerospace & Defense", "group": "defense"},
    "GLD": {"label": "SPDR Gold Shares", "group": "haven"},
    "UUP": {"label": "Invesco Dollar Bullish", "group": "haven"},
    "VIXY": {"label": "ProShares VIX Short-Term", "group": "volatility"},
}

# SPY is the market control in every non-broad regression, so it is never
# itself regressed with a control.
BROAD_TICKERS = [t for t, m in TICKERS.items() if m["group"] == "broad"]

# Fatalities are weighted above raw event counts: a fatal engagement is a
# stronger signal of escalation than a protest. The index is then log-damped so
# that Ukraine 2022 does not single-handedly define the scale.
FATALITY_WEIGHT = 3.0

# Rolling window for z-scoring the intensity index, in months.
ZSCORE_WINDOW = 36

# Below this |t| we refuse to print a number. See lib/exposure.ts for the
# matching rule on the front end.
TSTAT_THRESHOLD = 2.0

YEARS = list(range(2018, 2027))


def theme_ids():
    return list(THEMES.keys())


def countries_for(theme_id):
    return THEMES[theme_id]["countries"]
