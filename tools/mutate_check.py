"""Red-observation by targeted mutation: remove one guard at a time and require a named test to fail.

Each mutation is (file, exact text, replacement, named tests). The file is restored byte for byte afterwards, even
on error. A mutation is **killed** only when pytest exits 1 and one of its named tests (a node id, or a test file
meaning any test in it) is among the failures. A failure of some other test, a collection error, or a timeout is
not evidence that this guard is tested, so it is reported as survived, error or timeout. Exit 0 only if every
mutation is killed.

No bytecode is ever written from a mutant (TOOL-A): pytest runs with PYTHONDONTWRITEBYTECODE=1. Otherwise a same-size
mutant restored within its own mtime second stays what `import` loads (the .pyc's mtime and size still match), so later
runs test the mutant while `git status` is clean.

Before applying a mutation the tool writes `<git-dir>/mutate-applied.json` (git dir from
`git rev-parse --git-dir`, so each worktree has its own) holding the file path, the sha256 of the
original bytes, and those bytes in base64. The sidecar is removed only after the original bytes
are written back. A kill between the two leaves it, and `--restore` puts the file back.

Usage: python tools/mutate_check.py <mutations.json>
       python tools/mutate_check.py --restore
       python tools/mutate_check.py --check-clean

TOOL-B, cosmic-ray mode: python tools/mutate_check.py --cosmic-ray <module-tests.json> [<dump.jsonl>|-]
re-derives each kill in a `cosmic-ray dump <session.sqlite>` transcript (a file, or `-`/omitted for
stdin) from a named test failing, the same rule as above. cosmic-ray 8.7.0's WorkResult carries no
exit code (cosmic_ray/testing.py:run_tests, read at 8.7.0): it returns TestOutcome.KILLED for *any*
non-zero test-command exit alike -- a real named failure, a collection error, any other non-zero exit
-- and KILLED with output=="timeout" for a hang. Its own summary does not separate these (TOOL-B).
`cosmic_ray.commands.dump` is not a module; `cli.py`'s `dump` command is the only source, one JSON
[WorkItem, WorkResult|null] pair per line. <module-tests.json> maps a module path (exact, or a
directory prefix covering every module under it, as "src/harness_bench/grade" covers
"grade/runner.py") to its named tests, e.g.
{"src/harness_bench/ledger.py": ["tests/test_ledger.py", "tests/test_verify.py"]}.
"""

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# a node id, with its parametrize case id whole: a case id may hold spaces ("[answer and timeout in one tick]")
FAILED = re.compile(r"^FAILED ([^\s\[]+(?:\[[^\]\n]*\])?)", re.MULTILINE)
SUMMARY = re.compile(r"\b\d+ (?:passed|failed|errors?|skipped|deselected|xfailed|xpassed|warnings?)\b|\bno tests ran\b")


def _matched_failure(output: str, named: list[str]) -> str | None:
    """The first `FAILED <node id>` line in output naming one of `named`, or None."""
    for f in FAILED.findall(output):
        for n in named:
            if f == n or f.startswith((n + "::", n + "[")):
                return f
    return None


def _ran_to_completion(output: str) -> bool:
    """True when `output` carries real pytest evidence -- a `FAILED <node id>` line or a summary
    line (`N passed`, `N failed`, `no tests ran`, ...) -- as opposed to a broken environment (the
    interpreter vanished, a launch failure) whose exit code and text carry no such evidence."""
    return bool(FAILED.search(output) or SUMMARY.search(output))


def verdict(returncode: int | None, output: str, named: list[str]) -> str:
    """killed | survived | error | timeout, from one pytest run of the named tests."""
    if returncode is None:
        return "timeout"
    if not _ran_to_completion(output):
        return "error"
    if returncode not in (0, 1):
        return "error"
    if returncode == 1 and _matched_failure(output, named) is not None:
        return "killed"
    return "survived"


def cosmic_ray_verdict(result: dict | None, named: list[str]) -> tuple[str, str | None]:
    """(verdict, matched named test) re-derived from one cosmic-ray WorkResult dict (`cli.py:dump`,
    cosmic-ray 8.7.0). cosmic-ray counts KILLED for any non-zero test-command exit and for a timeout
    alike; only a `FAILED <node id>` line naming one of `named` is evidence of a real kill.

    killed: a named test's own FAILED line is present. survived: pytest ran and failed (there is at
    least one FAILED line) but none names this mutation's tests -- the wrong test failed, or the
    mutant is equivalent. error: no test ran at all (a collection error, a launch failure, any other
    non-test-producing failure) or the worker itself did not exit normally. timeout: cosmic-ray's own
    "timeout" sentinel (a hang is not a kill). pending: dump's WorkResult was null (no result yet).
    """
    if result is None:
        return "pending", None
    if result.get("worker_outcome") != "normal" or result.get("test_outcome") == "incompetent":
        return "error", None
    output = result.get("output") or ""
    if output == "timeout":
        return "timeout", None
    if not _ran_to_completion(output):
        return "error", None
    if result.get("test_outcome") == "survived":
        return "survived", None
    if result.get("test_outcome") == "killed":
        match = _matched_failure(output, named)
        if match is not None:
            return "killed", match
        return ("survived", None) if FAILED.search(output) else ("error", None)
    return "error", None


def named_tests_for(module_paths: list[str], test_map: dict[str, list[str]]) -> list[str]:
    """The configured named tests for a cosmic-ray WorkItem's mutated module path(s).

    Matches by exact path, else by the longest `test_map` key that is a path-prefix (a directory
    entry, e.g. "src/harness_bench/grade", covers every module under it). Windows-style backslash
    separators (cli.py stringifies `module_path` with `Path.__str__`) are normalised first.
    """
    named: list[str] = []
    for raw in module_paths:
        path = raw.replace("\\", "/")
        best: str | None = None
        for key in test_map:
            k = key.replace("\\", "/").rstrip("/")
            if (path == k or path.startswith(k + "/")) and (best is None or len(k) > len(best)):
                best = k
        if best is not None:
            named.extend(t for t in test_map[best] if t not in named)
    return named


def derive_cosmic_ray(lines: Iterable[str], test_map: dict[str, list[str]]) -> tuple[list[dict], int]:
    """Re-derive a named-test verdict for every WorkItem in a `cosmic-ray dump` transcript.

    Returns (records, overstated): each record is {job_id, module_path, operator_name, verdict,
    cosmic_ray_outcome, named_test}; `overstated` counts WorkItems cosmic-ray itself called
    "killed" whose re-derived verdict is not "killed" -- the TOOL-B signature.
    """
    records = []
    overstated = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        work_item, result = json.loads(line)
        module_paths = [m["module_path"] for m in work_item["mutations"]]
        named = named_tests_for(module_paths, test_map)
        cr_outcome = result.get("test_outcome") if result is not None else None
        outcome, matched = cosmic_ray_verdict(result, named)
        if cr_outcome == "killed" and outcome != "killed":
            overstated += 1
        records.append({
            "job_id": work_item["job_id"],
            "module_path": ", ".join(module_paths),
            "operator_name": ", ".join(m["operator_name"] for m in work_item["mutations"]),
            "verdict": outcome,
            "cosmic_ray_outcome": cr_outcome,
            "named_test": matched,
        })
    return records, overstated


def _main_cosmic_ray(argv: list[str]) -> int:
    test_map = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    dump_arg = argv[1] if len(argv) > 1 else "-"
    text = sys.stdin.read() if dump_arg == "-" else Path(dump_arg).read_text(encoding="utf-8")
    records, overstated = derive_cosmic_ray(text.splitlines(), test_map)
    killed = sum(1 for r in records if r["verdict"] == "killed")
    for r in records:
        disagreement = "" if r["verdict"] == r["cosmic_ray_outcome"] else f"  (cosmic-ray said {r['cosmic_ray_outcome']})"
        named = f"  {r['named_test']}" if r["named_test"] else ""
        print(f"{r['verdict']:<8} {r['job_id']} {r['module_path']}{named}{disagreement}", flush=True)
    print(f"{killed} named kills of {len(records)}; {overstated} overstated "
          f"(cosmic-ray killed, not a named test failure)", flush=True)
    return 1 if overstated else 0


def _git_dir() -> Path | None:
    """Git dir of the checkout ROOT is in. None when this checkout is not a git worktree."""
    env = {k: v for k, v in os.environ.items() if k not in {"GIT_DIR", "GIT_WORK_TREE"}}
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, env=env,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def _sidecar_path() -> Path | None:
    git_dir = _git_dir()
    if git_dir is None:
        return None
    return git_dir / "mutate-applied.json"


def _read_sidecar() -> dict | None:
    path = _sidecar_path()
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_sidecar(rel: str, original: bytes) -> None:
    path = _sidecar_path()
    if path is None:
        return
    payload = {
        "file": rel,
        "sha256": hashlib.sha256(original).hexdigest(),
        "original_b64": base64.b64encode(original).decode("ascii"),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _remove_sidecar() -> None:
    path = _sidecar_path()
    if path is not None and path.is_file():
        path.unlink()


def apply_mutation(rel: str, original: bytes, mutated: bytes) -> None:
    """Record the original bytes, then write the mutant. A kill after this returns leaves both."""
    _write_sidecar(rel, original)
    (ROOT / rel).write_bytes(mutated)


def _restore_original(rel: str, original: bytes) -> None:
    """Write the original bytes back, and only then remove the sidecar."""
    (ROOT / rel).write_bytes(original)
    _remove_sidecar()


def _refuse_if_sidecar() -> int | None:
    record = _read_sidecar()
    if record is None:
        return None
    print(
        f"refusing to start: {record['file']} still has an applied mutation; "
        "run python tools/mutate_check.py --restore",
        flush=True,
    )
    return 2


def _cmd_restore() -> int:
    path = _sidecar_path()
    if path is None or not path.is_file():
        print("nothing to restore", flush=True)
        return 0
    record = json.loads(path.read_text(encoding="utf-8"))
    original = base64.b64decode(record["original_b64"])
    target = ROOT / record["file"]
    current = target.read_bytes() if target.is_file() else None
    if current != original:
        target.write_bytes(original)
        print(f"restored {record['file']}", flush=True)
    else:
        print(f"{record['file']} already matched the recorded original", flush=True)
    path.unlink()
    return 0


def _cmd_check_clean() -> int:
    record = _read_sidecar()
    if record is None:
        return 0
    print(record["file"], flush=True)
    return 1


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--restore":
        return _cmd_restore()
    if argv and argv[0] == "--check-clean":
        return _cmd_check_clean()
    if argv and argv[0] == "--cosmic-ray":
        return _main_cosmic_ray(argv[1:])
    refused = _refuse_if_sidecar()
    if refused is not None:
        return refused
    spec = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    survivors = 0
    for m in spec:
        path = ROOT / m["file"]
        original = path.read_bytes()
        text = original.decode("utf-8").replace("\r\n", "\n")
        if m["find"] not in text:
            print(f"SKIP     {m['name']}: text not found", flush=True)
            survivors += 1
            continue
        mutated = text.replace(m["find"], m["replace"], 1).encode("utf-8")
        try:
            apply_mutation(m["file"], original, mutated)
            try:
                # --color=no: FORCE_COLOR paints the FAILED line, and the kill regex then sees no result.
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "--color=no", "-rf", "-p", "no:cacheprovider", *m["tests"]],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    check=False, timeout=m.get("timeout", 180),
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                outcome = verdict(result.returncode, result.stdout + result.stderr, m["tests"])
            except subprocess.TimeoutExpired:
                outcome = "timeout"
            print(f"{outcome:<8} {m['name']}", flush=True)
            survivors += 0 if outcome == "killed" else 1
        finally:
            _restore_original(m["file"], original)
    print(f"{survivors} not killed" if survivors else "every mutation killed", flush=True)
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
