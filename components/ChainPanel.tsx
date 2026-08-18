"use client";

import { explainBreak } from "@/lib/chain";
import { THEMES } from "@/lib/themes";
import { bps } from "@/lib/format";
import type { ChainedThemeImpact } from "@/lib/chain";
import type { Forecast, Link } from "@/lib/types";

interface Props {
  impact: ChainedThemeImpact;
  forecast: Forecast;
  link: Link;
}

/**
 * Shows the three layers as three steps, each marked passed or blocked, so the
 * reader can see exactly where a missing number went missing. An app that
 * silently prints nothing teaches you not to trust it; an app that says "layer
 * two is where this stops" is debuggable.
 */
export default function ChainPanel({ impact, forecast, link }: Props) {
  const meta = THEMES[impact.theme];
  const l = link.themes[impact.theme];
  const tf = impact.forecast;

  const identified = impact.holdings.filter((h) => h.expectedReturn !== undefined).length;
  const breakReason = explainBreak(impact, link.tstat_threshold);

  return (
    <div>
      <div className="chain">
        <div className="chain-step" data-ok={tf.covered > 0}>
          <span className="idx">1</span>
          <span className="lbl">
            Escalation risk across {meta.label}
            <br />
            <span className="muted" style={{ fontSize: 11 }}>
              {tf.covered} of {tf.members} countries forecast
            </span>
          </span>
          <span className="val">{(tf.expectedFraction * 100).toFixed(0)}%</span>
        </div>

        <div className="chain-step" data-ok={tf.linkOk}>
          <span className="idx">2</span>
          <span className="lbl">
            Implied conflict shock
            <br />
            <span className="muted" style={{ fontSize: 11 }}>
              {l
                ? `slope ${l.slope >= 0 ? "+" : ""}${l.slope.toFixed(2)}, t=${l.tstat.toFixed(2)}, R²=${l.r2.toFixed(2)}`
                : "no link estimated"}
            </span>
          </span>
          <span className="val">
            {tf.expectedShock === undefined
              ? "blocked"
              : `${tf.expectedShock >= 0 ? "+" : ""}${tf.expectedShock.toFixed(2)}σ`}
          </span>
        </div>

        <div className="chain-step" data-ok={identified > 0}>
          <span className="idx">3</span>
          <span className="lbl">
            Portfolio response
            <br />
            <span className="muted" style={{ fontSize: 11 }}>
              {identified} of {impact.holdings.length} holdings identified
            </span>
          </span>
          <span className="val">{impact.empty ? "blocked" : bps(impact.expectedReturn)}</span>
        </div>
      </div>

      {breakReason ? (
        <div className="chain-break">{breakReason}</div>
      ) : (
        <p className="hint" style={{ marginBottom: 0 }}>
          Expected portfolio return for {forecast.target_month.slice(0, 7)} from{" "}
          {meta.label} conflict alone: <strong>{bps(impact.expectedReturn)}</strong> ±{" "}
          {bps(impact.se, { sign: false })}. The error band compounds both estimated
          layers and still understates the true uncertainty, because the forecaster&apos;s
          own error is not propagated into it.
        </p>
      )}
    </div>
  );
}
