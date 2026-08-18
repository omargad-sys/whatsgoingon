"use client";

import { THEMES, TICKERS } from "@/lib/themes";
import { bps, pct } from "@/lib/format";
import type { ThemeImpact } from "@/lib/exposure";
import type { ThemeId } from "@/lib/types";

interface Props {
  impact: ThemeImpact;
  onThemeChange: (theme: ThemeId) => void;
  themes: ThemeId[];
}

/**
 * The table view. It exists partly because per-holding numbers are genuinely
 * useful and partly because every chart on this page needs a text equivalent
 * for the numbers it encodes with color and length.
 */
export default function ExposureTable({ impact, onThemeChange, themes }: Props) {
  return (
    <div>
      <div className="row-actions" style={{ marginTop: 0, marginBottom: 10, flexWrap: "wrap" }}>
        {themes.map((t) => (
          <button
            key={t}
            type="button"
            className="pill"
            aria-pressed={impact.theme === t}
            onClick={() => onThemeChange(t)}
          >
            {THEMES[t].label}
          </button>
        ))}
      </div>

      {impact.holdings.length === 0 ? (
        <p className="hint">No holdings yet.</p>
      ) : (
        <table className="data">
          <caption className="visually-hidden">
            Per-holding modeled response to a one standard deviation{" "}
            {THEMES[impact.theme].label} conflict shock
          </caption>
          <thead>
            <tr>
              <th scope="col">Holding</th>
              <th scope="col" className="num">
                Weight
              </th>
              <th scope="col" className="num">
                Per +1σ
              </th>
              <th scope="col" className="num">
                t
              </th>
            </tr>
          </thead>
          <tbody>
            {impact.holdings.map((h) => (
              <tr key={h.ticker}>
                <td>
                  <span className="ticker-cell">
                    <strong>{h.ticker}</strong>
                    <span className="muted" style={{ fontSize: 11.5 }}>
                      {TICKERS[h.ticker]?.group ?? ""}
                    </span>
                  </span>
                </td>
                <td className="num">{pct(h.weight, 0)}</td>
                <td className="num">
                  {h.status === "identified" && h.pair ? (
                    bps(h.pair.beta)
                  ) : h.status === "not-identified" ? (
                    <span className="null-note">not identified</span>
                  ) : (
                    <span className="null-note">no estimate</span>
                  )}
                </td>
                <td className="num muted">
                  {h.pair ? h.pair.tstat.toFixed(2) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={2} style={{ paddingTop: 8 }}>
                <strong>Portfolio</strong>
              </td>
              <td className="num" style={{ paddingTop: 8 }}>
                {impact.empty ? (
                  <span className="null-note">not identified</span>
                ) : (
                  <strong>{bps(impact.impact)}</strong>
                )}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      )}

      <p className="hint" style={{ marginTop: 10, marginBottom: 0 }}>
        &ldquo;Not identified&rdquo; means the estimated relationship did not clear the
        significance gate, so no number is shown. It does not mean the effect is zero.
      </p>
    </div>
  );
}
