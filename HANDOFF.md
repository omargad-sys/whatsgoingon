# Where this stands

Last updated 2026-08-19.

## Do this first

All the code below is committed and pushed. `main` is in sync with origin.
Only one thing is left, and it is the important one:

GitHub, **Actions -> Refresh data -> Run workflow**, defaults, start it, walk away.

That run is the whole ballgame. It is the first time this pipeline will ever
have touched real ACLED data. It replaces every synthetic location, every fake
number, and the placeholder share card. Expect it to take an hour or more on a
cold cache.

If it fails, the log is the thing to read, not the code.

## The finding that reframed the project

`check_coverage.py` came back with all five probe countries stopping on the
exact same day, 2025-08-19, which was exactly 364 days before the run. Five
unrelated conflicts do not end on the same Tuesday. That is a rolling one-year
embargo.

ACLED sells four tiers. Open gets aggregated data only. **Research**, which is
what an academic email gets, gets event-level data lagged. Partner and
Enterprise get weekly. This account is Research, so twelve months back is the
freshest event data it will ever return. Re-running does not change it.

So the map is a picture of last year: real coordinates, real place names, real
fatality counts, independently coded, and twelve months stale. Real and old
instead of fake and current.

The site now says this out loud. Before, the only freshness figure on screen
read off the pipeline run time and would have said "refreshed today" over
year-old events.

**The open question worth pursuing:** whether NJIT has an institutional ACLED
agreement, or whether a student project qualifies for Partner access. Weekly
data turns this from a historical tool into a live one. That is a conversation
with ACLED, not code, and it is the highest-leverage thing left.

## What changed today

Four commits, all on `main`, all pushed.

### `20ca2bf` themes are now a partition plus overlays

Two structural bugs that corrupted every portfolio number:

- Iran, Iraq and Yemen were in both `oil_supply` and `mena`, and both were
  summed into the holdings total. Gulf escalation was counted twice.
- Only 30 of 52 countries belonged to any theme. Mozambique could top the
  escalation risk list while being structurally incapable of moving a single
  portfolio figure.

Six regional themes now partition the universe, every country in exactly one,
so summing them is valid. `oil_supply` and `global` became overlays: estimated
and displayed, never added to a total. Summation filters on `PARTITION_THEMES`
rather than special-casing `global` by name.

Guards: three Python tests and two TS tests assert disjointness, full coverage,
and that overlays stay out of totals. `lib/themes.ts` and the `ThemeId` union
are generated from `universe.py`, not hand-maintained.

### `e4bac43` the coverage probe is now cheap

`check_coverage.py` and `build_snapshot.discover_latest` both answered "what is
the last date this account can read" by pulling entire country-years. Ukraine
is tens of thousands of rows in 5000-row pages. The first probe sat for minutes
with no output, looked like a hang, and burned quota in CI before the real
fetch began.

`latest_event_date()` walks back a month at a time asking for one row and one
field, then binary searches the hit month for the exact day. Worst case is
about twelve tiny requests.

The binary search also fixes a correctness bug the old approach would have had
anyway: a single Ukraine month exceeds the 5000-row cap, so taking the max over
a truncated page returns whatever the API ordered first, not the real last day.

### `19f479e` the site states its own staleness

A banner above the fold with the real cutoff and the gap in words, a
methodology section at `#lag` explaining the tier and what it costs the
forecast layer, and a footer line that leads with the event cutoff instead of
the build time.

The lag is computed from `manifest.acled.last_week`, not hardcoded, so the
banner turns itself off if the account is ever upgraded. `dataLag(null)`
returns null rather than zero days, because zero would render as "current",
which is the one claim a missing value must never make.

### `bca3121` workflow fixes

The refresh job staged only `public/data`, so `build_og.py` regenerated
`public/og.png` every run and the workflow discarded it. Link previews
described the previous run's data. Timeout raised 90 to 300 minutes, because a
cold-cache first run pulling nine years across 52 countries can exceed 90, and
a timeout discards every API call already spent.

## Standing decisions

- No Claude attribution anywhere in this repo. A stop hook asks to reauthor the
  commits on roughly every turn. The answer is no every time. The "Unverified"
  badge on GitHub is just the absence of a GPG signature and affects nothing.
- Never handle the ACLED password. Omar wires his own credentials; everything
  is built against synthetic fixtures until the Action runs.
- Vercel builds `main`. Pushing to a feature branch deploys nothing. This cost
  several rounds of "still no map" earlier in the project.
- Tanker and oil-rig AIS layer is deferred, explicitly.

## Gotchas that will bite again

- **Running git through the Cowork device bridge is unreliable.** The mount
  cannot delete files, so git leaves stale `.git/index.lock` behind and later
  commands fail with "another git process seems to be running". Run git from
  PowerShell in the real folder. `_to_delete/` holds files the bridge could not
  remove; delete it in Explorer.
- Local repo config was set to `core.fileMode=false` and `core.autocrlf=input`
  because working through the Linux mount was making all 68 files show as
  modified. Leave those set.
- `npm run build` over the mounted filesystem is extremely slow, eight minutes
  without getting past `next build`. Not a failure. Push and let Vercel build.
- The `bun:test` import in `lib/chain.test.ts` makes `npx tsc --noEmit` report
  one error. Pre-existing, harmless, `next build` does not care.
- "Synthetic Location" in map popups is the literal contents of the fixture
  data, not a display bug. `make_fixtures.py` writes it deliberately so fake
  data can never be mistaken for real. The plumbing for real names already
  works: `build_snapshot.py` carries `location`, `admin1` and `country` into
  the geojson.

## Verification commands

```powershell
bun test                                  # 26 pass
cd research; python -m unittest discover tests   # 32 pass
node scripts/check-artifacts.mjs
python scripts/check-imports.py
```

## After the Action succeeds

- Confirm the synthetic banner is gone and the lag banner has appeared with a
  real date.
- Click a map dot and confirm the popup reads like "Kramatorsk, Donetsk,
  Ukraine" rather than "Synthetic Location".
- Check whether the XGBoost forecaster beats the persistence baseline on the
  real 52-country panel. On the 5-country panel the baseline won at 0.962. If
  the baseline wins again, the app ships the baseline and says so, which is the
  designed behaviour, not a failure.
- Look at how many of the 80 ticker-theme pairs survive the t-gate and the FDR
  gate. Expect very few. That is the honest answer, and the suppression rule is
  the product's credibility.
- Load the site on a real phone.
