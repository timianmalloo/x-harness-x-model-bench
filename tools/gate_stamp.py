"""The gate ring input digest and stamp manager (Rank 1 of CI-OPT proposal).

Computes a deterministic SHA-256 over all inputs to the frozen gate characterizations:
1. sorted bytes of src/harness_bench/grade/**/*.py (relative path and normalized content),
2. tasks/D1's task_version_hash,
3. bench/metrics.yaml (relative path and normalized content),
4. bench/regrade-baseline-0.3.yaml (relative path and normalized content),
5. pinned tool versions: dotnet SDK version from tasks/D1/workspace/global.json and
   Stryker version constant in src/harness_bench/grade/mutation.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STAMP_REL = Path("tests") / "fixtures" / "gate" / "gate-stamp.yaml"


def stamp_path(root: Path | None = None) -> Path:
    return (root or ROOT) / STAMP_REL


def extract_stryker_version(mutation_file: Path) -> str:
    content = mutation_file.read_text(encoding="utf-8")
    match = re.search(r'STRYKER_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError(f"STRYKER_VERSION constant not found in {mutation_file}")
    return match.group(1)


def extract_dotnet_sdk_version(global_json_file: Path) -> str:
    data = json.loads(global_json_file.read_text(encoding="utf-8"))
    return str(data["sdk"]["version"])


def compute_digest(root: Path | None = None) -> str:
    repo_root = (root or ROOT).resolve()
    h = hashlib.sha256()

    # 1. Sorted bytes of src/harness_bench/grade/**/*.py (path and content)
    grade_dir = repo_root / "src" / "harness_bench" / "grade"
    grade_files = sorted(
        p for p in grade_dir.rglob("*.py")
        if "__pycache__" not in p.parts and p.is_file()
    )
    for p in grade_files:
        rel = p.relative_to(repo_root).as_posix().encode()
        content = p.read_bytes().replace(b"\r\n", b"\n")
        h.update(rel + b"\0")
        h.update(content + b"\0")

    # 2. tasks/D1's task_version_hash
    # Import locally or dynamically so tools/gate_stamp can be run independently
    try:
        from harness_bench.plan import task_version_hash
    except ImportError:
        sys.path.insert(0, str(repo_root / "src"))
        from harness_bench.plan import task_version_hash
    d1_hash = task_version_hash(repo_root / "tasks" / "D1")
    h.update(b"tasks/D1:task_version_hash\0")
    h.update(d1_hash.encode() + b"\0")

    # 3. bench/metrics.yaml
    metrics_path = repo_root / "bench" / "metrics.yaml"
    metrics_content = metrics_path.read_bytes().replace(b"\r\n", b"\n")
    h.update(b"bench/metrics.yaml\0")
    h.update(metrics_content + b"\0")

    # 4. bench/regrade-baseline-0.3.yaml
    baseline_path = repo_root / "bench" / "regrade-baseline-0.3.yaml"
    baseline_content = baseline_path.read_bytes().replace(b"\r\n", b"\n")
    h.update(b"bench/regrade-baseline-0.3.yaml\0")
    h.update(baseline_content + b"\0")

    # 5. Pinned tool versions: dotnet SDK version from global.json and Stryker version from mutation.py
    global_json = repo_root / "tasks" / "D1" / "workspace" / "global.json"
    dotnet_ver = extract_dotnet_sdk_version(global_json)
    mutation_py = repo_root / "src" / "harness_bench" / "grade" / "mutation.py"
    stryker_ver = extract_stryker_version(mutation_py)

    tools_line = f"dotnet:{dotnet_ver}\nstryker:{stryker_ver}\n".encode()
    h.update(b"pinned_tool_versions\0")
    h.update(tools_line + b"\0")

    return h.hexdigest()


def read_stamp(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Stamp file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "digest" not in data:
        raise ValueError(f"Invalid stamp file {path}: missing 'digest' field")
    return str(data["digest"])


def write_stamp(path: Path, digest: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# Pinned grader inputs stamp. Renew via: python tools/gate_stamp.py --renew\n"
        "schema: bench-gate-stamp/1\n"
        f"digest: {digest}\n"
    )
    path.write_text(body, encoding="utf-8")


def renew(root: Path | None = None) -> int:
    repo_root = (root or ROOT).resolve()
    venv_pytest = repo_root / ".venv" / "Scripts" / "pytest.exe"
    if venv_pytest.is_file():
        cmd = [str(venv_pytest), "-m", "gate"]
    elif shutil.which("pytest"):
        cmd = [shutil.which("pytest"), "-m", "gate"]
    else:
        cmd = [sys.executable, "-m", "pytest", "-m", "gate"]

    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
    output = proc.stdout + "\n" + proc.stderr

    if proc.returncode == 5:
        sys.stderr.write("Refusing to write stamp: pytest exited 5 (no tests ran).\n")
        return 5

    if proc.returncode != 0:
        sys.stderr.write(f"Refusing to write stamp: pytest exited with error {proc.returncode}.\n")
        sys.stderr.write(output)
        return proc.returncode

    match = re.search(r"(\d+) passed", output)
    passed_count = int(match.group(1)) if match else 0
    if passed_count == 0:
        sys.stderr.write("Refusing to write stamp: 0 tests passed (at least one test must run and pass).\n")
        sys.stderr.write(output)
        return 1
    if re.search(r"\b\d+ skipped\b", output):  # a skipped gate test proved nothing (e.g. HB_GATE_RUNS unset)
        sys.stderr.write("Refusing to write stamp: a gate test was skipped; every gate test must run and pass.\n")
        sys.stderr.write(output)
        return 1

    digest = compute_digest(repo_root)
    target = stamp_path(repo_root)
    write_stamp(target, digest)
    print(f"Renewed gate stamp {target}: {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the gate ring input digest stamp.")
    parser.add_argument("--print", action="store_true", dest="print_digest", help="Print current digest")
    parser.add_argument("--renew", action="store_true", help="Run pytest -m gate and renew stamp on pass")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root path")
    args = parser.parse_args(argv)

    if args.print_digest:
        print(compute_digest(args.root))
        return 0

    if args.renew:
        return renew(args.root)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
