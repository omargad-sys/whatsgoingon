"use client";

import { useEffect, useRef, useState } from "react";

import type { ChangeEvent } from "react";

import { shortDate } from "@/lib/format";

interface Props {
  weeks: string[];
  value: number;
  windowWeeks: number;
  onChange: (index: number) => void;
  onWindowChange: (weeks: number) => void;
}

const WINDOWS = [
  { weeks: 1, label: "1w" },
  { weeks: 4, label: "4w" },
  { weeks: 13, label: "13w" },
  { weeks: 999, label: "All" },
];

export default function TimeSlider({
  weeks,
  value,
  windowWeeks,
  onChange,
  onWindowChange,
}: Props) {
  const [playing, setPlaying] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const last = weeks.length - 1;

  useEffect(() => {
    if (!playing) return;
    timer.current = setInterval(() => {
      onChange(value >= last ? 0 : value + 1);
    }, 550);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [playing, value, last, onChange]);

  // Stop at the end rather than looping forever in the background.
  useEffect(() => {
    if (playing && value >= last) setPlaying(false);
  }, [playing, value, last]);

  if (!weeks.length) return null;

  const from = Math.max(0, value - (windowWeeks - 1));
  const rangeLabel =
    windowWeeks === 1
      ? `Week of ${shortDate(weeks[value])}`
      : `${shortDate(weeks[from])} to ${shortDate(weeks[value])}`;

  return (
    <div className="map-overlay timeline">
      <div className="timeline-head">
        <span className="label">{rangeLabel}</span>
        <span className="sub">
          {weeks.length} weeks · ending {shortDate(weeks[last])}
        </span>
      </div>

      <input
        type="range"
        min={0}
        max={last}
        step={1}
        value={value}
        aria-label="Week shown on the map"
        onChange={(e: ChangeEvent<HTMLInputElement>) => {
          setPlaying(false);
          onChange(Number(e.target.value));
        }}
      />

      <div className="timeline-controls">
        <button
          type="button"
          className="pill"
          aria-pressed={playing}
          onClick={() => setPlaying((p) => !p)}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <span style={{ flex: 1 }} />
        {WINDOWS.map((w) => (
          <button
            key={w.label}
            type="button"
            className="pill"
            aria-pressed={windowWeeks === w.weeks}
            onClick={() => onWindowChange(w.weeks)}
            title={w.weeks === 999 ? "Whole window" : `Trailing ${w.label}`}
          >
            {w.label}
          </button>
        ))}
      </div>
    </div>
  );
}
