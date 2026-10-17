"""The lint gate: the bench's own code (src, tests, tools) is ruff-clean under the repo's own config.

`ruff check` with no path reads `[tool.ruff]` in pyproject.toml, so every machine lints the same files with the same
pinned ruff (its default rules; the version is pinned in the dev dependencies). Task workspaces and oracles (`tasks/`)
are upstream, task-versioned code, `bench/` holds calibration fixtures, and `docs/ai-forward-pack/` is the pack's
managed copy: none is linted here (finding of 2026-10-17: 1,899 hits there, 1 in the bench's own code).
"""

import subprocess
import sys
from pathlib import PurePosixPath

from archived_runs import ROOT

LINTED = {"src", "tests", "tools"}


def _ruff(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "ruff", "check", "--no-cache", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", timeout=300, check=False,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def test_ruff_with_no_path_lints_exactly_src_tests_and_tools():
    listed = _ruff("--show-files")
    assert listed.returncode == 0, listed.stderr
    tops = {PurePosixPath(ROOT.joinpath(line.strip()).relative_to(ROOT).as_posix()).parts[0]
            for line in listed.stdout.splitlines() if line.strip()}
    assert tops == LINTED, sorted(tops)


def test_the_benchs_own_code_is_ruff_clean():
    done = _ruff("--output-format", "concise")
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-1000:]
