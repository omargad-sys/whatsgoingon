"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import ChainPanel from "./ChainPanel";
import ExposureTable from "./ExposureTable";
import ImpactBars from "./ImpactBars";
import PortfolioBuilder from "./PortfolioBuilder";
import RiskList from "./RiskList";
import ThemeList from "./ThemeList";
import TimeSlider from "./TimeSlider";
import type { MapFilters } from "./ConflictMap";

import { allThemeImpacts, buildLookup } from "@/lib/exposure";
import { chainAll, chainedTotal, toThemeImpactShape } from "@/lib/chain";
import { SEVERITY_BANDS, THEMES, THEME_ORDER, TICKER_LIST } from "@/lib/themes";
import { HEAT_RAMP } from "@/lib/mapTheme";
import { bps, decodeHoldings, encodeHoldings, relativeAge } from "@/lib/format";
import type {
  CountryMonthly,
  EventCollection,
  Forecast,
  Holding,
  Link,
  Manifest,
  Sensitivities,
  ThemeId,
  WorldHeat,
} from "@/lib/types";

// MapLibre touches `window` at import time, so it can only load in the browser.
const ConflictMap = dynamic(() => import("./ConflictMap"), {
  ssr: false,
  loading: () => (
    <div className="map-root" style={{ display: "grid", placeItems: "center" }}>
      <span className="muted">Loading map…</span>
    </div>
  ),
});

const EVENT_TYPES = [
  "Battles",
  "Explosions/Remote violence",
  "Violence against civilians",
  "Protests",
  "Riots",
];

const DEFAULT_HOLDINGS: Holding[] = [
  { ticker: "VOO", weight: 0.6 },
  { ticker: "XLE", weight: 0.2 },
  { ticker: "GLD", weight: 0.2 },
];

interface Props {
  sensitivities: Sensitivities;
  manifest: Manifest;
  forecast: Forecast;
  link: Link;
}

export default function Dashboard({ sensitivities, manifest, forecast, link }: Props) {
  const params = useSearchParams();

  const [heat, setHeat] = useState<WorldHeat | null>(null);
  const [events, setEvents] = useState<EventCollection | null>(null);
  const [panel, setPanel] = useState<CountryMonthly | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [holdings, setHoldings] = useState<Holding[]>(
    () => decodeHoldings(params.get("p"), TICKER_LIST) ?? DEFAULT_HOLDINGS,
  );
  const [theme, setTheme] = useState<ThemeId>(() => {
    const t = params.get("t") as ThemeId | null;
    return t && THEME_ORDER.includes(t) ? t : "oil_supply";
  });

  const [week, setWeek] = useState(0);
  const [windowWeeks, setWindowWeeks] = useState(4);
  const [types, setTypes] = useState<string[]>([]);
  const [minFatalities, setMinFatalities] = useState(0);
  const [mode, setMode] = useState<"dark" | "light">("dark");
  const [focus, setFocus] = useState<[number, number, number] | null>(null);
  const [country, setCountry] = useState<string | null>(null);

  /* --------------------------------------------------------------- data */

  useEffect(() => {
    let cancelled = false;
    const grab = async <T,>(path: string): Promise<T> => {
      const res = await fetch(path);
      if (!res.ok) throw new Error(`${path} returned ${res.status}`);
      return (await res.json()) as T;
    };

    Promise.all([
      grab<WorldHeat>("/data/world-heat.json"),
      grab<EventCollection>("/data/events-top.geojson"),
      grab<CountryMonthly>("/data/country-monthly.json"),
    ])
      .then(([h, e, p]) => {
        if (cancelled) return;
        setHeat(h);
        setEvents(e);
        setPanel(p);
        setWeek(Math.max(0, h.weeks.length - 1));
      })
      .catch((err: Error) => !cancelled && setLoadError(err.message));

    return () => {
      cancelled = true;
    };
  }, []);

  /* ---------------------------------------------------------- url state */

  // history.replaceState rather than router.replace: this is presentation state,
  // not a navigation. Going through the Next router would re-render the route on
  // every keystroke in a weight field, and Safari rate-limits rapid history
  // writes, hence the debounce.
  useEffect(() => {
    const id = setTimeout(() => {
      const next = new URLSearchParams();
      const encoded = encodeHoldings(holdings);
      if (encoded) next.set("p", encoded);
      if (theme !== "oil_supply") next.set("t", theme);
      const qs = next.toString();
      window.history.replaceState(null, "", qs ? `/?${qs}` : "/");
    }, 300);
    return () => clearTimeout(id);
  }, [holdings, theme]);

  /* ------------------------------------------------------------- model */

  const lookup = useMemo(() => buildLookup(sensitivities), [sensitivities]);
  const allCountries = useMemo(() => Object.keys(forecast.countries), [forecast]);

  // Per-sigma sensitivities, for the "what would a 1 sigma shock do" panel.
  const perSigma = useMemo(
    () => allThemeImpacts(holdings, THEME_ORDER, lookup),
    [holdings, lookup],
  );

  // The chained view: forecast -> implied shock -> expected return.
  const chained = useMemo(
    () => chainAll(holdings, THEME_ORDER, lookup, forecast, link, allCountries),
    [holdings, lookup, forecast, link, allCountries],
  );
  const selectedChain = useMemo(
    () => chained.find((i) => i.theme === theme) ?? chained[0],
    [chained, theme],
  );
  const selectedImpact = useMemo(
    () => (selectedChain ? toThemeImpactShape(selectedChain) : undefined),
    [selectedChain],
  );
  const forecastTotal = useMemo(() => chainedTotal(chained), [chained]);

  /* -------------------------------------------------------------- map */

  const probabilities = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(forecast.countries).map(([name, v]) => [name, v.p]),
      ),
    [forecast],
  );

  const filters: MapFilters = useMemo(
    () => ({
      from: Math.max(0, week - (windowWeeks - 1)),
      to: week,
      types,
      minFatalities,
    }),
    [week, windowWeeks, types, minFatalities],
  );

  // Selecting from either side drives the same state, so the map and the risk
  // list can never disagree about what is selected.
  const onSelectCountry = useCallback(
    (name: string, centroid: [number, number, number] | null) => {
      setCountry((prev) => (prev === name ? null : name));
      if (centroid) setFocus(centroid);
    },
    [],
  );

  const onSelectTheme = useCallback((t: ThemeId) => {
    setTheme(t);
    // Rough framing for the theme's region. Deliberately approximate: the point
    // is to get the reader looking at the right part of the world.
    const framing: Record<ThemeId, [number, number, number] | null> = {
      oil_supply: [45, 22, 18],
      eastern_europe: [33, 49, 9],
      mena: [38, 31, 12],
      east_asia: [118, 28, 16],
      global: null,
    };
    setFocus(framing[t]);
  }, []);

  const toggleType = (t: string) =>
    setTypes((prev) => (prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]));

  const visibleEvents = useMemo(() => {
    if (!events) return 0;
    const allow = types.length ? new Set(types) : null;
    return events.features.filter(
      (f) =>
        f.properties.w >= filters.from &&
        f.properties.w <= filters.to &&
        f.properties.f >= minFatalities &&
        (!allow || allow.has(f.properties.t)),
    ).length;
  }, [events, filters, types, minFatalities]);

  /* ------------------------------------------------------------ render */

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <h1>What&apos;s Going On</h1>
          <span className="tag">
            Conflict events from ACLED, overlaid on a portfolio of index and sector ETFs
          </span>
        </div>
        <span className="spacer" />
        <nav>
          <button
            type="button"
            className="pill"
            onClick={() => {
              const next = mode === "dark" ? "light" : "dark";
              setMode(next);
              document.documentElement.dataset.theme = next;
            }}
          >
            {mode === "dark" ? "Light" : "Dark"}
          </button>
          <a className="pill" href="/methodology">
            Methodology
          </a>
        </nav>
      </header>

      {manifest.synthetic && (
        <div className="banner" role="status">
          <strong>Synthetic data.</strong> This build was made from generated fixtures, not
          from ACLED. Every number on this page is fake.
        </div>
      )}

      {loadError && (
        <div className="banner" role="alert">
          <strong>Could not load map data.</strong> {loadError}
        </div>
      )}

      <div className="body">
        <div className="map-pane">
          <ConflictMap
            heat={heat}
            events={events}
            filters={filters}
            mode={mode}
            focus={focus}
            highlight={country}
            probabilities={probabilities}
            onPickCountry={(c: string) =>
              onSelectCountry(c, forecast.countries[c]?.centroid ?? null)
            }
          />

          <div className="map-overlay filters">
            {EVENT_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                className="pill"
                aria-pressed={types.includes(t)}
                onClick={() => toggleType(t)}
              >
                {t.replace("Explosions/Remote violence", "Explosions")}
              </button>
            ))}
            <button
              type="button"
              className="pill"
              aria-pressed={minFatalities > 0}
              onClick={() => setMinFatalities((v) => (v > 0 ? 0 : 1))}
            >
              Fatal only
            </button>
          </div>

          <div className="map-overlay legend">
            <div className="legend-title">Event density</div>
            <div className="legend-ramp">
              {HEAT_RAMP[mode].map((c) => (
                <span key={c} style={{ background: c }} />
              ))}
            </div>
            <div className="legend-scale">
              <span>fewer</span>
              <span>more</span>
            </div>

            <div className="legend-title" style={{ marginTop: 12 }}>
              Individual events
            </div>
            {SEVERITY_BANDS.map((b) => (
              <div className="legend-row" key={b.label}>
                <span className="legend-dot" style={{ background: b.varName }} />
                <span>{b.label}</span>
              </div>
            ))}
            <div className="legend-row muted" style={{ marginTop: 8, fontSize: 11 }}>
              {visibleEvents.toLocaleString()} events shown
            </div>
          </div>

          {heat && (
            <TimeSlider
              weeks={heat.weeks}
              value={week}
              windowWeeks={windowWeeks}
              onChange={setWeek}
              onWindowChange={setWindowWeeks}
            />
          )}
        </div>

        <aside className="side">
          <section className="section">
            <h2>Right now</h2>
            <div className="stat-row">
              <div className="stat">
                <div className="k">Portfolio, {forecast.target_month.slice(0, 7)}</div>
                <div className="v">
                  {forecastTotal.themesCounted === 0 ? (
                    <span className="null-note" style={{ fontSize: 13 }}>
                      not identified
                    </span>
                  ) : (
                    bps(forecastTotal.value)
                  )}
                </div>
              </div>
              <div className="stat">
                <div className="k">{THEMES[theme].label}</div>
                <div className="v small">
                  {!selectedChain || selectedChain.empty ? (
                    <span className="null-note" style={{ fontSize: 13 }}>
                      not identified
                    </span>
                  ) : (
                    bps(selectedChain.expectedReturn)
                  )}
                </div>
              </div>
            </div>
            <p className="hint" style={{ marginBottom: 0 }}>
              Expected return for {forecast.target_month.slice(0, 7)}, from conflict
              escalation risk alone, summed over regional themes. This is a conditional
              estimate, not a price target, and not investment advice. Conflict data as
              of {forecast.as_of_month.slice(0, 7)}, refreshed{" "}
              {relativeAge(manifest.generated_at)}.
            </p>
          </section>

          <section className="section">
            <h2>Escalation forecast · {forecast.target_month.slice(0, 7)}</h2>
            {country && (
              <p style={{ margin: "0 0 10px" }}>
                <span className="selection-chip">
                  {country}
                  <button
                    type="button"
                    onClick={() => setCountry(null)}
                    aria-label={`Clear ${country} selection`}
                  >
                    ×
                  </button>
                </span>
              </p>
            )}
            <RiskList forecast={forecast} onSelect={onSelectCountry} selected={country} />
          </section>

          <section className="section">
            <h2>Conflict themes</h2>
            <ThemeList
              panel={panel}
              currentShock={sensitivities.current_shock}
              selected={theme}
              onSelect={onSelectTheme}
            />
          </section>

          <section className="section">
            <h2>Your portfolio</h2>
            <p className="hint">
              Weights are renormalised to 100%. The URL updates as you edit, so the link
              is shareable.
            </p>
            <PortfolioBuilder holdings={holdings} onChange={setHoldings} />
          </section>

          <section className="section">
            <h2>How {THEMES[theme].label} reaches your portfolio</h2>
            {selectedChain && (
              <ChainPanel impact={selectedChain} forecast={forecast} link={link} />
            )}
          </section>

          <section className="section">
            <h2>Sensitivity per +1σ shock</h2>
            <p className="hint">
              The middle layer on its own: what a one standard deviation escalation would
              do, independent of how likely one is.
            </p>
            <ImpactBars impacts={perSigma} hasHoldings={holdings.length > 0} />
          </section>

          <section className="section">
            <h2>By holding</h2>
            {selectedImpact && (
              <ExposureTable
                impact={selectedImpact}
                themes={THEME_ORDER}
                onThemeChange={onSelectTheme}
              />
            )}
          </section>

          <footer className="footer">
            <p style={{ margin: "0 0 8px" }}>
              Conflict data from the Armed Conflict Location &amp; Event Data Project
              (ACLED), <a href="https://acleddata.com">acleddata.com</a>. Used under
              ACLED&apos;s terms; this is a non-commercial research project and
              redistributes only aggregates, never raw event data.
            </p>
            <p style={{ margin: 0 }}>
              Escalation forecast by the{" "}
              {forecast.source === "model" ? "gradient-boosted model" : "persistence baseline"}{" "}
              (ROC-AUC {forecast.evaluation[forecast.source === "model" ? "model_roc_auc" : "baseline_roc_auc"].toFixed(3)}
              ). {Object.values(link.themes).filter((t) => t?.significant).length} of{" "}
              {Object.keys(link.themes).length} theme links and{" "}
              {sensitivities.sample.n_significant} of {sensitivities.sample.n_pairs}{" "}
              ticker-theme relationships are statistically identified. Nothing here is
              investment advice.
            </p>
          </footer>
        </aside>
      </div>
    </div>
  );
}
