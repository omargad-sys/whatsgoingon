#!/usr/bin/env python3
"""Assert every third-party import in research/ is installed.

    python scripts/check-imports.py

Runs in CI before the pipeline. Catches the case where a module is added to a
script but never added to requirements.txt, which otherwise fails halfway
through a build that has already spent API calls.
"""

import importlib.util
import pathlib
import re
import sys

RESEARCH = pathlib.Path(__file__).resolve().parent.parent / "research"

# import name -> pip name, where they differ
PIP_NAME = {"dotenv": "python-dotenv", "sklearn": "scikit-learn"}
# imported inside try/except with a working fallback
OPTIONAL = {"xgboost"}

STDLIB = set(sys.stdlib_module_names)
LOCAL = {p.stem for p in RESEARCH.glob("*.py")}

pattern = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.M)

missing = []
seen = set()
for path in sorted(RESEARCH.rglob("*.py")):
    for mod in pattern.findall(path.read_text(encoding="utf-8")):
        if mod in STDLIB or mod in LOCAL or mod in seen:
            continue
        seen.add(mod)
        if importlib.util.find_spec(mod) is None:
            entry = (mod, PIP_NAME.get(mod, mod), mod in OPTIONAL)
            missing.append(entry)

hard = [m for m in missing if not m[2]]
soft = [m for m in missing if m[2]]

for mod, pip, _ in soft:
    print(f"note  {mod} not installed; the code falls back. `pip install {pip}` to enable it.")
for mod, pip, _ in hard:
    print(f"FAIL  {mod} is imported but not installed. Add `{pip}` to research/requirements.txt.")

if hard:
    sys.exit(1)
print(f"OK  all {len(seen)} imported modules resolve")
