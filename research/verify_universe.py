"""Check that every country in the universe actually came back with data.

    cd research && python verify_universe.py

Reads the built panel. No credentials, no network, no API calls.

Why this exists: ACLED matches the `country` filter exactly. A name that is
spelled differently on their side than in `universe.py` does not raise an
error, it returns zero rows. The country then quietly vanishes from the panel,
from every theme it belonged to, and from the forecast, and nothing anywhere
says so. `universe.py` has claimed since the first commit that this script
guards against exactly that. It did not exist until now.

Two kinds of problem it reports:

  MISSING   in COUNTRIES but absent from the panel. Almost always a name
            mismatch, since ACLED covers essentially every country.
  SILENT    present but zero events across the entire window. Legitimate for a
            genuinely quiet country, suspicious for anywhere else.

Exits non-zero only with --strict, so it can be run as a report inside a
pipeline without turning a naming quibble into a lost hour of fetching.
"""

import argparse
import sys

from paths import COUNTRY_MONTHLY, read_json
from universe import COUNTRIES, OVERLAY_THEMES, PARTITION_THEMES, THEMES

# Countries that can plausibly record no political violence at all in a window.
# Everywhere else, zero is a bug until proven otherwise.
PLAUSIBLY_QUIET = {"Qatar", "Oman", "Bahrain", "United Arab Emirates", "Kuwait"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if any country is missing or unexpectedly silent",
    )
    args = ap.parse_args()

    if not COUNTRY_MONTHLY.exists():
        print(f"No panel at {COUNTRY_MONTHLY}. Run build_panel.py first.")
        return 1

    panel = read_json(COUNTRY_MONTHLY)
    present = panel.get("countries", {})
    months = panel.get("months", [])

    print(f"Panel: {len(present)} countries x {len(months)} months")
    print(f"Universe: {len(COUNTRIES)} countries\n")

    missing = [c for c in COUNTRIES if c not in present]
    extra = [c for c in present if c not in COUNTRIES]

    silent = []
    for name in COUNTRIES:
        series = present.get(name)
        if not series:
            continue
        if sum(series.get("events", [])) == 0:
            silent.append(name)

    unexpected_silent = [c for c in silent if c not in PLAUSIBLY_QUIET]

    if missing:
        print(f"MISSING ({len(missing)}) - in the universe, absent from the panel:")
        for c in missing:
            print(f"  {c}")
        print("  Check the spelling against ACLED's `country` field. A mismatch")
        print("  returns zero rows silently rather than erroring.\n")

    if silent:
        print(f"SILENT ({len(silent)}) - present but zero events in the whole window:")
        for c in silent:
            tag = "" if c in PLAUSIBLY_QUIET else "   <-- unexpected"
            print(f"  {c}{tag}")
        print()

    if extra:
        print(f"EXTRA ({len(extra)}) - in the panel but not in the universe:")
        for c in extra:
            print(f"  {c}")
        print()

    # A country that is missing or silent is also silently absent from whatever
    # theme it belongs to, which is the part that actually corrupts numbers.
    dropped = set(missing) | set(unexpected_silent)
    if dropped:
        print("Theme coverage lost:")
        for theme in PARTITION_THEMES + OVERLAY_THEMES:
            members = set(THEMES[theme]["countries"])
            hit = sorted(dropped & members)
            if hit:
                kind = "partition" if theme in PARTITION_THEMES else "overlay"
                print(f"  {theme} ({kind}): {len(hit)}/{len(members)} lost - {', '.join(hit)}")
        print()

    if not missing and not unexpected_silent:
        print("OK: every country in the universe is present and non-empty.")
        if silent:
            print(f"     ({len(silent)} quiet by expectation: {', '.join(silent)})")
        return 0

    print(
        f"{len(missing)} missing, {len(unexpected_silent)} unexpectedly silent."
    )
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
