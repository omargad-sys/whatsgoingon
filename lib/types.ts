export type ThemeId = "oil_supply" | "eastern_europe" | "mena" | "east_asia" | "global";

/** [weekIndex, lon, lat, events, fatalities] */
export type HeatCell = [number, number, number, number, number];

export interface WorldHeat {
  cell_size: number;
  weeks: string[];
  schema: string[];
  cells: HeatCell[];
}

export interface EventProps {
  /** ISO date */
  d: string;
  /** week index into WorldHeat.weeks */
  w: number;
  /** event_type */
  t: string;
  /** sub_event_type */
  s: string;
  /** country */
  c: string;
  /** location */
  l: string;
  /** fatalities */
  f: number;
}

export interface EventFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: EventProps;
}

export interface EventCollection {
  type: "FeatureCollection";
  features: EventFeature[];
}

export interface CountrySeries {
  events: number[];
  fatalities: number[];
  battles: number[];
  protests: number[];
  violence_civilians: number[];
}

export interface CountryMonthly {
  months: string[];
  countries: Record<string, CountrySeries>;
  generated_at: string;
}

export interface SensitivityPair {
  ticker: string;
  theme: ThemeId;
  /** expected same-month return for a +1 sigma shock, e.g. 0.0068 = +68 bps */
  beta: number;
  se: number;
  tstat: number;
  pvalue: number;
  beta_lag: number;
  tstat_lag: number;
  r2: number;
  n: number;
  controlled: boolean;
  passes_tstat: boolean;
  passes_fdr: boolean;
  significant: boolean;
}

export interface Sensitivities {
  generated_at: string;
  tstat_threshold: number;
  fdr_q: number;
  spec: string;
  gate: string;
  sample: { start: string | null; end: string | null; n_pairs: number; n_significant: number };
  current_shock: Partial<Record<ThemeId, number | null>>;
  pairs: SensitivityPair[];
}

export interface Manifest {
  generated_at: string;
  synthetic: boolean;
  window_days: number;
  acled: {
    weeks: number;
    first_week: string | null;
    last_week: string | null;
    grid_cells: number;
    detail_events: number;
    panel_months: number;
    panel_countries: number;
  };
  prices: { tickers: string[]; first_date: string | null; last_date: string | null };
  model: { pairs: number; significant: number; tstat_threshold: number; fdr_q: number };
}

export interface Holding {
  ticker: string;
  /** portfolio weight as a fraction, 0..1 */
  weight: number;
}

export interface ForecastCountry {
  /** probability of escalation in the target month */
  p: number;
  fatalities: number;
  events: number;
  threshold: number;
  ratio: number;
  /** [lon, lat, spread] or null */
  centroid: [number, number, number] | null;
}

export interface Forecast {
  generated_at: string;
  as_of_month: string;
  target_month: string;
  lookahead_months: number;
  threshold_quantile: number;
  /** which predictor actually won the walk-forward comparison */
  source: "model" | "baseline";
  backend: string;
  evaluation: {
    model_roc_auc: number;
    baseline_roc_auc: number;
    margin: number;
    model_brier: number;
    baseline_brier: number;
    calibration_slope: number | null;
    windows: number;
    base_rate: number;
  };
  countries: Record<string, ForecastCountry>;
}

export interface ThemeLink {
  intercept: number;
  slope: number;
  se: number;
  tstat: number;
  pvalue: number;
  r2: number;
  n: number;
  mean_frac: number;
  significant: boolean;
}

export interface Link {
  generated_at: string;
  spec: string;
  tstat_threshold: number;
  themes: Partial<Record<ThemeId, ThemeLink>>;
}
