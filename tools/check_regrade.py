"""The wave-3 byte-identity gate: the smoke archive re-grades byte-identically (design docs/design/phase3-graders.md,
"The byte-identity gate"; R-59 c6, DR-6; CORE s2). The Leader runs it on each gate run after the 0.4 freeze.

Per run R: E03_before = sha256(export(load(R, "0.3"))); pass A; EA = sha256(export(load(R, "0.4"))); pass B; EB; E03_after.
It passes only when every criterion holds:
1. both passes are real and distinct: each completed, each is the current `version` pass right after it ran, A != B
   (a dead pass B would otherwise export pass A again);
2. EA == EB;
3. E03_before == E03_after == the committed baseline (bench/regrade-baseline-0.3.yaml); a run with no 0.3 pass is
   recorded as `no 0.3 pass` and must have none (`load(R, "0.3").grading_id is None`);
4. both passes carry the frozen `catalog_hash` (bench/catalog-freeze.yaml; P1);
5. non-vacuity: pass A's `pass_at_1` and `partial_credit` equal the 0.3 values (or, with no 0.3 pass, the expected
   values), each metric's non-NA cell count equals tests/fixtures/gate/expected-counts.yaml, and no reason starts with
   `HB-GRD-` or `infrastructure failure`;
6. judge calls: never claimed. With no judged cell the gate notes `judge half not exercised: not proven`; with one, the
   zero-call proof needs the gateway's per-call record for pass B (W3-GW-D, S-5), so it is noted `not proven`;
7. `bench verify R` has no error (a warning, e.g. `anchor: not recorded`, is noted).
Preconditions checked by `main`: P2 the price list equals the plan's; P3 `bench validate` is green; P4 no engine holds R.

Usage: python tools/check_regrade.py <run_dir>... [--root <bench root>] [--version 0.4]
Exit 0 only if every run passes. Pass A and pass B are real grading passes written into each run's ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from harness_bench import config, ledger, oslock, views
from harness_bench.grade import runner
from harness_bench.plan import file_hash, load_confirmed

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "bench/regrade-baseline-0.3.yaml"
FREEZE = "bench/catalog-freeze.yaml"
EXPECTED = "tests/fixtures/gate/expected-counts.yaml"
CORRECTNESS = ("pass_at_1", "partial_credit")  # DR-G4 changes no current value (G16), so pass A must equal 0.3 here
BAD_REASON = ("HB-GRD-", "infrastructure failure")


@dataclass
class Report:
    run: str
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def _sha(view: views.RunView) -> str:
    return hashlib.sha256(views.export(view)).hexdigest()


def _started(run_dir: Path, grading_id: str | None) -> dict:
    if grading_id is None:
        return {}
    path = run_dir / "events" / f"{grading_id}.jsonl"
    rows = ledger.read_segment(path) if path.is_file() else []
    return next((r for r in rows if r["kind"] == "grading.started"), {})


def _pass(label: str, grade: Callable[[Path], str], run_dir: Path, version: str, report: Report) -> tuple[str | None, views.RunView]:
    """Run one pass; criterion 1 for it (completed, and the current `version` pass right after it ran)."""
    try:
        gid: str | None = grade(run_dir)
    except Exception as exc:  # noqa: BLE001 - a killed or failed pass is a gate finding, never a crash of the checker
        gid, why = None, type(exc).__name__
    else:
        why = "no grading.completed"
    view = views.load(run_dir, version)
    if gid is None or gid not in views.completed_passes(run_dir):
        report.failures.append(f"criterion 1: pass {label} did not complete ({why})")
    elif view.grading_id != gid:
        report.failures.append(f"criterion 1: pass {label} is not the current {version} pass")
    return gid, view


def _values(view: views.RunView, metrics) -> dict[tuple[str, str], tuple]:
    return {(c.cell_id, m): (c.scores[m].value, c.scores[m].reason) for c in view.cells for m in metrics if m in c.scores}


def gate(run_dir: Path, grade: Callable[[Path], str], *, baseline: dict, frozen_hash: str | None, expected: dict | None,
         version: str = "0.4", judged: bool = False) -> Report:
    """Steps 1-6 and criteria 1-7 for one gate run. `grade` runs one real pass and returns its grading_id."""
    report = Report(run_dir.name)
    v03 = views.load(run_dir, "0.3")
    e03_before = _sha(v03)
    a_id, va = _pass("A", grade, run_dir, version, report)
    b_id, vb = _pass("B", grade, run_dir, version, report)
    if a_id is not None and a_id == b_id:
        report.failures.append("criterion 1: passes A and B are the same pass")
    if _sha(va) != _sha(vb):  # 2
        report.failures.append("criterion 2: pass B's export differs from pass A's")
    v03_after = views.load(run_dir, "0.3")  # 3
    e03_after = _sha(v03_after)
    base = (baseline.get("runs") or {}).get(run_dir.name)
    if base is not None:
        if not e03_before == e03_after == base["export_sha256"]:
            report.failures.append(f"criterion 3: the 0.3 export {e03_before} before, {e03_after} after, "
                                   f"baseline {base['export_sha256']}")
    elif v03.grading_id is None and v03_after.grading_id is None:
        report.notes.append("no 0.3 pass")
    else:
        report.failures.append(f"criterion 3: a 0.3 pass with no committed baseline in {BASELINE} (P5)")
    for label, gid in (("A", a_id), ("B", b_id)):  # 4
        got = _started(run_dir, gid).get("catalog_hash", "not recorded")
        if frozen_hash is None or got != frozen_hash:
            report.failures.append(f"criterion 4: pass {label} catalog_hash {got} != frozen {frozen_hash or 'none (P1)'}")
    _non_vacuity(va, v03, expected, report)  # 5
    report.notes.append("judge calls in pass B: not proven (the gateway per-call record is W3-GW-D's, S-5)" if judged
                        else "judge half not exercised: not proven")  # 6
    for f in views.verify(run_dir):  # 7
        if f.level == "error":
            report.failures.append(f"criterion 7: {f.code} {f.message}")
        else:
            report.notes.append(f"verify warning: {f.code} {f.message}")
    return report


def _non_vacuity(va: views.RunView, v03: views.RunView, expected: dict | None, report: Report) -> None:
    if expected is None:
        report.failures.append(f"criterion 5: no expected counts for this run in {EXPECTED}")
        return
    want = _values(v03, CORRECTNESS) if v03.grading_id is not None else {
        (cid, m): (v, None) for cid, row in (expected.get("values") or {}).items() for m, v in row.items()}
    got = _values(va, CORRECTNESS)
    if not want:
        report.failures.append("criterion 5: no 0.3 values and no expected values to compare pass A's correctness with")
    for key in sorted(want.keys() | got.keys()):
        if want.get(key) != got.get(key):
            report.failures.append(f"criterion 5: {key[1]} of cell {key[0]} is {got.get(key)}, expected {want.get(key)}")
    counts = expected.get("counts") or {}
    metrics = sorted({m for c in va.cells for m in c.scores} | set(counts))
    for m in metrics:
        n = sum(1 for c in va.cells if m in c.scores and c.scores[m].value is not None)
        if counts.get(m) is None:
            report.failures.append(f"criterion 5: {m} has no expected non-NA count ({n} measured)")
        elif n != counts[m]:
            report.failures.append(f"criterion 5: {m} non-NA count {n} != expected {counts[m]}")
    bad = sorted((c.cell_id, m) for c in va.cells for m, s in c.scores.items() if (s.reason or "").startswith(BAD_REASON))
    if bad:
        report.failures.append(f"criterion 5: HB-GRD or infrastructure reasons in pass A: {bad}")


def preconditions(run_dir: Path, root: Path) -> list[str]:
    """P2-P4 (P1 is criterion 4; P5 is criterion 3)."""
    out = []
    if file_hash(root / "bench" / "prices.yaml") != load_confirmed(run_dir).get("price_list_hash"):
        out.append("P2: bench/prices.yaml differs from the plan's price_list_hash")
    if config.validate_repo(root):
        out.append("P3: bench validate is not green")
    if oslock.is_held(run_dir / ".lock"):
        out.append("P4: an engine holds the run (running)")
    return out


def _judged(run_dir: Path, root: Path) -> bool:
    plan = load_confirmed(run_dir)
    tasks = plan.get("tasks") or {}
    for task in {c["task"] for c in plan["cells"]}:
        graders = (tasks.get(task) or {}).get("graders")
        if graders is None:
            graders = config.load_yaml(root / "tasks" / task / "task.yaml").get("graders") or []
        if "judge" in graders:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--version", default="0.4")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    baseline = config.load_yaml(root / BASELINE)
    freeze = config.load_yaml(root / FREEZE) if (root / FREEZE).is_file() else {}
    frozen_hash = ((freeze.get("versions") or {}).get(args.version) or {}).get("catalog_hash")
    expected = config.load_yaml(root / EXPECTED).get("runs") or {}
    ok = True
    for run_dir in args.runs:
        run_dir = run_dir.resolve()
        pre = preconditions(run_dir, root)
        report = Report(run_dir.name, failures=pre) if pre else gate(
            run_dir, lambda d: runner.run_pass(d, root).grading_id, baseline=baseline, frozen_hash=frozen_hash,
            expected=expected.get(run_dir.name), version=args.version, judged=_judged(run_dir, root))
        print(f"{'PASS' if report.ok else 'FAIL'} {report.run}")
        for line in report.failures:
            print(f"  x {line}")
        for line in report.notes:
            print(f"  - {line}")
        ok = ok and report.ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
