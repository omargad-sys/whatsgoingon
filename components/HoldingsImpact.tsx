"use client";

import { useState } from "react";

import { THEMES, TICKERS } from "@/lib/themes";
import type { HoldingOutlook } from "@/lib/chain";

interface Props {
  outlooks: HoldingOutlook[];
  /** e.g. "2026-09" */
  month: string;
}

/**
 * One row per thing you own, which is the question people actually arrive with.
 *
 * Signed magnitude, so a diverging encoding: one hue each side of a neutral
 * midline, length carries size, direction carries sign. Every row is directly
 * labelled, so no legend is needed and colour is never the only channel.
 *
 * Deliberately in percent rather than basis points. Basis points are precise and
 * standard, and completely opaque to anyone who does not already work in
 * markets, which is most of the people who will open this.
 *
 * Rows with nothing measurable render as words, never as a zero-length bar. A
 * zero bar reads as "no effect"; the truth is "no measurable effect", and the
 * whole project rests on not blurring those two.
 */
export default function HoldingsImpact({ outlooks, month }: Props) {
  const [open, setOpen] = useState<string | null>(null);

  if (!outlooks.length) {
    return <p className="hint">Add a holding below to see how conflict risk touches it.</p>;
  }

  const scale = Math.max(
    0.0005,
    ...outlooks.map((o) => Math.abs(o.expected ?? 0) + (o.se ?? 0)),
  );

  const pct = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(2)}%`;

  return (
    <div>
      {outlooks.map((o) => {
        const measured = o.expected !== undefined;
        const positive = (o.expected ?? 0) >= 0;
        const width = measured ? (Math.abs(o.expected!) / scale) * 50 : 0;
        const seWidth = measured ? ((o.se ?? 0) / scale) * 50 : 0;
        const isOpen = open === o.ticker;

        return (
          <div key={o.ticker} className="holding-row">
            <button
              type="button"
              className="holding-head"
              onClick={() => setOpen(isOpen ? null : o.ticker)}
              aria-expanded={isOpen}
            >
              <span className="holding-id">
                <strong>{o.ticker}</strong>
                <span className="muted">{Math.round(o.weight * 100)}%</span>
              </span>

              <span className="holding-verdict">
                {measured ? (
                  <>
                    <span className={positive ? "up" : "down"}>{pct(o.expected!)}</span>
                    <span className="muted"> {positive ? "expected gain" : "expected drop"}</span>
                  </>
                ) : (
                  <span className="null-note">no measurable effect</span>
                )}
              </span>
            </button>

            {measured ? (
              <div className="diverge">
                <div className="diverge-mid" />
                <div
                  className="diverge-se"
                  style={{
                    left: positive ? "50%" : `${50 - width - seWidth}%`,
                    width: `${width + seWidth}%`,
                  }}
                />
                <div
                  className={`diverge-bar ${positive ? "pos" : "neg"}`}
                  style={{
                    left: positive ? "50%" : `${50 - width}%`,
                    width: `${Math.max(width, 0.6)}%`,
                  }}
                />
              </div>
            ) : (
              <div className="holding-why muted">
                {o.blocked === "no-link"
                  ? "Conflict in these regions has no measurable effect on regional intensity, so nothing reaches this holding."
                  : "This holding has no statistically identified response to any region. Broad index funds usually do not."}
              </div>
            )}

            {isOpen && (
              <div className="holding-detail">
                <div className="muted" style={{ marginBottom: 6 }}>
                  {TICKERS[o.ticker]?.label ?? o.ticker} · {TICKERS[o.ticker]?.group}
                </div>
                {measured ? (
                  <>
                    <table className="data">
                      <caption className="visually-hidden">
                        Regions contributing to {o.ticker}&apos;s expected move
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col">Driven by</th>
                          <th scope="col" className="num">
                            Contribution
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {o.drivers.map((d) => (
                          <tr key={d.theme}>
                            <td>{THEMES[d.theme].label}</td>
                            <td className="num">{pct(d.contribution)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="hint" style={{ margin: "8px 0 0" }}>
                      Range of roughly {pct(o.expected! - (o.se ?? 0))} to{" "}
                      {pct(o.expected! + (o.se ?? 0))}, and that band is a floor: it
                      leaves out the forecaster&apos;s own error.
                    </p>
                  </>
                ) : (
                  <p className="hint" style={{ margin: 0 }}>
                    Nothing is hidden here. The relationship was tested and could not be
                    distinguished from noise, so no number is shown.
                  </p>
                )}
              </div>
            )}
          </div>
        );
      })}

      <p className="hint" style={{ marginTop: 12, marginBottom: 0 }}>
        Expected move during {month} from conflict escalation risk alone, ignoring
        everything else that moves markets. Bars point right for a gain, left for a
        drop; the pale extension is the margin of error. Tap a row for the detail.
      </p>
    </div>
  );
}
