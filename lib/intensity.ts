import { THEMES } from "./themes";
import type { CountryMonthly, ThemeId } from "./types";

/** Must match research/universe.py FATALITY_WEIGHT. */
export const FATALITY_WEIGHT = 3;

export interface ThemeSeries {
  months: string[];
  /** log1p severity per month, same units as the model's level series */
  level: number[];
  /** raw event count per month, for a readable tooltip */
  events: number[];
}

/**
 * Mirrors research/intensity.py: severity is events plus weighted fatalities,
 * summed over the theme's member countries and log-damped. The chart shows the
 * level rather than the z-score because a level is something a reader can sanity
 * check against the map; the z-score is shown separately as a single chip.
 */
export function themeSeries(panel: CountryMonthly, theme: ThemeId): ThemeSeries {
  const members =
    theme === "global"
      ? Object.keys(panel.countries)
      : THEMES[theme].countries.filter((c) => c in panel.countries);

  const n = panel.months.length;
  const severity = new Array<number>(n).fill(0);
  const events = new Array<number>(n).fill(0);

  for (const country of members) {
    const s = panel.countries[country];
    if (!s) continue;
    for (let i = 0; i < n; i++) {
      severity[i] += s.events[i] + FATALITY_WEIGHT * s.fatalities[i];
      events[i] += s.events[i];
    }
  }

  return { months: panel.months, level: severity.map((v) => Math.log1p(v)), events };
}

export function lastMonths<T>(values: T[], count: number): T[] {
  return values.slice(Math.max(0, values.length - count));
}
