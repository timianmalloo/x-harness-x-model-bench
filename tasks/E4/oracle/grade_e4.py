"""Run correctness.grade on the base workspace and the reference solution for task E4.

Unlike E6/D2 (authored/vendored workspaces), E4's workspace is not vendored into this repo
(see workspace/README.md): it is the pinned upstream django/django clone at source.commit. This
script builds that clone itself (git clone + checkout, network required, matching what a real
cell bootstrap would do per ADR-0013 Amendment 1) rather than reading tasks/E4/workspace/.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from harness_bench import archive, config
from harness_bench.grade import correctness


def _clone(repo: str, commit: str, dest: Path) -> None:
    subprocess.run(["git", "clone", "--quiet", repo, str(dest)], check=True)
    subprocess.run(["git", "checkout", "--quiet", commit], check=True, cwd=dest)


def main() -> None:
    root = config.repo_root()
    task_dir = root / "tasks" / "E4"
    ty = config.load_yaml(task_dir / "task.yaml")
    oracle = ty["oracle"]
    source = ty["source"]
    ref_dir = task_dir / "oracle" / "reference"

    tmp = Path(tempfile.mkdtemp(prefix="grade-e4-"))
    try:
        # 1. Base workspace: the pinned upstream commit, unmodified.
        ws_base = tmp / "ws_base"
        _clone(source["repo"], source["commit"], ws_base)

        out_base = tmp / "out_base"
        out_base.mkdir()
        res_base = correctness.grade(ws_base, task_dir, oracle, out_base, tmp, timeout=300.0)
        print("BASE_RESULT:", res_base)
        print("BASE_LOG:\n", (out_base / "oracle.log").read_text(encoding="utf-8"))

        # 2. Reference solution: the base clone with oracle/reference/ overlaid (the gold patch's
        #    two changed files, in full, at their real repo-relative paths).
        ws_ref = tmp / "ws_ref"
        shutil.copytree(ws_base, ws_ref, ignore=shutil.ignore_patterns(".git"))
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
