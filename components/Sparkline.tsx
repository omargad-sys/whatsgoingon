"use client";

import { useId, useMemo, useState } from "react";
import type { MouseEvent } from "react";

interface Props {
  values: number[];
  labels: string[];
  color: string;
  /** Accessible name. A single-series chart needs no legend; the title names it. */
  title: string;
  formatValue?: (v: number) => string;
  width?: number;
  height?: number;
}

/**
 * Single-series magnitude-over-time. One line, 2px, recessive baseline, no
 * gridlines at this size, no per-point labels. Hover exposes a crosshair and a
 * value readout, and the same numbers are reachable as a table for screen
 * readers.
 */
export default function Sparkline({
  values,
  labels,
  color,
  title,
  formatValue = (v) => v.toLocaleString(),
  width = 132,
  height = 30,
}: Props) {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);

  const { points, area, min, max } = useMemo(() => {
    const clean = values.filter((v) => Number.isFinite(v));
    if (clean.length < 2) return { points: "", area: "", min: 0, max: 0 };

    const lo = Math.min(...clean);
    const hi = Math.max(...clean);
    const span = hi - lo || 1;
    const stepX = width / (values.length - 1);

    const coords = values.map((v, i) => {
      const x = i * stepX;
      const y = height - 2 - ((v - lo) / span) * (height - 4);
      return [x, Number.isFinite(y) ? y : height - 2] as const;
    });

    return {
      points: coords.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" "),
      area: `0,${height} ${coords.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ")} ${width},${height}`,
      min: lo,
      max: hi,
    };
  }, [values, width, height]);

  if (!points) return <div style={{ width, height }} aria-hidden="true" />;

  const stepX = width / (values.length - 1);
  const hoverX = hover === null ? 0 : hover * stepX;
  const span = max - min || 1;
  const hoverY =
    hover === null ? 0 : height - 2 - ((values[hover] - min) / span) * (height - 4);

  return (
    <div style={{ position: "relative", width, height }}>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby={`${id}-title`}
        style={{ display: "block", overflow: "visible" }}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e: MouseEvent<SVGSVGElement>) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const i = Math.round(((e.clientX - rect.left) / rect.width) * (values.length - 1));
          setHover(Math.min(values.length - 1, Math.max(0, i)));
        }}
      >
        <title id={`${id}-title`}>{title}</title>
        <defs>
          <linearGradient id={`${id}-fill`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.22" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={area} fill={`url(#${id}-fill)`} />
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
        {hover !== null && (
          <g>
            <line
              x1={hoverX}
              x2={hoverX}
              y1={0}
              y2={height}
              stroke="var(--axis)"
              strokeWidth="1"
            />
            <circle
              cx={hoverX}
              cy={hoverY}
              r="3.5"
              fill={color}
              stroke="var(--surface-1)"
              strokeWidth="2"
            />
          </g>
        )}
      </svg>

      {hover !== null && (
        <div
          style={{
            position: "absolute",
            left: Math.min(Math.max(hoverX - 40, -20), width - 40),
            top: -34,
            background: "var(--surface-1)",
            border: "1px solid var(--border-strong)",
            borderRadius: 6,
            padding: "3px 6px",
            fontSize: 11,
            whiteSpace: "nowrap",
            pointerEvents: "none",
            zIndex: 4,
            color: "var(--text-primary)",
          }}
        >
          <strong style={{ fontVariantNumeric: "tabular-nums" }}>
            {formatValue(values[hover])}
          </strong>{" "}
          <span className="muted">{labels[hover]}</span>
        </div>
      )}
    </div>
  );
}
