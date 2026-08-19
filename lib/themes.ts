import type { ThemeId } from "./types";

/**
 * Mirrors research/universe.py. If you change a theme's membership there,
 * change it here too. The unit test `test_every_theme_member_is_in_the_universe`
 * guards the Python side; `npm run check` guards that the artifact only
 * contains theme ids that appear below.
 */
export const THEME_ORDER: ThemeId[] = ["mena", "eastern_europe", "east_asia", "south_central_asia", "sub_saharan", "latin_america", "oil_supply", "global"] as ThemeId[];

/**
 * Partition themes are disjoint and cover the whole universe, so their effects
 * can be summed. Overlay themes cut across regions and are displayed but never
 * added to a total, or a country would be counted twice.
 */
export const PARTITION_THEMES: ThemeId[] = ["mena", "eastern_europe", "east_asia", "south_central_asia", "sub_saharan", "latin_america"] as ThemeId[];

export const THEMES: Record<
  ThemeId,
  { label: string; blurb: string; partition: boolean; countries: string[] }
> = {
  mena: {
    label: "Middle East & North Africa",
    blurb: "Gulf producers, the Levant and North Africa.",
    partition: true,
    countries: ["Saudi Arabia", "Iran", "Iraq", "United Arab Emirates", "Kuwait", "Qatar", "Oman", "Bahrain", "Yemen", "Israel", "Palestine", "Lebanon", "Syria", "Jordan", "Turkey", "Egypt", "Libya", "Algeria", "Tunisia", "Morocco"],
  },
  eastern_europe: {
    label: "Eastern Europe",
    blurb: "The Russia/Ukraine theatre and its immediate neighbours.",
    partition: true,
    countries: ["Ukraine", "Russia", "Belarus", "Moldova"],
  },
  east_asia: {
    label: "East & Southeast Asia",
    blurb: "Taiwan Strait, Korean peninsula, South China Sea, Myanmar.",
    partition: true,
    countries: ["China", "Taiwan", "North Korea", "South Korea", "Philippines", "Indonesia", "Myanmar"],
  },
  south_central_asia: {
    label: "South & Central Asia",
    blurb: "Afghanistan, Pakistan, India and the Caspian.",
    partition: true,
    countries: ["Pakistan", "Afghanistan", "India", "Kazakhstan", "Azerbaijan", "Armenia"],
  },
  sub_saharan: {
    label: "Sub-Saharan Africa",
    blurb: "Sahel, Horn of Africa, Nigeria and the Congo basin.",
    partition: true,
    countries: ["Nigeria", "Angola", "Sudan", "Ethiopia", "Somalia", "Mali", "Niger", "Burkina Faso", "Chad", "Democratic Republic of Congo", "Mozambique"],
  },
  latin_america: {
    label: "Latin America",
    blurb: "Mexico, the Andes and Brazil.",
    partition: true,
    countries: ["Mexico", "Colombia", "Brazil", "Venezuela"],
  },
  oil_supply: {
    label: "Oil supply",
    blurb: "Producers and chokepoints, cutting across regions.",
    partition: false,
    countries: ["Saudi Arabia", "Iran", "Iraq", "United Arab Emirates", "Kuwait", "Qatar", "Oman", "Libya", "Algeria", "Nigeria", "Venezuela", "Kazakhstan", "Angola", "Yemen"],
  },
  global: {
    label: "Global",
    blurb: "Every country in the universe, aggregated.",
    partition: false,
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
  mena: "var(--series-1)",
  eastern_europe: "var(--series-2)",
  east_asia: "var(--series-3)",
  south_central_asia: "var(--series-4)",
  sub_saharan: "var(--series-5)",
  latin_america: "var(--series-6)",
  oil_supply: "var(--series-7)",
  global: "var(--series-8)",
};

/** Severity bands for individual events. Status colors, always with a label. */
export const SEVERITY_BANDS = [
  { min: 20, label: "20+ killed", varName: "var(--status-critical)" },
  { min: 5, label: "5-19 killed", varName: "var(--status-serious)" },
  { min: 1, label: "1-4 killed", varName: "var(--status-warning)" },
  { min: 0, label: "No deaths recorded", varName: "var(--text-muted)" },
];
