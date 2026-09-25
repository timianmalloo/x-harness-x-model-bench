"""Hidden tests for A1 (never in the cell's working copy). Stdlib only: run with `python -m unittest`.

The cases are LiveCodeBench's tests for AtCoder abc396_c ("Buy Balls"), 3 public and 40 private,
stored verbatim in `a1_cases.json` (provenance and licence: ../NOTICE.md). Each case is one test, so
the unittest summary counts cases and the correctness grader's partial credit is the fraction passed.

The check ports LiveCodeBench's stdio rule (lcb_runner/evaluation/testing_util.py, `get_stripped_lines`
and `grade_stdio`, at LiveCodeBench 28fef95): strip the whole output, split on newlines, strip each
line; the line counts must be equal; each line matches exactly or as a list of Decimals. LiveCodeBench's
own runner cannot run here: it times cases with `signal.alarm`, which Windows does not have. So each
case runs `solution.py` as a child process under LiveCodeBench's default per-case timeout (6 s,
lcb_runner/runner/parser.py `--timeout`).
"""

import json
import subprocess
import sys
import unittest
from decimal import Decimal, InvalidOperation
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLUTION = HERE / "solution.py"
CASES = json.loads((HERE / "a1_cases.json").read_text(encoding="utf-8"))
TIMEOUT_SECONDS = 6


def stripped_lines(text: str) -> list[str]:
    return [line.strip() for line in text.strip().split("\n")]


def decimals(line: str) -> list[Decimal] | None:
    try:
        return [Decimal(part) for part in line.split()]
    except InvalidOperation:
        return None


def mismatch(got: str, want: str) -> str | None:
    """None when LiveCodeBench's stdio rule accepts got for want, else the reason."""
    got_lines, want_lines = stripped_lines(got), stripped_lines(want)
    if len(got_lines) != len(want_lines):
        return f"line count {len(got_lines)} != {len(want_lines)}"
    for i, (g, w) in enumerate(zip(got_lines, want_lines)):
        if g == w:
            continue
        gd, wd = decimals(g), decimals(w)
        if gd is None or wd is None or gd != wd:
            return f"line {i}: {g[:80]!r} != {w[:80]!r}"
    return None


class HiddenBuyBalls(unittest.TestCase):
    def run_case(self, case: dict) -> None:
        try:
            done = subprocess.run([sys.executable, str(SOLUTION)], input=case["input"], capture_output=True,
                                  text=True, encoding="utf-8", timeout=TIMEOUT_SECONDS, cwd=HERE, check=False)
        except subprocess.TimeoutExpired:
            self.fail(f"time limit exceeded ({TIMEOUT_SECONDS} s)")
        self.assertEqual(done.returncode, 0, f"runtime error: {done.stderr.strip()[-300:]}")
        reason = mismatch(done.stdout, case["output"])
        self.assertIsNone(reason, f"wrong answer: {reason}")


def _make(case: dict):
    return lambda self: self.run_case(case)


for _kind in ("public", "private"):
    for _i, _case in enumerate(CASES[_kind], 1):
        setattr(HiddenBuyBalls, f"test_{_kind}_{_i:02d}", _make(_case))


if __name__ == "__main__":
    unittest.main()
