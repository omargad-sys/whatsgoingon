import Link from "next/link";

import forecast from "@/public/data/forecast.json";
import linkData from "@/public/data/link.json";
import manifest from "@/public/data/manifest.json";
import sensitivities from "@/public/data/sensitivities.json";
import { THEMES, THEME_ORDER, TICKERS } from "@/lib/themes";
import type { Forecast, Link as LinkModel, Manifest, Sensitivities } from "@/lib/types";

export const metadata = {
  title: "Methodology — What's Going On",
};

const sens = sensitivities as unknown as Sensitivities;
const man = manifest as unknown as Manifest;
const fc = forecast as unknown as Forecast;
const link = linkData as unknown as LinkModel;

export default function Methodology() {
  const significant = sens.pairs.filter((p) => p.significant);
  const tOnly = sens.pairs.filter((p) => p.passes_tstat && !p.significant);

  return (
    <main className="prose">
      <p style={{ marginBottom: 20 }}>
        <Link href="/">← Back to the map</Link>
      </p>

      <h1>Methodology</h1>
      <p className="muted" style={{ marginTop: 0 }}>
        What this tool measures, how, and where it stops being trustworthy.
      </p>

      {man.synthetic && (
        <div className="callout">
          <strong>This build uses synthetic data.</strong> The pipeline ran against
          generated fixtures rather than ACLED, so every coefficient below is
          meaningless as a finding. It is here to demonstrate that the machinery works.
        </div>
      )}

      <h2>The short version</h2>
      <p>Three models in a chain, each with its own gate:</p>
      <ol>
        <li>
          <strong>Forecast.</strong> For each country, the probability that fatalities
          next month exceed its own historical high-water mark.
        </li>
        <li>
          <strong>Link.</strong> How much a region-wide escalation moves that
          region&apos;s conflict intensity, in standard deviations.
        </li>
        <li>
          <strong>Sensitivity.</strong> How each ETF responds to a one standard deviation
          conflict shock, net of the market.
        </li>
      </ol>
      <p>
        Multiply the three and you get an expected return for a portfolio, conditional
        on the conflict risk currently on the board. A number appears on screen only if
        all three layers clear their gate. Most do not, and the app says so instead of
        printing something.
      </p>
      <div className="callout">
        <strong>Chaining estimates multiplies their error.</strong> A chain built from
        two barely significant links deserves less confidence than either link alone,
        not more. The error bands shown are a floor, and they do not include the
        forecaster&apos;s own uncertainty at all.
      </div>

      <h2>Layer 1: the escalation forecast</h2>
      <p>
        A country-month is labelled <em>escalating</em> if fatalities{" "}
        {fc.lookahead_months} month(s) later exceed that country&apos;s own expanding{" "}
        {Math.round(fc.threshold_quantile * 100)}th percentile. The threshold uses only
        months strictly before the one being labelled. An earlier draft of this project
        used the full-sample quantile, which let 2024 decide what counted as escalation
        in 2019, and inflated every metric downstream.
      </p>
      <p>
        Features are the current month&apos;s event and fatality counts, trailing 3, 6
        and 12 month means computed with a one-month lag, and each series against its own
        trailing year.
      </p>
      <h3>Which predictor is actually running</h3>
      <p>
        Two candidates are evaluated by rolling-origin validation: a gradient-boosted
        classifier, and a baseline that is one division,{" "}
        <code>this month&apos;s fatalities / the country&apos;s threshold</code>. The one
        that wins is the one that ships, and the app names it rather than implying a
        model is at work when arithmetic is doing the job.
      </p>
      <table className="data" style={{ marginTop: 8 }}>
        <tbody>
          <tr>
            <td>Gradient-boosted model</td>
            <td className="num">ROC-AUC {fc.evaluation.model_roc_auc.toFixed(3)}</td>
            <td className="num">Brier {fc.evaluation.model_brier.toFixed(3)}</td>
          </tr>
          <tr>
            <td>Persistence baseline</td>
            <td className="num">ROC-AUC {fc.evaluation.baseline_roc_auc.toFixed(3)}</td>
            <td className="num">Brier {fc.evaluation.baseline_brier.toFixed(3)}</td>
          </tr>
          <tr>
            <td>
              <strong>Shipping</strong>
            </td>
            <td className="num" colSpan={2}>
              <strong>
                {fc.source === "model" ? "the model" : "the baseline"}
              </strong>{" "}
              <span className="muted">
                (margin {fc.evaluation.margin >= 0 ? "+" : ""}
                {fc.evaluation.margin.toFixed(3)}, gate 0.020)
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <p>
        Fatalities are strongly autocorrelated, so &ldquo;was this month bad&rdquo;
        already answers most of &ldquo;will next month be bad&rdquo;. A model that cannot
        beat that has not learned anything, and a margin under 0.02 across{" "}
        {fc.evaluation.windows} windows is noise. On a tie the simpler predictor wins.
      </p>
      <p>
        Calibration matters more than ranking here, because layer 2 converts these
        probabilities into an expected escalation rate and a mean of probabilities is
        only unbiased if they are calibrated. Calibration slope:{" "}
        <strong>
          {fc.evaluation.calibration_slope === null
            ? "not estimable"
            : fc.evaluation.calibration_slope.toFixed(2)}
        </strong>{" "}
        (1.00 is perfect).
      </p>

      <h2>Layer 2: escalation to conflict shock</h2>
      <pre>
        <code>{link.spec}</code>
      </pre>
      <p>
        <code>frac</code> is the share of a theme&apos;s countries whose escalation label
        is set in month t. Because that label describes month t+1, the shock it is
        regressed against is also at t+1. Getting that offset wrong by one month would
        let a month&apos;s violence predict itself, so the alignment is asserted in the
        test suite rather than trusted.
      </p>
      <table className="data" style={{ marginTop: 8 }}>
        <thead>
          <tr>
            <th scope="col">Theme</th>
            <th scope="col" className="num">Slope</th>
            <th scope="col" className="num">t</th>
            <th scope="col" className="num">R²</th>
            <th scope="col" className="num">n</th>
            <th scope="col">Chain</th>
          </tr>
        </thead>
        <tbody>
          {THEME_ORDER.filter((t) => link.themes[t]).map((t) => {
            const l = link.themes[t]!;
            return (
              <tr key={t}>
                <td>{THEMES[t].label}</td>
                <td className="num">{l.slope >= 0 ? "+" : ""}{l.slope.toFixed(2)}</td>
                <td className="num">{l.tstat.toFixed(2)}</td>
                <td className="num">{l.r2.toFixed(3)}</td>
                <td className="num">{l.n}</td>
                <td>{l.significant ? "passes" : <span className="null-note">broken here</span>}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p>
        The R² values are low, which is honest: escalation in a handful of countries
        explains only a small part of a region&apos;s aggregate month-over-month
        intensity change. A significant slope with a low R² means the direction is real
        and the magnitude is noisy.
      </p>

      <h2>Layer 3: conflict shock to prices</h2>
      <p>
        Each index is a shock: how unusual this month&apos;s change is relative to its own
        recent history. Each ETF&apos;s monthly return is regressed on that shock. The
        result is one number per ticker-theme pair, the estimated return impact of a one
        standard deviation escalation.
      </p>
      <p>
        Most of those numbers are not distinguishable from zero, and the app refuses to
        display those. That refusal is the design.
      </p>

      <h2>Conflict data</h2>
      <p>
        Event data comes from the{" "}
        <a href="https://acleddata.com">
          Armed Conflict Location &amp; Event Data Project
        </a>
        , pulled through their API. The pipeline covers{" "}
        {man.acled.panel_countries} countries selected for having a plausible
        transmission channel to a US-listed ETF: oil producers, chokepoints, major
        emerging markets and active theatres. It is not a global census, and countries
        outside the universe are invisible to the model.
      </p>
      <p>
        The map shows a {man.window_days}-day window: {man.acled.grid_cells.toLocaleString()}{" "}
        binned density cells across {man.acled.weeks} weeks, plus{" "}
        {man.acled.detail_events.toLocaleString()} individually plotted events. Individual
        dots are the most severe events per week, not every event; the heat layer is the
        complete count.
      </p>

      <h3>Known limitations of the source</h3>
      <ul>
        <li>
          ACLED coverage has widened over time. A rising raw event count can be better
          reporting rather than more violence, which is why the model works with
          rolling-window shocks instead of levels.
        </li>
        <li>
          Access on the Research tier is lagged, so &ldquo;right now&rdquo; means the most
          recent month in the data, not today.
        </li>
        <li>
          Events with unusable coordinates, including the 0,0 placeholder, are dropped
          from the map but still counted in the monthly panel.
        </li>
      </ul>

      <h2>The intensity index</h2>
      <p>For each theme, in each month:</p>
      <pre>
        <code>{`raw   = Σ over member countries of (events + 3 × fatalities)
level = log(1 + raw)
shock = level(t) − level(t−1)
z     = (shock − rolling_mean(shock, 36)) / rolling_std(shock, 36)`}</code>
      </pre>
      <p>
        Fatalities are weighted three to one against raw event counts because a fatal
        engagement signals escalation more strongly than a protest does. The logarithm
        stops a single catastrophic theatre from defining the entire scale. The rolling
        z-score makes a shock mean &ldquo;unusual against the recent past&rdquo; rather
        than &ldquo;unusual against 2018&rdquo;. Shocks are capped at ±4σ so that one
        methodology change in the source cannot dominate every regression.
      </p>

      <h3>Themes</h3>
      <ul>
        {THEME_ORDER.map((t) => (
          <li key={t}>
            <strong>{THEMES[t].label}</strong> — {THEMES[t].blurb}
            {THEMES[t].countries.length > 0 && (
              <span className="muted"> ({THEMES[t].countries.join(", ")})</span>
            )}
          </li>
        ))}
      </ul>
      <p>
        There are two kinds of theme, and the difference matters for the arithmetic.
        The six regional themes form a <strong>partition</strong>: every country in
        the universe belongs to exactly one of them, so their effects can be added
        into a portfolio total without counting any country twice. Oil supply and
        Global are <strong>overlays</strong>: they cut across regions, so Iran would
        be counted once as a Gulf producer and again as a MENA country. Overlays are
        estimated and displayed on their own, and never enter a total.
      </p>

      <h2>The regression</h2>
      <pre>
        <code>{sens.spec}</code>
      </pre>
      <p>
        <code>r</code> is the simple monthly return of the ETF, computed from the last
        close in each calendar month. <code>z</code> is the theme shock above. For every
        ticker that is not itself a broad US index, SPY&apos;s return enters as a control,
        so the reported coefficient is the conflict response net of &ldquo;the whole
        market moved&rdquo;. Without that control, an energy ETF would look conflict
        sensitive simply by being equity.
      </p>
      <p>
        Standard errors are Newey-West, because conflict intensity is strongly
        autocorrelated and classical standard errors would be optimistically small.
        Sample: {sens.sample.start} to {sens.sample.end}.
      </p>

      <h2>Why most cells are blank</h2>
      <p>
        There are {sens.pairs.length} ticker-theme pairs. Testing that many hypotheses at
        a 5% level would produce two or three &ldquo;significant&rdquo; results from pure
        noise. So a pair has to clear two gates before the app will print a number:
      </p>
      <ol>
        <li>
          <strong>|t| ≥ {sens.tstat_threshold}</strong> on the contemporaneous
          coefficient.
        </li>
        <li>
          <strong>Benjamini-Hochberg</strong> false discovery rate control at q ={" "}
          {sens.fdr_q}, applied once across all {sens.pairs.length} pairs.
        </li>
      </ol>
      <p>
        On this build, {sens.pairs.filter((p) => p.passes_tstat).length} pairs clear the
        first gate and {significant.length} survive the second. The{" "}
        {tOnly.length} in between are exactly the results a less careful version of this
        tool would have reported as findings.
      </p>
      <div className="callout">
        <strong>&ldquo;Not identified&rdquo; is not &ldquo;zero&rdquo;.</strong> A blank
        cell means the data could not distinguish the relationship from noise at this
        sample size. The effect may be real and simply too small or too rare to measure
        with ~{sens.pairs[0]?.n ?? 0} monthly observations.
      </div>

      <h2>What survived</h2>
      {significant.length === 0 ? (
        <p>Nothing cleared both gates on this build.</p>
      ) : (
        <table className="data" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th scope="col">Ticker</th>
              <th scope="col">Theme</th>
              <th scope="col" className="num">
                Per +1σ
              </th>
              <th scope="col" className="num">
                t
              </th>
              <th scope="col" className="num">
                R²
              </th>
              <th scope="col" className="num">
                n
              </th>
            </tr>
          </thead>
          <tbody>
            {significant
              .slice()
              .sort((a, b) => Math.abs(b.tstat) - Math.abs(a.tstat))
              .map((p) => (
                <tr key={`${p.ticker}-${p.theme}`}>
                  <td>
                    <strong>{p.ticker}</strong>{" "}
                    <span className="muted">{TICKERS[p.ticker]?.group}</span>
                  </td>
                  <td>{THEMES[p.theme].label}</td>
                  <td className="num">
                    {p.beta > 0 ? "+" : ""}
                    {Math.round(p.beta * 10000)} bps
                  </td>
                  <td className="num">{p.tstat.toFixed(2)}</td>
                  <td className="num">{p.r2.toFixed(2)}</td>
                  <td className="num">{p.n}</td>
                </tr>
              ))}
          </tbody>
        </table>
      )}

      <h2>Things this tool cannot do</h2>
      <ul>
        <li>
          <strong>It does not forecast.</strong> Every number is a historical average
          response, conditional on a shock that has already been measured. It says
          nothing about whether a shock is coming.
        </li>
        <li>
          <strong>Correlation is not a mechanism.</strong> A significant coefficient may
          reflect a third variable that moves with both conflict and prices. Oil demand,
          for one, moves both.
        </li>
        <li>
          <strong>Monthly resolution is coarse.</strong> A market reaction that plays out
          over three days and reverses is invisible here.
        </li>
        <li>
          <strong>The sample is short.</strong> Roughly {sens.pairs[0]?.n ?? 0} months.
          Tail events, which are exactly the ones a risk tool should care about, are
          barely represented.
        </li>
        <li>
          <strong>Standard error bands assume independence across holdings.</strong> Real
          ETFs overlap, so the bands shown are a floor on the true uncertainty.
        </li>
      </ul>

      <h2>Reproducing it</h2>
      <pre>
        <code>{`cd research
pip install -r requirements.txt
cp .env.example .env      # add your ACLED credentials
python test_auth.py       # confirm event-level access
python build_all.py       # panel, map snapshot, prices, regression
python -m unittest discover tests

cd ..
node scripts/check-artifacts.mjs
npm run dev`}</code>
      </pre>
      <p>
        <code>python build_all.py --fixture</code> runs the whole thing against synthetic
        data with no credentials, which is how the pipeline is tested.
      </p>

      <h2>Attribution and terms</h2>
      <p>
        Conflict data: Armed Conflict Location &amp; Event Data Project (ACLED),{" "}
        <a href="https://acleddata.com">acleddata.com</a>. This is a non-commercial
        research project. It publishes only derived aggregates, never raw ACLED event
        data, and provides no bulk export. Price data is end-of-day closes from public
        endpoints and is not warranted for accuracy.
      </p>
      <p>
        Nothing on this site is investment advice. It is a description of past
        statistical relationships, most of which are weak.
      </p>

      <p style={{ marginTop: 32 }}>
        <Link href="/">← Back to the map</Link>
      </p>
    </main>
  );
}
