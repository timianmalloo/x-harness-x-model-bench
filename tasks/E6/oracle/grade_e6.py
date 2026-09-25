"""Run correctness.grade on base workspace and reference solution for task E6."""

import shutil
import tempfile
from pathlib import Path
from harness_bench import config
from harness_bench.grade import correctness

def main():
    root = config.repo_root()
    task_dir = root / "tasks" / "E6"
    ty = config.load_yaml(task_dir / "task.yaml")
    oracle = ty["oracle"]
    ws_base = task_dir / "workspace"
    ref_dir = task_dir / "oracle" / "reference"

    tmp = Path(tempfile.mkdtemp(prefix="grade-e6-"))
    try:
        # 1. Base workspace run
        out_base = tmp / "out_base"
        out_base.mkdir()
        res_base = correctness.grade(ws_base, task_dir, oracle, out_base, tmp, timeout=120.0)
        print("BASE_RESULT:", res_base)
        base_log = (out_base / "oracle.log").read_text(encoding="utf-8")
        print("BASE_LOG:\n", base_log)

        # 2. Reference solution run
        # Reference folder holds Problem.cs; compose temporary working copy with E6.csproj
        ref_ws = tmp / "ref_ws"
        ref_ws.mkdir()
        shutil.copyfile(ws_base / "E6.csproj", ref_ws / "E6.csproj")
        shutil.copyfile(ref_dir / "Problem.cs", ref_ws / "Problem.cs")

        out_ref = tmp / "out_ref"
        out_ref.mkdir()
        res_ref = correctness.grade(ref_ws, task_dir, oracle, out_ref, tmp, timeout=120.0)
        print("REF_RESULT:", res_ref)
        ref_log = (out_ref / "oracle.log").read_text(encoding="utf-8")
        print("REF_LOG:\n", ref_log)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
