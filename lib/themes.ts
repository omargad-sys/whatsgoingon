import type { ThemeId } from "./types";

/**
 * Mirrors research/universe.py. If you change a theme's membership there,
 * change it here too. The unit test `test_every_theme_member_is_in_the_universe`
 * guards the Python side; `npm run check` guards that the artifact only
 * contains theme ids that appear below.
 */
export const THEME_ORDER: ThemeId[] = [
  "oil_supply",
  "eastern_europe",
  "mena",
  "east_asia",
  "global",
];

export const THEMES: Record<ThemeId, { label: string; blurb: string; countries: string[] }> = {
  oil_supply: {
    label: "Oil supply",
    blurb: "Producers and chokepoints whose disruption feeds through to crude.",
    countries: [
      "Saudi Arabia", "Iran", "Iraq", "United Arab Emirates", "Kuwait", "Qatar",
      "Oman", "Libya", "Algeria", "Nigeria", "Venezuela", "Kazakhstan", "Angola", "Yemen",
    ],
  },
  eastern_europe: {
    label: "Eastern Europe",
    blurb: "Russia/Ukraine theatre and its immediate neighbours.",
    countries: ["Ukraine", "Russia", "Belarus", "Moldova"],
  },
  mena: {
    label: "Middle East & North Africa",
    blurb: "Levant and Gulf political violence, broadly defined.",
    countries: [
      "Israel", "Palestine", "Lebanon", "Syria", "Egypt", "Jordan",
      "Turkey", "Iran", "Iraq", "Yemen",
    ],
  },
  east_asia: {
    label: "East Asia",
    blurb: "Taiwan Strait, Korean peninsula, South China Sea.",
    countries: ["China", "Taiwan", "North Korea", "South Korea", "Philippines"],
  },
  global: {
    label: "Global",
    blurb: "Every country in the universe, aggregated.",
    countries: [],
  },
};

export const TICKERS: Record<string, { label: string; group: string }> = {
  VOO: { label: "Vanguard S&P 500", group: "Broad US" },
  VTI: { label: "Vanguard Total US Market", group: "Broad US" },
  SPY: { label: "SPDR S&P 500", group: "Broad US" },
  XLE: { label: "Energy Select Sector", group: "Energy" },
  USO: { label: "US Oil Fund", group: "Energy" },
  ITA: { label: "iShares Aerospace & Defense", group: "Defense" },
  XAR: { label: "SPDR Aerospace & Defense", group: "Defense" },
  GLD: { label: "SPDR Gold Shares", group: "Haven" },
  UUP: { label: "Invesco Dollar Bullish", group: "Haven" },
  VIXY: { label: "ProShares VIX Short-Term", group: "Volatility" },
};

export const TICKER_LIST = Object.keys(TICKERS);

/** Categorical slots in fixed order. Never cycled: a 6th theme is not a hue. */
export const THEME_COLOR_VAR: Record<ThemeId, string> = {
  oil_supply: "var(--series-1)",
  eastern_europe: "var(--series-2)",
  mena: "var(--series-3)",
  east_asia: "var(--series-4)",
  global: "var(--series-5)",
};

/** Severity bands for individual events. Status colors, always with a label. */
export const SEVERITY_BANDS = [
  { min: 20, label: "20+ killed", varName: "var(--status-critical)" },
  { min: 5, label: "5-19 killed", varName: "var(--status-serious)" },
  { min: 1, label: "1-4 killed", varName: "var(--status-warning)" },
  { min: 0, label: "No deaths recorded", varName: "var(--text-muted)" },
];
