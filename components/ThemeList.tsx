"use client";

import { useMemo } from "react";

import Sparkline from "./Sparkline";
import { THEME_COLOR_VAR, THEMES, THEME_ORDER } from "@/lib/themes";
import { lastMonths, themeSeries } from "@/lib/intensity";
import { describeShock, monthLabel } from "@/lib/format";
import type { CountryMonthly, ThemeId } from "@/lib/types";

interface Props {
  panel: CountryMonthly | null;
  currentShock: Partial<Record<ThemeId, number | null>>;
  selected: ThemeId;
  onSelect: (theme: ThemeId) => void;
}

const MONTHS_SHOWN = 36;

export default function ThemeList({ panel, currentShock, selected, onSelect }: Props) {
  const series = useMemo(() => {
    if (!panel) return null;
    return Object.fromEntries(
      THEME_ORDER.map((t) => {
        const s = themeSeries(panel, t);
        return [
          t,
          {
            level: lastMonths(s.level, MONTHS_SHOWN),
            events: lastMonths(s.events, MONTHS_SHOWN),
            months: lastMonths(s.months, MONTHS_SHOWN),
          },
        ];
      }),
    ) as Record<ThemeId, { level: number[]; events: number[]; months: string[] }>;
  }, [panel]);

  return (
    <div>
      {THEME_ORDER.map((t) => {
        const meta = THEMES[t];
        const z = currentShock[t];
        const s = series?.[t];

        return (
          <button
            key={t}
            type="button"
            className="theme-row"
            aria-pressed={selected === t}
            onClick={() => onSelect(t)}
          >
            <span>
              <span className="theme-name" style={{ display: "block" }}>
                {meta.label}
              </span>
              <span className="theme-sub">
                {z === null || z === undefined
                  ? "no reading"
                  : `${z > 0 ? "+" : ""}${z.toFixed(1)}σ · ${describeShock(z)}`}
              </span>
            </span>

            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {s && (
                <Sparkline
                  values={s.level}
                  labels={s.months.map(monthLabel)}
                  color={THEME_COLOR_VAR[t]}
                  title={`${meta.label} conflict intensity, last ${MONTHS_SHOWN} months`}
                  formatValue={(v) => `${Math.round(Math.expm1(v)).toLocaleString()} severity`}
                  width={104}
                  height={26}
                />
              )}
            </span>
          </button>
        );
      })}

      <p className="hint" style={{ marginTop: 10, marginBottom: 0 }}>
        Sparklines show log-damped severity (events plus weighted fatalities) over the
        last {MONTHS_SHOWN} months. The sigma figure is this month&apos;s change against
        its own 36-month history.
      </p>
    </div>
  );
}
