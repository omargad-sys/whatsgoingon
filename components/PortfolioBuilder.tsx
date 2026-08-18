"use client";

import type { ChangeEvent } from "react";

import { TICKERS, TICKER_LIST } from "@/lib/themes";
import type { Holding } from "@/lib/types";

interface Props {
  holdings: Holding[];
  onChange: (next: Holding[]) => void;
}

const PRESETS: { label: string; holdings: Holding[] }[] = [
  {
    label: "Three-fund",
    holdings: [
      { ticker: "VTI", weight: 0.7 },
      { ticker: "VOO", weight: 0.2 },
      { ticker: "GLD", weight: 0.1 },
    ],
  },
  {
    label: "Index only",
    holdings: [{ ticker: "VOO", weight: 1 }],
  },
  {
    label: "Conflict-tilted",
    holdings: [
      { ticker: "VOO", weight: 0.5 },
      { ticker: "XLE", weight: 0.2 },
      { ticker: "ITA", weight: 0.15 },
      { ticker: "GLD", weight: 0.15 },
    ],
  },
];

export default function PortfolioBuilder({ holdings, onChange }: Props) {
  const used = new Set(holdings.map((h) => h.ticker));
  const total = holdings.reduce((s, h) => s + (h.weight || 0), 0);
  const available = TICKER_LIST.filter((t) => !used.has(t));

  const update = (i: number, patch: Partial<Holding>) => {
    onChange(holdings.map((h, idx) => (idx === i ? { ...h, ...patch } : h)));
  };

  const grouped = TICKER_LIST.reduce<Record<string, string[]>>((acc, t) => {
    const g = TICKERS[t].group;
    (acc[g] ||= []).push(t);
    return acc;
  }, {});

  return (
    <div>
      {holdings.map((h, i) => (
        <div className="holding" key={`${h.ticker}-${i}`}>
          <select
            value={h.ticker}
            aria-label={`Holding ${i + 1} ticker`}
            onChange={(e: ChangeEvent<HTMLSelectElement>) => update(i, { ticker: e.target.value })}
          >
            {Object.entries(grouped).map(([group, tickers]) => (
              <optgroup key={group} label={group}>
                {tickers
                  .filter((t) => t === h.ticker || !used.has(t))
                  .map((t) => (
                    <option key={t} value={t}>
                      {t} · {TICKERS[t].label}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>

          <input
            type="number"
            min={0}
            max={100}
            step={1}
            inputMode="decimal"
            aria-label={`${h.ticker} weight, percent`}
            value={Math.round(h.weight * 1000) / 10}
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              const v = Number.parseFloat(e.target.value);
              update(i, { weight: Number.isFinite(v) ? Math.max(0, v) / 100 : 0 });
            }}
          />

          <button
            type="button"
            className="icon-btn"
            aria-label={`Remove ${h.ticker}`}
            onClick={() => onChange(holdings.filter((_, idx) => idx !== i))}
          >
            ×
          </button>
        </div>
      ))}

      {Math.abs(total - 1) > 0.005 && holdings.length > 0 && (
        <p className="weight-warn">
          Weights sum to {Math.round(total * 100)}%. They are renormalised to 100% before
          any impact is computed.
        </p>
      )}

      <div className="row-actions">
        <button
          type="button"
          className="btn"
          disabled={!available.length}
          onClick={() => onChange([...holdings, { ticker: available[0], weight: 0.1 }])}
        >
          Add holding
        </button>
        {holdings.length > 0 && (
          <button type="button" className="btn" onClick={() => onChange([])}>
            Clear
          </button>
        )}
      </div>

      <div className="row-actions" style={{ flexWrap: "wrap" }}>
        <span className="muted" style={{ fontSize: 11.5 }}>
          Presets:
        </span>
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            className="pill"
            onClick={() => onChange(p.holdings.map((h) => ({ ...h })))}
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}
