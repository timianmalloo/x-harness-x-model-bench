"""The default test run never starts a real model cell (control for defect class SUITE-A).

Tests marked `credentials` use the operator's harness logins and make real model calls. They run only on an
explicit opt-in (`-m ""` or `-m credentials`), never from a bare `pytest`, because a coordination worker that
runs "the full suite" must not start a benchmark cell (owner ruling 3, ADR-0002; ruling R-9).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _collect(*args: str) -> str:
    result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
                            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False)
    return result.stdout


def test_a_bare_run_selects_no_credentials_test():
    out = _collect("tests/e2e")
    assert "tests/e2e/" not in out, out
    assert "deselected" in out, out


def test_the_documented_opt_in_still_selects_them():
    out = _collect("-m", "", "tests/e2e")
    assert "tests/e2e/test_walking_skeleton.py" in out, out
