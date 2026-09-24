"""Red-observation by targeted mutation: remove one guard at a time and require a named test file to fail.

Each mutation is (file, exact text, replacement). The file is restored afterwards, even on error.
Exit 0 only if every mutation made the suite fail (a surviving mutation means that guard is untested).

Usage: python tools/mutate_check.py <mutations.json>
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    survivors = 0
    for m in spec:
        path = ROOT / m["file"]
        original = path.read_text(encoding="utf-8")
        if m["find"] not in original:
            print(f"SKIP {m['name']}: text not found", flush=True)
            survivors += 1
            continue
        try:
            path.write_text(original.replace(m["find"], m["replace"], 1), encoding="utf-8")
            try:
                result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", *m["tests"]], cwd=ROOT,
                                        capture_output=True, text=True, check=False, timeout=m.get("timeout", 180))
                killed = result.returncode != 0
            except subprocess.TimeoutExpired:  # the suite could not pass: the mutation is caught (as a hang)
                killed = True
            print(f"{'killed  ' if killed else 'SURVIVED'} {m['name']}", flush=True)
            survivors += 0 if killed else 1
        finally:
            path.write_text(original, encoding="utf-8")
    print(f"{survivors} survivor(s)" if survivors else "every mutation killed", flush=True)
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
