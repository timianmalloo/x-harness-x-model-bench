"""bench discriminate: run a task's reference, naive and defect variants as synthetic cells through the real engine,
archiver and grading pass, and write the create-once discrimination record (W1-E; ADR-0016 section 4; R-98; grade class).

The record body is a pure function of its key (task version, engine identity, platform): it holds no run id, grading id,
clock, duration or path, so a retry at an unchanged key writes equal bytes and is a confirmation. A trial that did not
run to the end, or that has any HB-RDY-011 item, writes nothing, so a transient fault can never leave a record that a
clean retry then contradicts. The link `runs/<run>/discrimination-link.json` is local and is written only after
`create_once` returned created or equal, never after HB-RDY-010, a failed trial or HB-RDY-011 (R-98 condition 1).
"""

import hashlib
import json
import secrets
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from harness_bench import (
    atomic,
    config,
    engine,
    ledger,
    oslock,
    plan,
    readiness,
    views,
    workspace,
)
from harness_bench.errors import BenchError
from harness_bench.grade import correctness, judge, runner
from harness_bench.readiness import (
    CORRECTNESS_SCORES,
    FLIPPED,
    ROLES,
    record_key,
    record_path,
)
from harness_bench.synthetic_agent import SYNTHETIC_VERSION

AGENT = Path(__file__).with_name("synthetic_agent.py")
RECORD_SCHEMA = "bench-discrimination/1"
LINK_SCHEMA = "bench-discrimination-link/1"
# The closed set of NA reasons a record may hold (R6-1, rev 6.3): grader constants with no measured value, path or pid in
# them. An unknown reason makes the trial HB-RDY-011, so no record carries text that could differ between honest trials.
NA_REASONS = frozenset({"not built", correctness.NO_PUBLIC_TESTS, correctness.NOT_D_TASK, correctness.NO_DIFFERENTIAL,
                        "no probe case declared", "did not build", "did not start"})
# A check or host fault: the trial is untrustworthy (HB-CHK-001..004) unless `expected` declares that very NA (EV-11).
UNTRUSTED_NA = ("invalid (check tampered)", "check exceeded its bound", "host suspended", "check output invalid")
UNDECLARED = "(differs)"  # what a record holds where the check's clause text is not the declared one


@dataclass(frozen=True)
class Result:
    outcome: str  # written | confirmed
    record_path: Path | None = None
    run_id: str | None = None
    notes: tuple[str, ...] = ()


class SyntheticLauncher:
    """The engine's Launcher for the synthetic harness: a stdlib ACP process; no login, no usage record.

    The agent's environment is the grader's allowlist plus exactly `HB_SYNTH_OVERLAY` and `TRACEPARENT` (D-E5): never
    `os.environ` and never a denylist, so a new credential name cannot reach it."""

    harness = "synthetic"
    credential_names: frozenset[str] = frozenset()
    credential_kind = "none (synthetic)"
    usage_source = "acp_turn"
    mode = None
    set_model = False
    shutdown_grace = 1.0

    def __init__(self, overlays: dict[str, Path]):
        self.overlays = overlays  # combo id -> the overlay folder that combo's cell applies

    def check_build(self) -> dict:
        return {"version": SYNTHETIC_VERSION}  # the identity manifest already hashes synthetic_agent.py (grade class)

    def seed(self, home: Path, cell: dict) -> None:
        home.mkdir(parents=True, exist_ok=True)

    def clean(self, home: Path) -> None:
        return None

    def argv_env(self, cell: dict, home: Path, traceparent: str):
        from harness_bench.grade._env import grading_env

        env = grading_env()
        env["HB_SYNTH_OVERLAY"] = str(self.overlays[cell["combo"]])
        env["TRACEPARENT"] = traceparent
        return [sys.executable, str(AGENT)], env

    def records(self, home: Path, session_id: str) -> list[Path]:
        return []

    def read(self, path: Path):
        raise NotImplementedError("the synthetic agent writes no native record")


def _first_diff(stored, new, path: str = "") -> tuple[str, object, object] | None:
    """The first differing JSON path of two parsed bodies, in sorted key order (PAT 9)."""
    if isinstance(stored, dict) and isinstance(new, dict):
        for key in sorted(stored.keys() | new.keys()):
            sub = f"{path}.{key}" if path else key
            if key not in stored or key not in new:
                return sub, stored.get(key, "<absent>"), new.get(key, "<absent>")
            found = _first_diff(stored[key], new[key], sub)
            if found:
                return found
        return None
    return None if stored == new else (path, stored, new)


def _overlays(task_dir: Path) -> dict[str, tuple[str, Path]]:
    """combo id -> (role, overlay folder) for the two roles every property task ships (W0 section 2)."""
    out = {}
    for role in ROLES:
        folder = task_dir / "oracle" / "solutions" / role
        if not folder.is_dir():
            raise BenchError("HB-RDY-005", f"{task_dir.name}: oracle/solutions/{role}/ is missing")
        out[f"synthetic-{role}"] = (role, folder)
    return out


def _variant_overlay(task_dir: Path, name: str, entry: dict, dest: Path) -> Path:
    """The reference overlay with the variant's edits applied, held under the run folder, never in the task folder. Every
    edit was checked by `readiness.variants` (path rule, `old` exactly once), so each applies once."""
    shutil.copytree(task_dir / "oracle" / "solutions" / "reference", dest)
    for edit in entry["edits"]:
        target = dest / edit["file"]
        target.write_bytes(target.read_bytes().replace(edit["old"].encode(), edit["new"].encode(), 1))
    return dest


def _matrix(run_id: str, task_id: str, combos: list[str]) -> dict:
    return {"schema": "bench-matrix/1", "run_id": run_id, "bom": {"subset": [task_id]}, "packs": ["off"], "repetitions": 1,
            "combos": [{"id": c, "harness": "synthetic", "model": "synthetic-1"} for c in combos]}


def _workspace_builder(task_dir: Path, sources: Path, upstream: Path):
    def build(cell: dict, cell_dir: Path) -> dict:
        source = workspace.task_source(task_dir, cell["task_version"], sources, upstream)
        workspace.cell_working_copy(source, cell_dir / "ws")
        return {"arm": "off", "pack_manifest": 0}

    return build


def _scores(run_dir: Path, grading_id: str, p: dict, combo_role: dict[str, str], keep: set[str]) -> tuple[dict, dict]:
    """(role -> metric -> value or {na: reason}, role -> the `property.json` pointer of its property_check_pass row)."""
    cell_role = {c["cell_id"]: combo_role[c["combo"]] for c in p["cells"]}
    scores: dict[str, dict] = {role: {} for role in combo_role.values()}
    pointers: dict[str, str] = {}
    for row in views.rows(run_dir, "scores"):
        if row["grading_id"] == grading_id and row["cell_id"] in cell_role:
            role = cell_role[row["cell_id"]]
            if row["metric_id"] in keep:
                scores[role][row["metric_id"]] = row["value"] if row["value"] is not None else {"na": row["reason"]}
            if row["metric_id"] == "property_check_pass" and row["evidence"]:
                pointers[role] = row["evidence"]
    return {role: dict(sorted(s.items())) for role, s in scores.items()}, pointers


def _untrustworthy(scores: dict[str, dict], expected: dict) -> list[str]:
    """HB-RDY-011 items from the scores alone: a check or host fault, or an NA reason outside the closed set."""
    items = []
    for role, row in scores.items():
        for metric, value in row.items():
            if not isinstance(value, dict):
                continue
            if (expected.get(role) or {}).get(metric) == value:
                continue  # an NA equal to the declared expected NA is the one exemption (EV-11)
            reason = value["na"]
            if reason.startswith(UNTRUSTED_NA):
                items.append(f"{role} {metric}: {reason}")
            elif reason not in NA_REASONS:
                items.append(f"{role} {metric}: NA reason outside the closed set ({reason})")
    return items


def _evidence_items(run_dir: Path, grading_id: str, labels: dict[str, str], pointers: dict[str, str], declared: dict) -> tuple[dict, list[str]]:
    """The HB-RDY-011 items a check-based trial can show, and the per-role evidence they were found in: unreadable
    evidence, a case `timeout` that nothing declares (R2-1), a hidden-test disagreement or not-comparable cell (R-93, R-96),
    a span with `unbiased_ok` false, and a reader that raised (its reason is the detail)."""
    items, found = [], {}
    for role, pointer in sorted(pointers.items()):
        try:
            found[role] = readiness.property_evidence(run_dir, pointer)
        except (OSError, ValueError, KeyError, IndexError) as exc:
            items.append(f"{role}: check evidence unreadable ({type(exc).__name__}: {exc})")
            continue
        allowed = set(declared.get(role.removeprefix("variant:"), {}).get("flips", ())) if role.startswith("variant:") else set()
        late = sorted(c for c, out in found[role]["cases"].items() if out == "timeout" and c not in allowed)
        if late:
            items.append(f"{role}: case {', '.join(late)} timed out (a timeout nothing declares is not measured content)")
    try:
        disagree, not_comparable = readiness.comparable_cells(run_dir, grading_id)
        unbiased = readiness.unbiased_failures(run_dir, grading_id)
    except BenchError as exc:
        return found, [*items, f"a reader could not run: {exc.message}"]
    for what, cells in (("hidden tests disagree with pass_at_1 in", disagree), ("not comparable (a side is NA) in", not_comparable),
                        ("a span with unbiased_ok false in", unbiased)):
        if cells:
            items.append(f"{what} {', '.join(labels.get(c, c) for c in cells)}")
    return found, items


def _variant_record(name: str, entry: dict, role: str, scores: dict, found: dict, check_based: bool, ref_scores: dict,
                    narrowed: set[str], scales: dict) -> tuple[dict, list[str]]:
    """One variant's record entry (observed flips, declared clause text where the check's clause is the declared one) and
    any HB-RDY-011 item (a declared clause the check's evidence cannot confirm fails closed)."""
    rec: dict = {"scores": scores[role]}
    items: list[str] = []
    if check_based:
        ev = found[role]
        rec["flips"] = sorted(c for c, out in ev["cases"].items() if out not in FLIPPED)
        rec["hidden_tests_pass"] = int(ev["hidden"] == 1)  # an int: the canonical form has no bool
        rec["deliverable"] = ev["deliverable"]
        observed = ev["clauses"]
        if entry["clauses"] and observed is None:
            items.append(f"variant {name}: clauses are declared but the check wrote no clauses.json (the pointer does not resolve)")
            observed = {}
        rec["clauses"] = {c: (entry["clauses"][c] if (observed or {}).get(c) == entry["clauses"][c] else UNDECLARED)
                          for c in rec["flips"] if c in entry["clauses"]}
    else:
        rec["flips"] = sorted(m for m in narrowed if readiness.normal(scores[role].get(m, {"na": "not recorded"}), scales.get(m))
                              != readiness.normal(ref_scores.get(m, {"na": "not recorded"}), scales.get(m)))
        rec["hidden_tests_pass"] = int(scores[role].get("pass_at_1") == 1)
        rec["clauses"] = {}
        if entry["clauses"]:
            items.append(f"variant {name}: a check-less variant declares clauses and this base records none (SR-E3 2)")
    return rec, items


def _sweep(task_id: str, folder: Path, lock: oslock.RunLock) -> list[Path]:
    """Sweep `bench/discrimination/<task>/` under this task's own discrimination lock and no other (RV-SEC: `atomic` does
    not know the pairing)."""
    if lock.path.name != f".discriminate-{task_id}.lock":
        raise ValueError(f"lock {lock.path.name} does not guard {folder}")
    return atomic.sweep_temps(folder, lock)


def _publish(task_id: str, path: Path, data: bytes, existed: bool, lock: oslock.RunLock) -> bool:
    """Write the record: True = created, False = equal bytes already there. HB-RDY-010 is raised before HB-LED-007 can be."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _sweep(task_id, path.parent, lock)
    if path.exists():
        if not existed:
            raise BenchError("HB-RDY-011", f"a record appeared at {path.name} during the trial; left for the operator, nothing written")
        stored = path.read_bytes()
        if stored != data:
            diff = _first_diff(json.loads(stored), json.loads(data))
            where, was, now = diff if diff else ("<bytes>", "?", "?")
            raise BenchError("HB-RDY-010", f"re-run disagrees with the stored record {path.name} at {where}: stored {was!r}, new {now!r}")
    return atomic.create_once(path, data)


def run(root: Path, task_id: str, *, runs: Path, cells_root: Path, upstream_root: Path | None = None) -> Result:
    """One discrimination trial of `task_id`. Takes the task's lock before planning (held: HB-RUN-005), runs the real
    engine and grading pass, and writes (or confirms) the record. Raises BenchError for every outcome that is not a
    record: HB-RDY-005 contract, HB-RDY-011 untrustworthy or incomplete, HB-RDY-010 determinism defect."""
    if task_id not in {p.name for p in (root / "tasks").iterdir() if p.is_dir()}:
        raise BenchError("HB-USR-002", f"no task folder {task_id!r} under tasks/")
    runs.mkdir(parents=True, exist_ok=True)
    with oslock.RunLock.acquire(runs / f".discriminate-{task_id}.lock", "HB-RUN-005") as lock:
        return _trial(root, task_id, runs, cells_root, upstream_root or root / ".tools" / "upstream", lock)


def _trial(root: Path, task_id: str, runs: Path, cells_root: Path, upstream: Path, lock: oslock.RunLock) -> Result:
    task_dir = root / "tasks" / task_id
    task = config.load_yaml(task_dir / "task.yaml")
    contract = readiness.contract_failures(root, task_id)
    if contract:
        raise BenchError("HB-RDY-005", "; ".join(f"{f.item}: {f.detail}" for f in contract))
    declared = readiness.variants(root, task_id)
    tv, ih = record_key(root, task_id)
    path = record_path(root, task_id)
    existed = path.exists()
    overlays = _overlays(task_dir)
    run_id = f"disc-{task_id.lower()}-{tv[:8]}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{secrets.token_hex(2)}"
    run_dir = runs / run_id
    for name, entry in declared.items():
        overlays[f"synthetic-v-{name}"] = (f"variant:{name}", _variant_overlay(task_dir, name, entry, run_dir / "variants" / name))
    combo_role = {combo: role for combo, (role, _folder) in overlays.items()}
    bom = config.load_yaml(root / "bench" / "bom.yaml")
    p = plan.build_plan(root, _matrix(run_id, task_id, list(overlays)), bom, run_id, {"synthetic": {"version": SYNTHETIC_VERSION}},
                        parallelism=1, kind="discrimination")
    plan.confirm(run_dir, p)
    cells_root.mkdir(parents=True, exist_ok=True)
    workspace.check_cells_root(cells_root)
    launcher = SyntheticLauncher({combo: folder for combo, (_role, folder) in overlays.items()})
    handler = engine.configure_logging(run_dir, p["trace_id"])
    try:
        cfg = engine.EngineConfig(
            run_dir=run_dir, cells_root=cells_root, launchers={"synthetic": launcher},
            build_workspace=_workspace_builder(task_dir, cells_root / ".sources", upstream),
            grade=lambda d: runner.run_pass(d, root, judge.IN_RUN, cells_root=cells_root).summary())
        summary = engine.Engine(p, cfg).run()
    finally:
        engine.log.removeHandler(handler)
        handler.close()
    bad = [f"{c['label']} ({summary.outcomes.get(c['cell_id'], {}).get('outcome')}, "
           f"{summary.outcomes.get(c['cell_id'], {}).get('cause')})" for c in p["cells"]
           if summary.outcomes.get(c["cell_id"], {}).get("outcome") != "completed"]
    if summary.exit_code != 0 or bad:
        raise BenchError("HB-RDY-011", f"trial incomplete, nothing written: {', '.join(bad) or 'the run stopped'}")
    passes = views.completed_passes(run_dir)
    if len(passes) != 1:
        raise BenchError("HB-RDY-011", f"the grading pass did not complete exactly once ({len(passes)}), nothing written")
    (grading_id,) = passes
    narrowed = set(readiness.recorded_metrics(root, task))
    scores, pointers = _scores(run_dir, grading_id, p, combo_role, narrowed | set(CORRECTNESS_SCORES))
    expected = task.get("expected") or {}
    items = _untrustworthy(scores, expected)
    check_based = readiness.is_check_based(task)
    found: dict = {}
    if check_based:
        labels = {c["cell_id"]: c["label"] for c in p["cells"]}
        found, more = _evidence_items(run_dir, grading_id, labels, pointers, declared)
        items += more
        if not more:
            items += [f"{r}: no check evidence found for the cell" for r in sorted(set(combo_role.values()) - set(found))]
    body: dict = {"schema": RECORD_SCHEMA, "task": task_id, "task_version": tv, "identity_hash": ih, "platform": sys.platform,
                  "scores": {role: scores[role] for role in ROLES}, "expected": expected}
    if check_based and not items:
        body["probe"] = {role: {"deliverable": found[role]["deliverable"], "cases": dict(sorted(found[role]["cases"].items())),
                                "hosts_ready": found[role]["hosts_ready"]} for role in ROLES}
    if declared and not items:
        scales = readiness.scales(root)
        body["variants"] = {}
        for name, entry in declared.items():
            rec, more = _variant_record(name, entry, f"variant:{name}", scores, found, check_based, scores["reference"], narrowed, scales)
            body["variants"][name] = rec
            items += more
    if items:
        raise BenchError("HB-RDY-011", f"trial untrustworthy, nothing written: {'; '.join(items)}")
    body["readiness_failures"] = sorted(f"{f.code}: {f.item}" for f in readiness.body_failures(root, task_id, body))
    data = ledger.canonical(body)
    created = _publish(task_id, path, data, existed, lock)
    link = ledger.stamp({"schema": LINK_SCHEMA, "record_stem": path.stem, "record_sha256": hashlib.sha256(data).hexdigest(),
                         "run_id": run_id, "grading_id": grading_id})
    atomic.create_once(run_dir / "discrimination-link.json", ledger.canonical(link))
    return Result("written" if created else "confirmed", path, run_id)
