"""Archive a finished cell to runs/<run_id>/<cell_id>/, then tear down. Archive first, delete second.

Artifacts: diff.patch, test output, harness JSON summary, session log, OTel export, wall clock, exit status.
A failed archive blocks teardown. Spec: S-05 (docs/specs/README.md).
"""

from pathlib import Path


def archive(workspace: Path, run_dir: Path) -> None:
    raise NotImplementedError("runner.archive is not built yet; spec S-05")
