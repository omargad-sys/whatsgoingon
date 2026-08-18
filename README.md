# What's Going On

A conflict risk analyzer. It puts live political violence data from
[ACLED](https://acleddata.com) on a map, and next to it, an honest answer to the
question "does any of this actually touch my portfolio?"

For most holdings the honest answer is **no**, and the app says so rather than
inventing a number. See [Why most cells are blank](#why-most-cells-are-blank).

```
Python pipeline  ->  committed JSON artifacts  ->  static Next.js app on Vercel
   (weekly CI)          (public/data/)              (no secrets, no runtime API)
```

## What it does

- **Map.** A 180-day window of ACLED events: a binned density heat layer for the
  complete count, plus the most severe individual events as clickable dots.
  Scrub by week, filter by event type and lethality.
- **Themes.** Five conflict baskets (oil supply, Eastern Europe, MENA, East Asia,
  global) with a monthly intensity index and a current-shock reading.
- **Portfolio overlay.** Enter tickers and weights; get the modeled return impact
  of a 1σ escalation in each theme, per holding and in aggregate. The URL encodes
  the portfolio, so a link is shareable.

## Why most cells are blank

Ten tickers × five themes is fifty hypothesis tests. At a naive 5% level, two or
three of them come back "significant" from pure noise. So a relationship must
clear two gates before the app prints a number:

1. `|t| >= 2` on the contemporaneous coefficient, with Newey-West standard errors
2. Benjamini-Hochberg false discovery rate control at `q = 0.10`, applied once
   across all fifty pairs

Everything else renders as **"not identified"** — which is not the same claim as
"zero". Measured on known-null synthetic data, the `|t|` gate alone lets through
4.4% false positives; adding the FDR gate takes that to 0%.

Full write-up at `/methodology`, generated from the actual model output.

## Setup

### 1. ACLED access

Register at [acleddata.com](https://acleddata.com/register/) **with an
institutional (.edu) email**. Personal addresses land on the Open tier, which
serves aggregated data only and has no event-level API — the project cannot work
without event-level data.

```bash
cd research
pip install -r requirements.txt
cp .env.example .env      # add ACLED_EMAIL and ACLED_PASSWORD
python test_auth.py       # confirms auth AND event-level access
```

### 2. Build the data

```bash
cd research
python build_all.py              # panel, map snapshot, prices, regression
python -m unittest discover tests
```

No credentials handy? The entire pipeline runs on synthetic fixtures:

```bash
python build_all.py --fixture
```

Fixture builds stamp `"synthetic": true` into `manifest.json`, and the app shows
a banner saying every number on screen is fake.

### 3. Run the app

```bash
npm install
npm run check     # validates public/data/ before you waste time on a build
npm run dev
```

### 4. Deploy

Import the repo into Vercel. Framework auto-detects, root directory is the repo
root, and **there are no environment variables to set** — the app reads committed
JSON and never calls ACLED at runtime.

Add `ACLED_EMAIL` and `ACLED_PASSWORD` as **GitHub repository secrets** so the
weekly refresh workflow can run. Trigger it once manually from the Actions tab to
confirm it works.

## How the refresh works

`.github/workflows/refresh.yml` runs Mondays. It pulls ACLED, rebuilds every
artifact, validates them, and commits `public/data/` only if something changed.
The commit triggers a Vercel redeploy. Credentials live in GitHub Secrets and
never reach Vercel or the browser.

Weekly rather than daily because Research-tier data is lagged; a daily run would
mostly commit noise.

## Layout

```
app/                    Next.js routes: map dashboard, /methodology
components/             Map, portfolio builder, charts (hand-rolled SVG, no chart lib)
lib/                    exposure math, theme definitions, formatting
public/data/            committed artifacts — the contract between Python and the app
scripts/
  check-artifacts.mjs   schema + sanity validation, runs in CI and on prebuild
research/
  fetch_events.py       ACLED OAuth + paginated fetch
  aggregate.py          events -> country-month panel
  intensity.py          panel -> theme shock z-scores
  ols.py                OLS with Newey-West SEs (no statsmodels dependency)
  build_*.py            the four artifact builders
  build_all.py          runs everything, writes the manifest
  make_fixtures.py      synthetic data with a planted signal, for tests
  tests/                unit tests, stdlib unittest
```

## Design notes

**Why a static site.** ACLED's OAuth issues a 24-hour token, responses cap at 5000
rows, and the EULA is unfriendly to redistributing raw event data. Precomputing in
CI sidesteps all three: no token caching on serverless, no pagination at request
time, and the repo holds only derived aggregates.

**Why the SPY control.** Every non-broad ticker is regressed with SPY's return as a
control, so the reported coefficient is the conflict response net of "the whole
market moved". Without it, an energy ETF looks conflict-sensitive just by being
equity.

**Why log-damped intensity.** Raw event counts trend upward partly because ACLED's
coverage widened. Working with rolling-window z-scores of log severity means a
shock is "unusual against the recent past", not "unusual against 2018".

**Why hand-rolled OLS.** Newey-West is about thirty lines of numpy. Dropping
statsmodels keeps the CI install to four packages.

## Limits

It does not forecast. It reports average historical responses conditional on a
shock that has already been measured, at monthly resolution, over a short sample.
Correlation here is not a mechanism. Nothing in it is investment advice.

## Attribution

Conflict data from the Armed Conflict Location & Event Data Project (ACLED),
[acleddata.com](https://acleddata.com). Non-commercial research project. Publishes
derived aggregates only, never raw ACLED event data, and offers no bulk export.
Price data is end-of-day closes from public endpoints, not warranted for accuracy.
