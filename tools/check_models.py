"""Model-check the TLA+ models of the benchmark itself (spec US-44), in both directions.

1. The real design (BUG = "none") passes: every safety invariant at small bounds and at the US-44
   bounds (3 cells, parallelism 2, 1 crash), grading mutual exclusion at 2 passes, liveness at 1 cell;
   and a reachability witness shows every cell can finish.
2. Every seeded-bug variant is rejected, and by the invariant or property it targets. A variant that
   passes means the model cannot see that defect: the check fails.

TLC comes from the pinned tla2tools.jar, downloaded once into .tools/ and verified by sha256.
Needs Java 11+ on PATH.

Usage: python tools/check_models.py [--quick | --deep]
  --quick  skips the US-44-bounds safety run (small bounds only)
  --deep   adds safety at 2 crashes (on demand)
"""

import hashlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
JAR = ROOT / ".tools" / "tla2tools.jar"
TLA_VERSION = "v1.7.4"
JAR_URL = f"https://github.com/tlaplus/tlaplus/releases/download/{TLA_VERSION}/tla2tools.jar"
JAR_SHA256 = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"
TIMEOUT = 3600

MODEL = "run_lifecycle"
# Seeded bug -> the invariant ("inv") or temporal property ("prop") that must reject it.
VARIANTS = {
    "relaunch_prompted": ("inv", "AtMostOnePrompt"),
    "send_before_persist": ("inv", "AtMostOnePrompt"),
    "launch_after_outcome": ("inv", "NoPromptAfterOutcome"),
    "archive_live": ("inv", "NoArchiveWhileLive"),
    "delete_before_archive": ("inv", "NothingDeletedUnarchived"),
    "grade_twice": ("inv", "GradedOncePerPass"),
    "grade_unarchived": ("inv", "GradedOnlyWhenArchived"),
    "no_lock": ("inv", "AtMostOneActivePass"),
    "apply_twice": ("inv", "ControlAppliedOnce"),
    "launch_after_stop": ("inv", "NoLaunchAfterStop"),
    "exceed_parallelism": ("inv", "ParallelismBound"),
    "reconcile_no_wait": ("inv", "NoLaunchBesideOrphan"),
    "relaunch_stopped": ("inv", "StoppedNeverRelaunched"),
    "double_resolution": ("inv", "DecisionResolvedOnce"),
    "launch_while_open": ("inv", "NoLaunchWhileDecisionOpen"),
    "record_while_running": ("inv", "NoOutcomeWhileRunning"),
    "no_timeout": ("prop", "DecisionEventuallyResolved"),
    "stop_ignored": ("prop", "StopReachesTerminal"),
    "record_without_kill": ("prop", "EndedCellsGetArchived"),
    "no_budget_kill": ("prop", "PromptedCellsEnd"),
    "grade_skipped": ("prop", "ArchivedCellsGetGraded"),
}
# The real design and the variants run at small bounds (2 cells, parallelism 1, 1 crash, 1 pass, the
# engine and `bench grade` both grading); two-pass variants use the grading config. Every seeded
# defect is reachable there.
SMALL = {"Cells = {c1, c2, c3}": "Cells = {c1, c2}", "Parallelism = 2": "Parallelism = 1",
         'Graders = {"engine"}': 'Graders = {"engine", "bench"}'}
DEEP = {"MaxCrashes = 1": "MaxCrashes = 2"}
TWO_PASS = {"no_lock"}             # variants that need two grading passes use the grading config
# Variants whose defect needs a free slot beside an orphan run at parallelism 2.
WIDER = {"reconcile_no_wait": {"Parallelism = 1": "Parallelism = 2"}}
WITNESS = "NotAllCellsFinished"   # must be violated by the real design: the run can finish


def ensure_jar() -> Path:
    if not JAR.exists():
        JAR.parent.mkdir(exist_ok=True)
        with urllib.request.urlopen(JAR_URL, timeout=120) as response:
            JAR.write_bytes(response.read())
    digest = hashlib.sha256(JAR.read_bytes()).hexdigest()
    if digest != JAR_SHA256:
        JAR.unlink()
        raise SystemExit(f"tla2tools.jar sha256 mismatch: {digest} (expected {JAR_SHA256}); deleted")
    return JAR


def tlc(cfg_text: str, label: str) -> tuple[int, str, float]:
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / f"{label}.cfg"
        cfg.write_text(cfg_text, encoding="utf-8")
        started = time.monotonic()
        result = subprocess.run(
            ["java", "-XX:+UseParallelGC", "-XX:MaxRAMPercentage=75", "-cp", str(JAR), "tlc2.TLC",
             "-workers", "auto",
             "-metadir", str(Path(tmp) / "meta"), "-config", str(cfg), f"{MODEL}.tla"],
            cwd=MODELS, capture_output=True, text=True, timeout=TIMEOUT,
            check=False)  # TLC exits non-zero on the violations the variants expect
        return result.returncode, result.stdout + result.stderr, time.monotonic() - started


def states(output: str) -> str:
    found = re.findall(r"([\d,]+) distinct states found", output)
    return found[-1] if found else "?"


def substitute(cfg_text: str, replacements: dict[str, str]) -> str:
    """Replace config lines; a line that is not there is an error, never a silent no-op."""
    for old, new in replacements.items():
        if old not in cfg_text:
            raise SystemExit(f"config drift: {old!r} not found")
        cfg_text = cfg_text.replace(old, new)
    return cfg_text


def with_bug(cfg_text: str, bug: str) -> str:
    return substitute(cfg_text, {'BUG = "none"': f'BUG = "{bug}"'})


def only_property(cfg_text: str, name: str) -> str:
    """A liveness variant is checked against its target property alone, so the right one rejects it."""
    head, _, tail = cfg_text.partition("PROPERTIES")
    rest = tail.split("CHECK_DEADLOCK", 1)[1]
    return f"{head}PROPERTIES\n    {name}\n\nCHECK_DEADLOCK{rest}"


def only_invariant(cfg_text: str, name: str) -> str:
    """A safety variant is checked against its target invariant alone: TLC stops at the first
    violation, so another invariant could otherwise pre-empt the target and hide that it is vacuous."""
    head = cfg_text.split("INVARIANTS")[0]
    return f"{head}INVARIANTS\n    {name}\n\nCHECK_DEADLOCK FALSE\n"


def main(argv: list[str]) -> int:
    ensure_jar()
    safety = (MODELS / f"{MODEL}.safety.cfg").read_text(encoding="utf-8")
    liveness = (MODELS / f"{MODEL}.liveness.cfg").read_text(encoding="utf-8")
    small = substitute(safety, SMALL)
    failures = []

    grading = (MODELS / f"{MODEL}.grading.cfg").read_text(encoding="utf-8")
    runs = [("liveness", liveness), ("grading", grading), ("safety-small", small)]
    if "--quick" not in argv:
        runs.append(("safety", safety))
    if "--deep" in argv:
        runs.append(("safety-2-crashes", substitute(safety, DEEP)))
    for label, cfg in runs:
        code, out, secs = tlc(cfg, label)
        clean = code == 0 and "violated" not in out and "Error:" not in out
        print(f"{'ok  ' if clean else 'FAIL'} {label:<24} real design, {states(out)} states, {secs:.0f}s", flush=True)
        if not clean:
            failures.append(label)
            print(out[-3000:], flush=True)

    code, out, secs = tlc(only_invariant(small, WITNESS), "witness")
    reached = f"Invariant {WITNESS} is violated" in out
    print(f"{'ok  ' if reached else 'FAIL'} {'witness':<24} every cell can finish graded and deleted ({secs:.0f}s)", flush=True)
    if not reached:
        failures.append("witness")

    for bug, (kind, target) in VARIANTS.items():
        if kind == "prop":
            base = only_property(liveness, target)
        else:
            base = only_invariant(grading if bug in TWO_PASS else small, target)
        cfg = with_bug(substitute(base, WIDER.get(bug, {})), bug)
        code, out, secs = tlc(cfg, bug)
        expected = (f"Invariant {target} is violated" if kind == "inv"
                    else "Temporal properties were violated")
        caught = expected in out
        print(f"{'ok  ' if caught else 'FAIL'} {bug:<24} rejected by {target}" if caught
              else f"FAIL {bug:<24} NOT rejected by {target} ({states(out)} states, {secs:.0f}s)",
              flush=True)
        if not caught:
            failures.append(bug)
    print(f"{len(failures)} failure(s)" if failures else "all model checks passed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
