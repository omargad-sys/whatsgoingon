#!/usr/bin/env python3
"""Assert every third-party import in research/ is installed.

    python scripts/check-imports.py

Runs in CI before the pipeline. Catches the case where a module is added to a
script but never added to requirements.txt, which otherwise fails halfway
through a build that has already spent API calls.
"""

import ast
import importlib.util
import pathlib
import sys

RESEARCH = pathlib.Path(__file__).resolve().parent.parent / "research"

# import name -> pip name, where they differ
PIP_NAME = {"dotenv": "python-dotenv", "sklearn": "scikit-learn"}
# imported inside try/except with a working fallback
OPTIONAL = {"xgboost"}

STDLIB = set(sys.stdlib_module_names)


def imported_modules(source, filename="<string>"):
    """Root module name of every import in a file, via the syntax tree.

    This used to be a regex over the raw text, which meant any line that merely
    began with the word "from" or "import" was read as an import. A docstring
    sentence starting "from every theme it belongs to" was reported as a
    missing package called `every`, and the CI step that runs this check would
    have failed the build over a piece of prose. A parser cannot make that
    mistake: strings, comments and identifiers are different node types.
    """
    tree = ast.parse(source, filename=str(filename))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            # level > 0 is a relative import (`from . import x`), always local.
            if node.level == 0 and node.module:
                yield node.module.split(".")[0]


def scan(research_dir):
    """-> (seen_count, [(module, pip_name, is_optional)]) for what is missing."""
    local = {p.stem for p in research_dir.glob("*.py")}
    missing = []
    seen = set()
    for path in sorted(research_dir.rglob("*.py")):
        try:
            mods = list(imported_modules(path.read_text(encoding="utf-8"), path))
        except SyntaxError as err:
            raise SyntaxError(f"{path}: {err}") from err
        for mod in mods:
            if mod in STDLIB or mod in local or mod in seen:
                continue
            seen.add(mod)
            if importlib.util.find_spec(mod) is None:
                missing.append((mod, PIP_NAME.get(mod, mod), mod in OPTIONAL))
    return len(seen), missing


def main():
    try:
        count, missing = scan(RESEARCH)
    except SyntaxError as err:
        print(f"FAIL  {err}")
        return 1

    hard = [m for m in missing if not m[2]]
    soft = [m for m in missing if m[2]]

    for mod, pip, _ in soft:
        print(f"note  {mod} not installed; the code falls back. `pip install {pip}` to enable it.")
    for mod, pip, _ in hard:
        print(f"FAIL  {mod} is imported but not installed. Add `{pip}` to research/requirements.txt.")

    if hard:
        return 1
    print(f"OK  all {count} imported modules resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
