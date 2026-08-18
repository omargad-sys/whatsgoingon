"use client";

import { rankedRisk } from "@/lib/chain";
import type { Forecast } from "@/lib/types";

interface Props {
  forecast: Forecast;
  onFocus: (centroid: [number, number, number]) => void;
  limit?: number;
}

/**
 * Ordered magnitude by category, so a bar. Sequential encoding rather than
 * categorical: the bars are one hue and length carries the value, because
 * probability is a magnitude and colouring each country differently would
 * imply an identity that does not exist.
 */
export default function RiskList({ forecast, onFocus, limit = 10 }: Props) {
  const rows = rankedRisk(forecast, limit);
  const max = Math.max(0.01, ...rows.map((r) => r.p));

  if (!rows.length) return <p className="hint">No forecast available.</p>;

  return (
    <div>
      <table className="data">
        <caption className="visually-hidden">
          Countries ranked by probability of conflict escalation in {forecast.target_month}
        </caption>
        <thead>
          <tr>
            <th scope="col">Country</th>
            <th scope="col" style={{ width: "44%" }}>
              Escalation probability
            </th>
            <th scope="col" className="num">
              p
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.country}>
              <td>
                {r.centroid ? (
                  <button
                    type="button"
                    className="linklike"
                    onClick={() => onFocus(r.centroid as [number, number, number])}
                    title={`Show ${r.country} on the map`}
                  >
                    {r.country}
                  </button>
                ) : (
                  r.country
                )}
              </td>
              <td>
                <div className="prob-track">
                  <div
                    className="prob-fill"
                    style={{ width: `${Math.max((r.p / max) * 100, 1.5)}%` }}
                  />
                </div>
              </td>
              <td className="num">{r.p.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="hint" style={{ marginTop: 10, marginBottom: 0 }}>
        Probability that fatalities in {forecast.target_month.slice(0, 7)} exceed the
        country&apos;s own historical {Math.round(forecast.threshold_quantile * 100)}th
        percentile. Predicted by the{" "}
        <strong>{forecast.source === "model" ? "gradient-boosted model" : "persistence baseline"}</strong>
        , which won the walk-forward comparison.
      </p>
    </div>
  );
}
