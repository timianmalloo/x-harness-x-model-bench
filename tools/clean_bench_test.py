"""Remove the folders tests leave under the clean parent (C:/Projects/bench-test), defect class CLN-A.

Only folders the test suite and the coordination tooling create are candidates:
- a random hex name (`tests/conftest.py`'s `base`);
- `e2e-<n>` (a kept E2E run);
- `tmp<...>`;
- `verify-*` / `cr-*` (throwaway verification and mutation shards);
- `race-*`.

Anything else, for example the `repro-*` runs the fixtures cite, is listed and kept.

Dry run by default. `--delete` removes each candidate. Read-only files (git objects) are made writable first, and
every folder that still cannot be removed is reported with its error. A file another process holds open shows as
WinError 32. The exit status is 1 if anything could not be removed.

Usage: python tools/clean_bench_test.py [--root C:/Projects/bench-test] [--delete]
"""

import argparse
import os
import re
import shutil
import stat
import sys
from pathlib import Path

CANDIDATE = re.compile(r"^(?:[0-9a-f]{8,32}|e2e-\d+|tmp\w+|verify-.+|cr-.+|race-.+)$")


def _writable(func, path, _exc) -> None:
    os.chmod(path, stat.S_IWRITE)
    func(path)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="C:/Projects/bench-test")
    ap.add_argument("--delete", action="store_true", help="remove the candidates (default: list them)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"nothing to do: {root} does not exist")
        return 0
    children = sorted(p for p in root.iterdir() if p.is_dir())
    candidates = [p for p in children if CANDIDATE.match(p.name)]
    kept = [p for p in children if p not in candidates]
    print(f"{len(candidates)} test folder(s) under {root}; kept (not test-made): {[p.name for p in kept]}")
    if not args.delete:
        print("dry run: pass --delete to remove them")
        return 0
    failed = []
    for p in candidates:
        try:
            shutil.rmtree(p, onexc=_writable)
        except OSError as exc:
            failed.append((p.name, exc))
    for name, exc in failed:
        print(f"not removed: {name}: {exc}")
    print(f"removed {len(candidates) - len(failed)} of {len(candidates)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
