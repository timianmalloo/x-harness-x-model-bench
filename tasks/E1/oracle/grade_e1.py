"""Run correctness.grade on the base workspace and the reference solution for task E1.

E1 vendors its workspace directly (tasks/E1/workspace/code.png), like E6 -- unlike E4 there is no
task_source() build from a live upstream clone. correctness.grade()'s oracle.runner gate only builds
"unittest" and "dotnet" (src/harness_bench/grade/correctness.py:150,246,388); "pytest" is not merged
yet (the Leader's parallel slice). Both calls below are therefore expected to return an NA Result with
reason "oracle runner 'pytest' not built ..." today -- this script documents that disclosed gap; it is
not the discrimination proof (that is the direct pytest command run and recorded in evidence.md).
"""

import shutil
import tempfile
from pathlib import Path

from harness_bench import archive, config
from harness_bench.grade import correctness


def main() -> None:
    root = config.repo_root()
    task_dir = root / "tasks" / "E1"
    ty = config.load_yaml(task_dir / "task.yaml")
    oracle = ty["oracle"]
    ws_base = task_dir / "workspace"
    ref_dir = task_dir / "oracle" / "reference"

    tmp = Path(tempfile.mkdtemp(prefix="grade-e1-"))
    try:
        # 1. Base workspace: code.png only, no output.txt.
        out_base = tmp / "out_base"
        out_base.mkdir()
        res_base = correctness.grade(ws_base, task_dir, oracle, out_base, tmp, timeout=120.0)
        print("BASE_RESULT:", res_base)

        # 2. Reference solution: code.png plus the reference output.txt overlaid.
        ref_ws = tmp / "ref_ws"
        ref_ws.mkdir()
        shutil.copyfile(ws_base / "code.png", ref_ws / "code.png")
        shutil.copyfile(ref_dir / "output.txt", ref_ws / "output.txt")

        out_ref = tmp / "out_ref"
        out_ref.mkdir()
        res_ref = correctness.grade(ref_ws, task_dir, oracle, out_ref, tmp, timeout=120.0)
        print("REF_RESULT:", res_ref)
    finally:
        shutil.rmtree(tmp, onexc=archive.make_writable)


if __name__ == "__main__":
    main()
