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
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STAMP_REL = Path("tests") / "fixtures" / "gate" / "gate-stamp.yaml"

# The stamped tier (`-m stamped`): the dotnet D1 grader tests and the verdicts coverage tests. It has its OWN stamp so
# a verdicts/stats/power edit never forces the 77-81 minute gate ring (the gate digest above is unchanged). Its digest
# is the gate digest plus these files, which the verdicts coverage tests execute (verdicts.verdict and what it calls).
STAMPED_STAMP_REL = Path("tests") / "fixtures" / "gate" / "stamped-stamp.yaml"
STAMPED_EXTRA_INPUTS = tuple(f"src/harness_bench/{name}.py" for name in ("errors", "power", "stats", "verdicts"))
STAMPED_MAX_AGE = datetime.timedelta(hours=24)  # the once-a-day full run, whatever the digest says


def stamp_path(root: Path | None = None) -> Path:
    return (root or ROOT) / STAMP_REL


def stamped_stamp_path(root: Path | None = None) -> Path:
    return (root or ROOT) / STAMPED_STAMP_REL


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
    # Sort key is the case-folded posix-relative path, not native Path comparison: pathlib's `Path.__lt__`
    # compares case-insensitively on Windows and case-sensitively on POSIX, so a bare `sorted(...)` here
    # would put this digest's own file order at risk of the same cross-host mismatch that hit
    # plan.tree_hash's tasks/<ID> ordering (ADR-0013 Amendment 1, macOS port; see plan.py's tree_hash
    # docstring for the verified cause). No filename in grade/ collides under case-folding today, but the
    # explicit key removes the platform dependency rather than relying on that happening to stay true.
    grade_dir = repo_root / "src" / "harness_bench" / "grade"
    grade_files = sorted(
        (p for p in grade_dir.rglob("*.py") if "__pycache__" not in p.parts and p.is_file()),
        key=lambda p: p.relative_to(repo_root).as_posix().casefold(),
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


def compute_stamped_digest(root: Path | None = None) -> str:
    repo_root = (root or ROOT).resolve()
    h = hashlib.sha256(compute_digest(repo_root).encode() + b"\0")
    for rel in STAMPED_EXTRA_INPUTS:
        h.update(rel.encode() + b"\0")
        h.update((repo_root / rel).read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def stamped_stale(root: Path | None = None, now: datetime.datetime | None = None) -> str | None:
    """Why `-m stamped` must run (a reason), or None when the stamp is current and under a day old. Never raises."""
    target = stamped_stamp_path(root)
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
        digest, renewed = str(data["digest"]), datetime.datetime.fromisoformat(str(data["renewed"]))
    except (OSError, ValueError, KeyError, TypeError):
        return "no readable stamped stamp"
    if digest != compute_stamped_digest(root):
        return "stamped inputs changed"
    if (now or datetime.datetime.now(datetime.UTC)) - renewed > STAMPED_MAX_AGE:
        return "daily full run due"
    return None


def read_stamp(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Stamp file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "digest" not in data:
        raise ValueError(f"Invalid stamp file {path}: missing 'digest' field")
    return str(data["digest"])


def write_stamp(path: Path, digest: str, renewed: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if renewed is None:
        body = (
            "# Pinned grader inputs stamp. Renew via: python tools/gate_stamp.py --renew\n"
            "schema: bench-gate-stamp/1\n"
            f"digest: {digest}\n"
        )
    else:
        body = (
            "# Stamped-tier stamp. Renew via: python tools/gate_stamp.py --renew-stamped\n"
            "schema: bench-stamped-stamp/1\n"
            f"digest: {digest}\n"
            f"renewed: {renewed}\n"
        )
    path.write_text(body, encoding="utf-8", newline="\n")  # LF on every OS (.gitattributes eol=lf)


def renew(root: Path | None = None, *, stamped: bool = False) -> int:
    repo_root = (root or ROOT).resolve()
    marker = "stamped" if stamped else "gate"
    venv_pytest = repo_root / ".venv" / "Scripts" / "pytest.exe"
    if venv_pytest.is_file():
        cmd = [str(venv_pytest), "-m", marker]
    elif shutil.which("pytest"):
        cmd = [shutil.which("pytest"), "-m", marker]
    else:
        cmd = [sys.executable, "-m", "pytest", "-m", marker]
    if stamped:
        cmd += ["-n", "4"]  # the 450 s D1 test bounds the wall time either way; the rest overlaps it
    env = {**os.environ, "HB_REQUIRE_DOTNET": "1"} if stamped else None  # a skipped stamped test proves nothing

    proc = subprocess.run(cmd, cwd=repo_root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
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

    if stamped:
        digest, target = compute_stamped_digest(repo_root), stamped_stamp_path(repo_root)
        write_stamp(target, digest, datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"))
        print(f"Renewed stamped stamp {target}: {digest}")
        return 0
    digest = compute_digest(repo_root)
    target = stamp_path(repo_root)
    write_stamp(target, digest)
    print(f"Renewed gate stamp {target}: {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the gate ring input digest stamp.")
    parser.add_argument("--print", action="store_true", dest="print_digest", help="Print current digest")
    parser.add_argument("--renew", action="store_true", help="Run pytest -m gate and renew stamp on pass")
    parser.add_argument("--print-stamped", action="store_true", help="Print the stamped-tier digest")
    parser.add_argument("--check-stamped", action="store_true",
                        help="Exit 1 (naming why) when `pytest -m stamped` must run: inputs moved, no stamp, or older than a day")
    parser.add_argument("--renew-stamped", action="store_true",
                        help="Run pytest -m stamped (HB_REQUIRE_DOTNET=1) and renew the stamped stamp on pass")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root path")
    args = parser.parse_args(argv)

    if args.print_digest:
        print(compute_digest(args.root))
        return 0

    if args.renew:
        return renew(args.root)

    if args.print_stamped:
        print(compute_stamped_digest(args.root))
        return 0

    if args.check_stamped:
        reason = stamped_stale(args.root)
        print(reason or "stamped stamp current")
        return 1 if reason else 0

    if args.renew_stamped:
        return renew(args.root, stamped=True)

    parser.print_help()
    return 1


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    sys.exit(main())
