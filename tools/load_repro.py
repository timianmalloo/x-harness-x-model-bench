"""FLAKE-A load-repro tool: run one test node N times and record the failure rate and each failure's stage.

A counted loop (pytest-repeat is not a dependency). Each run is `uv run pytest <node> -n 4 --dist loadscope`.
A run that ends without a result for the node is a failure with stage "no result", never a pass.

  python tools/load_repro.py <node> --runs N --out record.json
"""

import argparse
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

DEFAULT_PREFIX = ["uv", "run", "pytest", "-n", "4", "--dist", "loadscope"]
HEADER = re.compile(r"^_{2,} (?:ERROR at (setup|teardown) of )?\S+ _{2,}$", re.MULTILINE)
NO_RESULT = "no result"


def _outcome(junit: Path, node: str) -> bool | None:
    """True when the node failed or errored, False when it passed, None when there is no result for it."""
    try:
        cases = [c for c in ET.parse(junit).getroot().iter("testcase") if c.get("name") == node.rsplit("::", 1)[-1]]
    except (OSError, ET.ParseError):
        return None
    if not cases:
        return None
    if any(c.find("failure") is not None or c.find("error") is not None for c in cases):
        return True
    if any(c.find("skipped") is not None for c in cases):
        return None
    return False


def _stage_and_error(output: str) -> tuple[str, str]:
    """The stage of the first failure section in pytest's output, and its first `E` line."""
    match = HEADER.search(output)
    if not match:
        return NO_RESULT, ""
    stage = match.group(1) or "call"
    error = next((ln[1:].strip() for ln in output[match.end():].splitlines() if ln.startswith("E ")), "")
    return stage, error


def _base_sha(cwd) -> str:
    done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return done.stdout.strip() if done.returncode == 0 else "not recorded"


def run_repro(node: str, runs: int, out, prefix=None, cwd=None) -> dict:
    failure_list, walls = [], []
    for run in range(1, runs + 1):
        junit = Path(out).with_name(f"{Path(out).stem}.run{run}.xml")
        junit.unlink(missing_ok=True)
        start = time.monotonic()
        done = subprocess.run(
            [*(prefix or DEFAULT_PREFIX), node, "--junitxml", str(junit)],
            cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        walls.append(round(time.monotonic() - start, 3))
        failed = _outcome(junit, node)
        junit.unlink(missing_ok=True)
        if failed is False:
            continue
        stage, error = _stage_and_error(done.stdout) if failed else (NO_RESULT, "")
        failure_list.append({"run": run, "stage": stage, "first_error": error})
    record = {
        "node": node, "n": runs, "failures": len(failure_list), "rate": len(failure_list) / runs,
        "failure_list": failure_list, "wall_s": walls, "base_sha": _base_sha(cwd),
    }
    Path(out).write_text(json.dumps(record, indent=2), encoding="utf-8", newline="\n")
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("node")
    ap.add_argument("--runs", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    rec = run_repro(args.node, args.runs, args.out)
    print(f"{rec['failures']}/{rec['n']} failed (rate {rec['rate']:.2f}); record {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
