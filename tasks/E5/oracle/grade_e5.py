"""Run correctness.grade on the base workspace and the reference solution for task E5.

E5's task.yaml sets `source.workspace_from: source`, so its base tree is the one the engine's own
`workspace.task_source()` builds -- the pinned pylint-dev/pylint clone at `source.commit` (cached,
verified, fetched via `git archive`), with `tasks/E5/workspace/` overlaid -- and each working copy
is `workspace.cell_working_copy()`'s own `git clone --local`, exactly as a real cell gets it. This
proves the oracle against the tree the engine actually builds, not a working copy this script
clones on its own (ORCL-A; docs/lessons/defect-classes.md), and it proves E5's `runner: pytest`
oracle (the named `--junitxml` report `correctness.grade` now parses) rather than E4's `unittest`
one.
"""

import shutil
import tempfile
from pathlib import Path

from harness_bench import archive, config, workspace
from harness_bench.grade import correctness


def main() -> None:
    root = config.repo_root()
    task_dir = root / "tasks" / "E5"
    ty = config.load_yaml(task_dir / "task.yaml")
    oracle = ty["oracle"]
    ref_dir = task_dir / "oracle" / "reference"

    tmp = Path(tempfile.mkdtemp(prefix="grade-e5-"))
    try:
        # The one task source every cell of this task version would share (workspace.task_source),
        # built from the pinned upstream commit since task.yaml opts in (workspace_from: source).
        source = workspace.task_source(task_dir, "grade-e5-probe", tmp / "sources", tmp / "upstream")

        # 1. Base workspace: a fresh cell working copy of that source, unmodified.
        ws_base = workspace.cell_working_copy(source, tmp / "ws_base")

        out_base = tmp / "out_base"
        out_base.mkdir()
        res_base = correctness.grade(ws_base, task_dir, oracle, out_base, tmp, timeout=300.0)
        print("BASE_RESULT:", res_base)
        print("BASE_LOG:\n", (out_base / "oracle.log").read_text(encoding="utf-8"))

        # 2. Reference solution: a second cell working copy of the same source, with
        #    oracle/reference/ overlaid (the gold patch's one changed file, in full, at its real
        #    repo-relative path).
        ws_ref = workspace.cell_working_copy(source, tmp / "ws_ref")
        shutil.copytree(ref_dir, ws_ref, dirs_exist_ok=True)

        out_ref = tmp / "out_ref"
        out_ref.mkdir()
        res_ref = correctness.grade(ws_ref, task_dir, oracle, out_ref, tmp, timeout=300.0)
        print("REF_RESULT:", res_ref)
        print("REF_LOG:\n", (out_ref / "oracle.log").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, onexc=archive.make_writable)


if __name__ == "__main__":
    main()
