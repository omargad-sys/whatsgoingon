"use client";

import { useState } from "react";

import { THEMES } from "@/lib/themes";
import { bps } from "@/lib/format";
import type { ThemeImpact } from "@/lib/exposure";

interface Props {
  impacts: ThemeImpact[];
  /** Only shown when a portfolio has weights; otherwise the panel explains itself. */
  hasHoldings: boolean;
}

/**
 * Signed magnitude by category. Diverging encoding (two poles, neutral gray
 * midline) because the sign is the point: does escalation help or hurt this
 * portfolio. One axis, direct value labels, no gridlines beyond the zero rule.
 *
 * Themes where nothing was identified render as text, not as a zero-length bar.
 * A zero bar would read as "no effect"; the truth is "no measurable effect",
 * and those are different claims.
 */
export default function ImpactBars({ impacts, hasHoldings }: Props) {
  const [hover, setHover] = useState<string | null>(null);

  const measured = impacts.filter((i) => !i.empty);
  const scale = Math.max(0.0001, ...measured.map((i) => Math.abs(i.impact) + i.se));

  if (!hasHoldings) {
    return <p className="hint">Add at least one holding to see modeled impact.</p>;
  }

  if (!measured.length) {
    return (
      <p className="hint">
        None of your holdings has a statistically identified response to any of these
        themes. That is a real result, not a bug: broad index funds mostly do not
        move on conflict news.{" "}
        <a href="/methodology">How this is tested</a>.
      </p>
    );
  }

  return (
    <div>
      {impacts.map((im) => {
        const meta = THEMES[im.theme];
        const pctOfScale = im.empty ? 0 : (Math.abs(im.impact) / scale) * 50;
        const sePct = im.empty ? 0 : (im.se / scale) * 50;
        const positive = im.impact >= 0;
        const color = positive ? "var(--div-pos)" : "var(--div-neg)";

        return (
          <div
            key={im.theme}
            style={{ padding: "9px 0", borderBottom: "1px solid var(--grid)" }}
            onMouseEnter={() => setHover(im.theme)}
            onMouseLeave={() => setHover(null)}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: 8,
                marginBottom: 5,
              }}
            >
              <span style={{ fontSize: 12.5, fontWeight: 560 }}>{meta.label}</span>
              {im.empty ? (
                <span className="null-note">no detectable relationship</span>
              ) : (
                <span
                  style={{
                    fontSize: 12.5,
                    fontVariantNumeric: "tabular-nums",
                    color: "var(--text-primary)",
                  }}
                >
                  {bps(im.impact)}
                </span>
              )}
            </div>

            {!im.empty && (
              <div style={{ position: "relative", height: 12 }}>
                {/* neutral midline */}
                <div
                  style={{
                    position: "absolute",
                    left: "50%",
                    top: -1,
                    bottom: -1,
                    width: 1,
                    background: "var(--axis)",
                  }}
                />
                {/* standard-error whisker, drawn under the bar */}
                <div
                  style={{
                    position: "absolute",
                    top: 5,
                    height: 2,
                    background: "var(--div-mid)",
                    left: positive ? "50%" : `${50 - pctOfScale - sePct}%`,
                    width: `${pctOfScale + sePct}%`,
                    borderRadius: 1,
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    top: 1,
                    height: 10,
                    background: color,
                    left: positive ? "50%" : `${50 - pctOfScale}%`,
                    width: `${Math.max(pctOfScale, 0.6)}%`,
                    borderRadius: positive ? "0 4px 4px 0" : "4px 0 0 4px",
                    transition: "width 160ms ease, left 160ms ease",
                  }}
                />
              </div>
            )}

            {hover === im.theme && !im.empty && (
              <div style={{ marginTop: 6, fontSize: 11.5, color: "var(--text-secondary)" }}>
                {bps(im.impact)} ± {bps(im.se, { sign: false })} for a +1σ shock ·{" "}
                {Math.round(im.coverage * 100)}% of portfolio weight identified
              </div>
            )}
          </div>
        );
      })}

      <p className="hint" style={{ marginTop: 10, marginBottom: 0 }}>
        Bars point right when escalation is estimated to raise the portfolio and left
        when it lowers it. The pale extension is one standard error.
      </p>
    </div>
  );
}
