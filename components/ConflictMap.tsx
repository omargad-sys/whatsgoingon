"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, {
  type GeoJSONSource,
  type Map as MapLibreMap,
  type MapLayerMouseEvent,
  type Popup as MapLibrePopup,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { BASEMAP, HEAT_RAMP, INK, SEVERITY_COLORS, SURFACE, type Mode } from "@/lib/mapTheme";
import type { EventCollection, WorldHeat } from "@/lib/types";

const HEAT_SOURCE = "conflict-heat";
const EVENT_SOURCE = "conflict-events";
const HEAT_LAYER = "conflict-heat-layer";
const EVENT_LAYER = "conflict-event-layer";

export interface MapFilters {
  /** inclusive week index range into WorldHeat.weeks */
  from: number;
  to: number;
  /** event_type values to keep; empty means keep everything */
  types: string[];
  minFatalities: number;
}

interface Props {
  heat: WorldHeat | null;
  events: EventCollection | null;
  filters: MapFilters;
  mode: Mode;
  focus?: [number, number, number] | null;
}

type PointCollection = {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: Record<string, number>;
  }[];
};

const EMPTY: PointCollection = { type: "FeatureCollection", features: [] };

function heatToGeoJSON(heat: WorldHeat | null, from: number, to: number): PointCollection {
  if (!heat) return EMPTY;
  const features: PointCollection["features"] = [];
  for (const [week, lon, lat, events, fatalities] of heat.cells) {
    if (week < from || week > to) continue;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: { e: events, f: fatalities },
    });
  }
  return { type: "FeatureCollection", features };
}

function filterEvents(
  events: EventCollection | null,
  { from, to, types, minFatalities }: MapFilters,
): EventCollection {
  if (!events) return { type: "FeatureCollection", features: [] };
  const allow = types.length ? new Set(types) : null;
  return {
    type: "FeatureCollection",
    features: events.features.filter((f) => {
      const p = f.properties;
      if (p.w < from || p.w > to) return false;
      if (p.f < minFatalities) return false;
      if (allow && !allow.has(p.t)) return false;
      return true;
    }),
  };
}

/** Build the popup with DOM nodes rather than an HTML string: the text comes
 *  from a third-party feed and must never be parsed as markup. */
function popupNode(p: Record<string, unknown>, mode: Mode): HTMLElement {
  const root = document.createElement("div");
  root.style.font = "13px/1.45 system-ui, -apple-system, sans-serif";
  root.style.color = INK[mode];
  root.style.maxWidth = "230px";

  const title = document.createElement("div");
  title.style.fontWeight = "620";
  title.style.marginBottom = "2px";
  title.textContent = String(p.s || p.t || "Event");
  root.appendChild(title);

  const where = document.createElement("div");
  where.style.opacity = "0.75";
  where.textContent = [p.l, p.c].filter(Boolean).join(", ");
  root.appendChild(where);

  const when = document.createElement("div");
  when.style.opacity = "0.75";
  const fatal = Number(p.f) || 0;
  when.textContent = `${String(p.d)} · ${fatal === 1 ? "1 fatality" : `${fatal} fatalities`}`;
  root.appendChild(when);

  const type = document.createElement("div");
  type.style.marginTop = "6px";
  type.style.fontSize = "11.5px";
  type.style.opacity = "0.6";
  type.textContent = String(p.t || "");
  root.appendChild(type);

  return root;
}

export default function ConflictMap({ heat, events, filters, mode, focus }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const ready = useRef(false);
  const popup = useRef<MapLibrePopup | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const heatData = useMemo(
    () => heatToGeoJSON(heat, filters.from, filters.to),
    [heat, filters.from, filters.to],
  );
  const eventData = useMemo(() => filterEvents(events, filters), [events, filters]);

  // The 95th percentile of cell density sets the top of the heat scale, so the
  // ramp adapts to the window instead of being permanently saturated by one
  // conflict or permanently dim during a quiet stretch.
  const heatMax = useMemo(() => {
    const counts = heatData.features.map((f) => f.properties.e).sort((a, b) => a - b);
    if (!counts.length) return 10;
    return Math.max(5, counts[Math.floor(counts.length * 0.95)] ?? 10);
  }, [heatData]);

  useEffect(() => {
    if (!container.current || map.current) return;

    // Belt and braces on top of the inline style: set the geometry imperatively
    // with the important flag, which sits at the top of the cascade and cannot
    // be beaten by any stylesheet, including one using !important itself. This
    // element having a definite size is load-bearing, and it has silently lost
    // that size once already.
    const el = container.current;
    for (const [prop, value] of [
      ["position", "absolute"],
      ["inset", "0"],
      ["width", "100%"],
      ["height", "100%"],
    ] as const) {
      el.style.setProperty(prop, value, "important");
    }

    const instance = new maplibregl.Map({
      container: container.current,
      style: BASEMAP[mode],
      center: [25, 25],
      zoom: 1.4,
      minZoom: 0.8,
      maxZoom: 11,
      attributionControl: { compact: true },
      renderWorldCopies: true,
    });

    instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    instance.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

    // A zero-size container is the failure this map has actually shipped with:
    // MapLibre initialises happily, WebGL works, the style downloads, and the
    // user sees a black rectangle because the element has no height. Detect it
    // and say so, rather than rendering nothing and looking broken.
    const checkSize = () => {
      const el = container.current;
      if (!el) return;
      if (el.clientHeight < 2 || el.clientWidth < 2) {
        setFailure(
          `Map container has no size (${el.clientWidth}x${el.clientHeight}). ` +
            "This is a layout bug, not a data problem.",
        );
      } else {
        setFailure((f) => (f && f.startsWith("Map container") ? null : f));
      }
    };
    checkSize();

    // Re-measure on layout changes. Panels opening, the window resizing and the
    // mobile breakpoint all change the pane, and MapLibre does not notice on
    // its own.
    const observer = new ResizeObserver(() => {
      instance.resize();
      checkSize();
    });
    if (container.current) observer.observe(container.current);

    // If the style never resolves, `load` never fires and no layer is ever
    // added. Surface that instead of waiting forever on a blank canvas.
    const loadTimer = setTimeout(() => {
      if (!ready.current) {
        setFailure("Basemap did not load. Check for a blocked request to basemaps.cartocdn.com.");
      }
    }, 12000);

    instance.on("error", (e: { error?: { message?: string } }) => {
      const message = e.error?.message ?? "unknown";
      console.error("[map]", message);
    });

    instance.on("load", () => {
      ready.current = true;
      clearTimeout(loadTimer);
      setFailure((f) => (f && f.startsWith("Basemap") ? null : f));
      instance.addSource(HEAT_SOURCE, { type: "geojson", data: EMPTY });
      instance.addSource(EVENT_SOURCE, { type: "geojson", data: EMPTY });

      instance.addLayer({
        id: HEAT_LAYER,
        type: "heatmap",
        source: HEAT_SOURCE,
        paint: {
          "heatmap-weight": ["interpolate", ["linear"], ["get", "e"], 0, 0, 10, 1],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 0, 0.9, 6, 2.2, 10, 3],
          "heatmap-color": [
            "interpolate",
            ["linear"],
            ["heatmap-density"],
            0, "rgba(0,0,0,0)",
            0.15, HEAT_RAMP[mode][0],
            0.35, HEAT_RAMP[mode][1],
            0.55, HEAT_RAMP[mode][2],
            0.78, HEAT_RAMP[mode][3],
            1, HEAT_RAMP[mode][4],
          ],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 0, 6, 4, 18, 9, 42],
          // Hand off to the individual dots as the user zooms in: a heatmap at
          // street level is a lie about precision we do not have.
          "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 0, 0.85, 6, 0.7, 8.5, 0.15],
        },
      });

      instance.addLayer({
        id: EVENT_LAYER,
        type: "circle",
        source: EVENT_SOURCE,
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            1, ["interpolate", ["linear"], ["get", "f"], 0, 2, 5, 3.5, 40, 6],
            8, ["interpolate", ["linear"], ["get", "f"], 0, 5, 5, 9, 40, 18],
          ],
          "circle-color": [
            "step", ["get", "f"],
            SEVERITY_COLORS.none[mode],
            1, SEVERITY_COLORS.low[mode],
            5, SEVERITY_COLORS.medium[mode],
            20, SEVERITY_COLORS.high[mode],
          ],
          // 2px surface ring so overlapping marks stay separable.
          "circle-stroke-width": 1.5,
          "circle-stroke-color": SURFACE[mode],
          "circle-opacity": 0.9,
        },
      });

      instance.on("mouseenter", EVENT_LAYER, () => {
        instance.getCanvas().style.cursor = "pointer";
      });
      instance.on("mouseleave", EVENT_LAYER, () => {
        instance.getCanvas().style.cursor = "";
      });
      instance.on("click", EVENT_LAYER, (e: MapLayerMouseEvent) => {
        const f = e.features?.[0];
        if (!f) return;
        popup.current?.remove();
        popup.current = new maplibregl.Popup({ closeButton: true, maxWidth: "260px" })
          .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
          .setDOMContent(popupNode(f.properties as Record<string, unknown>, mode))
          .addTo(instance);
      });
    });

    map.current = instance;
    return () => {
      clearTimeout(loadTimer);
      observer.disconnect();
      popup.current?.remove();
      instance.remove();
      map.current = null;
      ready.current = false;
    };
    // Re-creating the map on mode change is intentional: the basemap style and
    // every paint expression differ, and restyling in place loses the sources.
  }, [mode]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const apply = () => {
      const src = instance.getSource(HEAT_SOURCE) as GeoJSONSource | undefined;
      if (!src) return;
      src.setData(heatData as unknown as GeoJSON.FeatureCollection);
      if (instance.getLayer(HEAT_LAYER)) {
        instance.setPaintProperty(HEAT_LAYER, "heatmap-weight", [
          "interpolate", ["linear"], ["get", "e"], 0, 0, heatMax, 1,
        ]);
      }
    };
    if (ready.current) apply();
    else instance.once("load", apply);
  }, [heatData, heatMax]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const apply = () => {
      const src = instance.getSource(EVENT_SOURCE) as GeoJSONSource | undefined;
      src?.setData(eventData as unknown as GeoJSON.FeatureCollection);
    };
    if (ready.current) apply();
    else instance.once("load", apply);
  }, [eventData]);

  useEffect(() => {
    if (!map.current || !focus) return;
    const [lon, lat, spread] = focus;
    map.current.flyTo({
      center: [lon, lat],
      zoom: Math.max(2.2, 6.5 - Math.log2(Math.max(spread, 0.5)) * 1.1),
      speed: 0.9,
    });
  }, [focus]);

  return (
    <>
      {/* Sizing lives in an inline style, not a stylesheet, on purpose.
          MapLibre stamps `maplibregl-map` onto this element and its own CSS sets
          `position: relative` there. Any class-based rule of ours ties on
          specificity, so the winner comes down to bundle order, which we do not
          control. An inline declaration beats every stylesheet rule regardless of
          order. This element must have a definite size or the map renders nothing,
          so it does not get to depend on load order. */}
      <div
        className="map-root"
        ref={container}
        role="application"
        aria-label="Conflict event map"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      />
      {failure && (
        <div className="map-failure" role="alert">
          <strong>The map isn&apos;t rendering.</strong>
          <span>{failure}</span>
          <span className="muted">
            The forecast, themes and portfolio panels are unaffected and still accurate.
          </span>
        </div>
      )}
    </>
  );
}
