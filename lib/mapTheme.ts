/**
 * MapLibre paint properties cannot read CSS custom properties, so the palette
 * values used inside the GL layers are duplicated here as literals. They must
 * stay in sync with app/globals.css.
 */

export const BASEMAP = {
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
} as const;

/** Sequential, one hue. Low end recedes into the surface. */
export const HEAT_RAMP = {
  dark: ["#184f95", "#256abf", "#3987e5", "#86b6ef", "#cde2fb"],
  light: ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95"],
} as const;

/** Status palette, ordered by severity. Always paired with a label in the legend. */
export const SEVERITY_COLORS = {
  none: { dark: "#898781", light: "#898781" },
  low: { dark: "#fab219", light: "#fab219" },
  medium: { dark: "#ec835a", light: "#ec835a" },
  high: { dark: "#d03b3b", light: "#d03b3b" },
} as const;

export const SURFACE = { dark: "#1a1a19", light: "#fcfcfb" } as const;
export const INK = { dark: "#ffffff", light: "#0b0b0b" } as const;

export type Mode = "dark" | "light";
