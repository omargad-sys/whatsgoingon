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
    "Qatar", "Oman", "Bahrain", "Yemen",
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

# Two kinds of theme, and the distinction is load-bearing.
#
# PARTITION themes carve the universe into disjoint regions. Every country
# belongs to exactly one, so their effects can be summed into a portfolio total
# without counting any country twice.
#
# OVERLAY themes cut across regions (oil supply spans the Gulf and Africa and
# Latin America; global is everything). They are estimated and displayed, but
# never added to the total, because doing so would count Iran once as a Gulf
# producer and again as a MENA country.
#
# The earlier version had no such distinction: Iran, Iraq and Yemen were in both
# oil_supply and mena, so the headline silently overstated them. And only 30 of
# 52 countries belonged to any theme at all, so escalation in Mozambique or
# Mexico could top the risk list while being structurally unable to move a
# single portfolio number.
THEMES = {
    "mena": {
        "label": "Middle East & North Africa",
        "blurb": "Gulf producers, the Levant and North Africa.",
        "partition": True,
        "countries": [
            "Saudi Arabia", "Iran", "Iraq", "United Arab Emirates", "Kuwait",
            "Qatar", "Oman", "Bahrain", "Yemen", "Israel", "Palestine",
            "Lebanon", "Syria", "Jordan", "Turkey", "Egypt", "Libya",
            "Algeria", "Tunisia", "Morocco",
        ],
    },
    "eastern_europe": {
        "label": "Eastern Europe",
        "blurb": "The Russia/Ukraine theatre and its immediate neighbours.",
        "partition": True,
        "countries": ["Ukraine", "Russia", "Belarus", "Moldova"],
    },
    "east_asia": {
        "label": "East & Southeast Asia",
        "blurb": "Taiwan Strait, Korean peninsula, South China Sea, Myanmar.",
        "partition": True,
        "countries": [
            "China", "Taiwan", "North Korea", "South Korea", "Philippines",
            "Indonesia", "Myanmar",
        ],
    },
    "south_central_asia": {
        "label": "South & Central Asia",
        "blurb": "Afghanistan, Pakistan, India and the Caspian.",
        "partition": True,
        "countries": [
            "Pakistan", "Afghanistan", "India", "Kazakhstan", "Azerbaijan", "Armenia",
        ],
    },
    "sub_saharan": {
        "label": "Sub-Saharan Africa",
        "blurb": "Sahel, Horn of Africa, Nigeria and the Congo basin.",
        "partition": True,
        "countries": [
            "Nigeria", "Angola", "Sudan", "Ethiopia", "Somalia", "Mali",
            "Niger", "Burkina Faso", "Chad", "Democratic Republic of Congo",
            "Mozambique",
        ],
    },
    "latin_america": {
        "label": "Latin America",
        "blurb": "Mexico, the Andes and Brazil.",
        "partition": True,
        "countries": ["Mexico", "Colombia", "Brazil", "Venezuela"],
    },

    # --- overlays: displayed, never summed ---
    "oil_supply": {
        "label": "Oil supply",
        "blurb": "Producers and chokepoints, cutting across regions.",
        "partition": False,
        "countries": [
            "Saudi Arabia", "Iran", "Iraq", "United Arab Emirates", "Kuwait",
            "Qatar", "Oman", "Libya", "Algeria", "Nigeria", "Venezuela",
            "Kazakhstan", "Angola", "Yemen",
        ],
    },
    "global": {
        "label": "Global",
        "blurb": "Every country in the universe, aggregated.",
        "partition": False,
        "countries": list(COUNTRIES),
    },
}

PARTITION_THEMES = [t for t, m in THEMES.items() if m["partition"]]
OVERLAY_THEMES = [t for t, m in THEMES.items() if not m["partition"]]

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
