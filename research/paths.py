"""Canonical paths. Everything is resolved relative to the repo root so the
scripts behave the same whether run from `research/` or from a CI runner."""

import json
from pathlib import Path

RESEARCH_DIR = Path(__file__).resolve().parent
REPO_ROOT = RESEARCH_DIR.parent

# Bulk ACLED event cache. Gitignored.
RAW_DIR = RESEARCH_DIR / "data" / "raw"
INTERIM_DIR = RESEARCH_DIR / "data" / "interim"
FIXTURE_DIR = RESEARCH_DIR / "fixtures"

# Derived artifacts consumed by the Next.js app. Committed.
# They live under public/ so Next serves them directly at /data/<file>, which
# keeps the 1.4 MB heat grid out of the JS bundle: the map fetches it at runtime
# instead of it being inlined into a server component.
GENERATED_DIR = REPO_ROOT / "public" / "data"

WORLD_HEAT = GENERATED_DIR / "world-heat.json"
EVENTS_TOP = GENERATED_DIR / "events-top.geojson"
COUNTRY_MONTHLY = GENERATED_DIR / "country-monthly.json"
SENSITIVITIES = GENERATED_DIR / "sensitivities.json"
FORECAST = GENERATED_DIR / "forecast.json"
LINK = GENERATED_DIR / "link.json"
PRICES = GENERATED_DIR / "prices.json"
MANIFEST = GENERATED_DIR / "manifest.json"


def ensure_dirs():
    for d in (RAW_DIR, INTERIM_DIR, GENERATED_DIR, FIXTURE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def write_json(path, obj, compact=True):
    """Write JSON deterministically so unchanged data produces no git diff."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(obj, separators=(",", ":"), sort_keys=False, allow_nan=False)
    else:
        text = json.dumps(obj, indent=2, sort_keys=False, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")
    kb = len(text) / 1024
    print(f"  wrote {path.relative_to(REPO_ROOT)} ({kb:,.0f} KB)")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
