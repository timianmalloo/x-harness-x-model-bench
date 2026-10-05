"""Task readiness: what `bench validate` says about a property task (W1-E section 8; grade class).

A property task is `ready` only because a discrimination record, made by the real engine and grader, shows its hidden
check discriminates. This module recomputes every verdict from the record and the current task files; it trusts nothing
the record says about itself (not even `readiness_failures`).

The readers `hidden_test_disagreements`, `comparable_cells` and `unbiased_failures` return `list[str]` or raise
`BenchError("HB-USR-002", <reason>)`; `discriminate` converts a raise into an HB-RDY-011 item whose detail is the reason.
They never return a bare None.
"""

import ast
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from harness_bench import atomic, config, identity, plan, views
from harness_bench.errors import BenchError
from harness_bench.grade import property as prop
from harness_bench.grade import runner
from harness_bench.synthetic_agent import OverlayError, safe_relpath

ROLES = ("reference", "naive")
CORRECTNESS_SCORES = ("pass_at_1", "partial_credit")  # recorded in `scores`, no expected value (R-90 condition 1)
FLIPPED = ("blocked", "passed")  # a case outcome outside this pair is a flip (W1-E section 7)
MAX_VARIANTS_BYTES = 64 * 1024
MAX_CLAUSE_CHARS = 200
VARIANT_NAME = re.compile(r"[a-z0-9]{1,16}")
OVERLAY_COMPONENT = re.compile(r"[A-Za-z0-9._-]+")
_NAME_LEN = 16
_PROPERTY_PASS = "property_check_pass"


@dataclass(frozen=True)
class Failure:
    code: str  # "HB-RDY-003"
    item: str  # "exploit_probes_blocked"
    detail: str  # "reference expected 1.0000, observed 0.0000"


def record_key(root: Path, task_id: str) -> tuple[str, str]:
    """(task version hash, engine identity hash) of the key a record of `task_id` has today. The identity is the
    manifest of this one task with no `builds/*` key (W0 section 6)."""
    tv = plan.task_version_hash(root / "tasks" / task_id)
    return tv, identity.identity_hash(identity.manifest(root, [task_id], builds=None))


def record_dir(root: Path, task_id: str) -> Path:
    return root / "bench" / "discrimination" / task_id


def record_path(root: Path, task_id: str) -> Path:
    """`bench/discrimination/<task>/<tv16>-<id16>-<platform>.json` for the current key."""
    tv, ih = record_key(root, task_id)
    return record_dir(root, task_id) / f"{tv[:_NAME_LEN]}-{ih[:_NAME_LEN]}-{sys.platform}.json"


def recorded_metrics(root: Path, task: Mapping) -> dict[str, dict]:
    """Catalog entries of the property grader's narrowed set for this task (R-90 condition 1), in catalog order."""
    catalog = config.load_yaml(root / "bench" / "metrics.yaml")
    return runner.applicable(catalog, list(task["graders"]), task["property"]["name"]).get("property", {})


def scales(root: Path) -> dict[str, int]:
    return runner._scales(config.load_yaml(root / "bench" / "metrics.yaml"))


def is_check_based(task: Mapping) -> bool:
    return task["property"]["name"] in config.CHECK_PROPERTIES


def normal(value, scale: int | None):
    """A score or expected value through the one normaliser: `("na", reason)` or `grade.property.at_scale`'s result.
    ValueError names what is wrong."""
    if isinstance(value, Mapping):
        if set(value) != {"na"} or not isinstance(value["na"], str):
            raise ValueError(f"{value!r} is not {{na: <reason>}}")
        return ("na", value["na"])
    return prop.at_scale(value, scale)


def show(value) -> str:
    return f"NA ({value['na']})" if isinstance(value, Mapping) and "na" in value else str(value)


def score_failures(root: Path, task_id: str, body: Mapping) -> list[Failure]:
    """HB-RDY-003: every metric of the narrowed set, per role, equals the task's declared `expected` by exact equality
    after both sides pass through `normal`. Pure in the record body and the current files."""
    task = config.load_yaml(root / "tasks" / task_id / "task.yaml")
    table, out = scales(root), []
    for role in ROLES:
        declared = (task.get("expected") or {}).get(role) or {}
        for metric in recorded_metrics(root, task):
            if metric not in declared:
                continue  # a missing expected is HB-RDY-005 (contract), not a record defect
            observed = (body.get("scores") or {}).get(role, {}).get(metric, {"na": "not recorded"})
            try:
                ok = normal(observed, table.get(metric)) == normal(declared[metric], table.get(metric))
                why = ""
            except ValueError as exc:
                ok, why = False, f" ({exc})"
            if not ok:
                out.append(Failure("HB-RDY-003", metric, f"{role} expected {show(declared[metric])}, observed {show(observed)}{why}"))
    return out


def declared_cases(root: Path, task_id: str) -> list[str]:
    spec = config.load_yaml(root / "tasks" / task_id / "oracle" / "check" / "cases.yaml")
    return [str(c["id"]) for c in spec.get("cases") or []]


def host_failures(root: Path, task_id: str, task: Mapping, body: Mapping) -> list[Failure]:
    """R-HOST (O1), only for a check-based property: the digest shows the real probe host ran every declared case, for
    every role. A check-less property has no host, so a `probe` in its record is itself a failure."""
    probe = body.get("probe")
    if not is_check_based(task):
        return [Failure("HB-RDY-001", task_id, "probe on a check-less task: it has no real host, so its record carries no probe")] \
            if probe is not None else []
    if not isinstance(probe, Mapping):
        return [Failure("HB-RDY-001", task_id, "record lacks real-host probe evidence")]
    cases, out = declared_cases(root, task_id), []
    for role in ROLES:
        digest = probe.get(role)
        if not isinstance(digest, Mapping):
            out.append(Failure("HB-RDY-001", task_id, f"probe evidence of the {role} role is missing"))
        elif (digest.get("deliverable") != "ran" or sorted(digest.get("cases") or {}) != sorted(cases)
              or digest.get("hosts_ready") != len(cases)):
            out.append(Failure("HB-RDY-001", task_id, f"probe of the {role} role does not show a real-host run of every case "
                                                      f"(deliverable {digest.get('deliverable')!r}, hosts_ready {digest.get('hosts_ready')!r}, "
                                                      f"{len(digest.get('cases') or {})} of {len(cases)} cases)"))
    return out


def variant_failures(declared: Mapping[str, dict], body: Mapping) -> list[Failure]:
    """The variant compare (O2): assertions (1) hidden tests pass, (2) the deliverable ran (check-based), (3) the flipped
    set equals the declared one, (4) the deciding clauses equal the declared ones. One failure per variant. A declared
    variant absent from the record is HB-RDY-001."""
    recorded, out = body.get("variants") or {}, []
    for name, entry in declared.items():
        got = recorded.get(name)
        if not isinstance(got, Mapping):
            out.append(Failure("HB-RDY-001", name, "declared variant is absent from the record"))
            continue
        why = []
        if got.get("hidden_tests_pass") != 1:
            why.append("hidden tests do not pass (1)")
        if "deliverable" in got and got["deliverable"] != "ran":
            why.append(f"deliverable {got['deliverable']!r}, not 'ran' (2)")
        if sorted(got.get("flips") or []) != sorted(entry["flips"]):
            why.append(f"flips observed {sorted(got.get('flips') or [])}, declared {sorted(entry['flips'])} (3)")
        if (got.get("clauses") or {}) != entry["clauses"]:
            why.append(f"clauses observed {got.get('clauses') or {}}, declared {entry['clauses']} (4)")
        if why:
            out.append(Failure("HB-RDY-003", name, "; ".join(why)))
    return out


def body_failures(root: Path, task_id: str, body: Mapping) -> list[Failure]:
    """Every record item recomputed from the body and the current files (HB-RDY-001 host rule, 003 scores, 003 variants)."""
    task = config.load_yaml(root / "tasks" / task_id / "task.yaml")
    out = score_failures(root, task_id, body) + host_failures(root, task_id, task, body)
    try:
        declared = variants(root, task_id)
    except BenchError as exc:
        return [*out, Failure("HB-RDY-005", "variants.py", exc.message)]
    return out + variant_failures(declared, body)


def _read_record(path: Path) -> dict | None:
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _name_parts(name: str) -> tuple[str, str, str] | None:
    stem = name.removesuffix(".json")
    if stem == name or len(stem) < 2 * _NAME_LEN + 3 or stem[_NAME_LEN] != "-" or stem[2 * _NAME_LEN + 1] != "-":
        return None
    return stem[:_NAME_LEN], stem[_NAME_LEN + 1:2 * _NAME_LEN + 1], stem[2 * _NAME_LEN + 2:]


def contract_failures(root: Path, task_id: str) -> list[Failure]:
    """HB-RDY-005..008 for one task: what needs no run."""
    return []


def record_failures(root: Path, task_id: str, *, baseline: Mapping | None = None) -> list[Failure]:
    """HB-RDY-001..004, 010, 011 for one task: what the discrimination record must show. With a campaign `baseline`
    manifest the identity compared is `identity_hash(identity.for_task(baseline, task))` (W0 section 6)."""
    tv, ih = record_key(root, task_id)
    if baseline is not None:
        ih = identity.identity_hash(identity.for_task(dict(baseline), task_id))
    folder = record_dir(root, task_id)
    names = sorted(p.name for p in folder.glob("*.json") if not atomic.is_temp_name(p.name)) if folder.is_dir() else []
    here = [n for n in names if (parts := _name_parts(n)) and parts[0] == tv[:_NAME_LEN] and parts[2] == sys.platform]
    if not here:
        present = ", ".join(names) or "none"
        return [Failure("HB-RDY-001", task_id, f"no discrimination record for task version {tv[:_NAME_LEN]} on {sys.platform}; present: {present}")]
    match = [n for n in here if _name_parts(n)[1] == ih[:_NAME_LEN]]  # type: ignore[index]
    if not match:
        return [Failure("HB-RDY-002", task_id, f"record identity {_name_parts(here[0])[1]} differs from the current {ih[:_NAME_LEN]}")]  # type: ignore[index]
    body = _read_record(folder / match[0])
    p_tv, p_ih, p_platform = _name_parts(match[0])  # type: ignore[misc]
    if (body is None or body.get("task") != task_id or body.get("platform") != p_platform
            or str(body.get("task_version", ""))[:_NAME_LEN] != p_tv or str(body.get("identity_hash", ""))[:_NAME_LEN] != p_ih):
        return [Failure("HB-RDY-001", task_id, f"record name {match[0]} does not match its body")]
    task = config.load_yaml(root / "tasks" / task_id / "task.yaml")
    if body.get("expected") != task.get("expected"):
        return [Failure("HB-RDY-001", task_id, "record expected differs from task.yaml (a tamper tell)")]
    return body_failures(root, task_id, body)


def problems(root: Path, *, baseline: Mapping | None = None) -> list[str]:
    """The lines `bench validate` prints, `x <code> <task>: <item>: <detail>`, plus non-failing `note:` lines."""
    return []


# --- the readers over a graded run (O3, O4) ------------------------------------------------------------------------


def _rows(run_dir: Path, grading_id: str) -> dict[str, dict[str, dict]]:
    """cell id -> metric id -> score row of one completed grading pass. HB-USR-002 with the reason when it cannot be read."""
    try:
        if grading_id not in views.completed_passes(run_dir):
            raise BenchError("HB-USR-002", f"grading pass {grading_id} is absent or not completed in {run_dir.name}")
        rows = [r for r in views.rows(run_dir, "scores") if r.get("grading_id") == grading_id]
    except (BenchError, OSError, ValueError, KeyError) as exc:
        reason = exc.message if isinstance(exc, BenchError) else f"{type(exc).__name__}: {exc}"
        raise BenchError("HB-USR-002", f"the scores of pass {grading_id} cannot be read: {reason}") from exc
    if not rows:
        raise BenchError("HB-USR-002", f"the scores ledger holds no rows for pass {grading_id}")
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        out.setdefault(r["cell_id"], {})[r["metric_id"]] = r
    return out


def _property_doc(run_dir: Path, cell: str, row: Mapping | None) -> dict | None:
    """The cell's `property.json` through the pointer its score row holds; None when it is not there or not JSON."""
    pointer = (row or {}).get("evidence")
    if not pointer:
        return None
    try:
        doc = json.loads((run_dir / pointer).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def unbiased_failures(run_dir: Path, grading_id: str) -> list[str]:
    """Cell ids with a grading span whose `unbiased_ok` is false. Raises BenchError("HB-USR-002", <reason>) when it cannot run."""
    out = []
    for cell, metrics in sorted(_rows(run_dir, grading_id).items()):
        row = metrics.get(_PROPERTY_PASS)
        if row is None:
            continue
        doc = _property_doc(run_dir, cell, row)
        if doc is None:
            if row["value"] is not None:
                raise BenchError("HB-USR-002", f"cell {cell} has a {_PROPERTY_PASS} value but no readable property.json")
            continue
        if any(not span.get("unbiased_ok") for span in doc.get("spans") or []):
            out.append(cell)
    return out


def comparable_cells(run_dir: Path, grading_id: str) -> tuple[list[str], list[str]]:
    """(cells where the hidden tests and `pass_at_1` disagree, cells where either side is NA), each sorted. Raises like the
    readers. A cell with no `property_check_pass` row (a task with no property grader) is not examined."""
    disagree, not_comparable = [], []
    for cell, metrics in sorted(_rows(run_dir, grading_id).items()):
        row = metrics.get(_PROPERTY_PASS)
        if row is None:
            continue
        doc = _property_doc(run_dir, cell, row)
        if doc is None and row["value"] is not None:
            raise BenchError("HB-USR-002", f"cell {cell} has a {_PROPERTY_PASS} value but no readable property.json")
        hidden = ((doc or {}).get("hidden_tests_pass") or {}).get("value")
        passed = (metrics.get("pass_at_1") or {}).get("value")
        if hidden is None or passed is None:
            not_comparable.append(cell)
        elif (hidden == 1) != (passed == 1):
            disagree.append(cell)
    return disagree, not_comparable


def hidden_test_disagreements(run_dir: Path, grading_id: str) -> list[str]:
    """Cell ids where the hidden tests and `pass_at_1` disagree; `[]` means every comparable cell agreed. Not-comparable
    cells are left out (the discriminate path turns them into HB-RDY-011 items through `comparable_cells`). Raises
    BenchError("HB-USR-002", <reason>) when it cannot run; the caller converts (R-96's third state, never a bare None)."""
    return comparable_cells(run_dir, grading_id)[0]


def property_evidence(run_dir: Path, pointer: str) -> dict:
    """What one cell's check recorded, for the probe digest and the variant compare: `deliverable`, `cases` (id ->
    outcome), `hosts_ready` (the `end: ready` lines of `hosts.jsonl`), `hidden` (the hidden-test value) and `clauses`
    (`clauses.json`, at most 64 KiB, or None). ValueError / OSError name what could not be read.

    assume: W1-F rev 3 gives no `check.deliverable`, `check.cases`, `check.hosts` or `check.clauses` pointers in
    property.json on this base, so the files are read at their fixed places beside it: `<property.json dir>/check/
    check.stdout`, `hosts.jsonl`, `clauses.json` (provisional, seam SR-E3 2). Confirm: a property.json that names them.
    Breaks if false: the evidence dir moves and every check-based trial is HB-RDY-011 (fail closed, never a pass)."""
    doc_path = run_dir / pointer
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    check = doc_path.parent / "check"
    result = json.loads((check / "check.stdout").read_text(encoding="utf-8").splitlines()[0])
    hosts = [json.loads(line) for line in (check / "hosts.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    clauses = None
    if (check / "clauses.json").is_file():
        if (check / "clauses.json").stat().st_size > MAX_VARIANTS_BYTES:
            raise ValueError("clauses.json is over 64 KiB")
        clauses = json.loads((check / "clauses.json").read_text(encoding="utf-8"))
        if not isinstance(clauses, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in clauses.items()):
            raise ValueError("clauses.json is not a {case id: clause text} object")
    return {"deliverable": result["deliverable"], "cases": {c["id"]: c["outcome"] for c in result["cases"]},
            "hosts_ready": sum(1 for h in hosts if h.get("end") == "ready"),
            "hidden": (doc.get("hidden_tests_pass") or {}).get("value"), "clauses": clauses}


# --- the variants file: data, never code (W1-E section 7; W0 section 2) -----------------------------------------------


def _bad(task_id: str, why: str) -> BenchError:
    return BenchError("HB-RDY-005", f"{task_id}: oracle/variants.py {why}")


def variants(root: Path, task_id: str) -> dict[str, dict]:
    """The task's declared defect variants `{name: {flips, clauses, edits}}`, read as data: one top-level `VARIANTS`
    assignment through `ast.literal_eval`; the file is never imported or executed. HB-RDY-005 on any defect: over 64 KiB,
    a parse or recursion error, none or more than one assignment (an annotated or augmented one included), a non-literal,
    a name that fails the charset or `check_segment`, a `clauses` text over 200 characters, an `edits[].file` that fails
    the overlay path rule (before any read), or an `old` that does not occur exactly once in the reference file."""
    path = root / "tasks" / task_id / "oracle" / "variants.py"
    if not path.is_file():
        return {}
    if path.stat().st_size > MAX_VARIANTS_BYTES:
        raise _bad(task_id, f"is over {MAX_VARIANTS_BYTES} bytes")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, RecursionError, MemoryError, ValueError) as exc:
        raise _bad(task_id, f"does not parse ({type(exc).__name__})") from exc
    targets = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "VARIANTS" for t in n.targets)]
    extras = [n for n in tree.body if isinstance(n, ast.AnnAssign | ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id == "VARIANTS"]
    if len(targets) != 1 or extras:
        raise _bad(task_id, "must hold exactly one plain top-level `VARIANTS = {...}` assignment")
    try:
        value = ast.literal_eval(targets[0].value)
    except (ValueError, TypeError, SyntaxError, RecursionError, MemoryError) as exc:
        raise _bad(task_id, f"VARIANTS is not a literal ({type(exc).__name__})") from exc
    if not isinstance(value, dict):
        raise _bad(task_id, "VARIANTS is not a mapping")
    for name, entry in value.items():
        _check_variant(root, task_id, name, entry)
    return value


def _check_variant(root: Path, task_id: str, name, entry) -> None:
    try:
        prop.check_segment("variant name", name if isinstance(name, str) else repr(name), VARIANT_NAME)
    except ValueError as exc:
        raise _bad(task_id, str(exc)) from exc
    if not isinstance(entry, dict) or set(entry) != {"flips", "clauses", "edits"}:
        raise _bad(task_id, f"variant {name} must have exactly the keys flips, clauses and edits")
    flips, clauses, edits = entry["flips"], entry["clauses"], entry["edits"]
    if not isinstance(flips, list) or not all(isinstance(f, str) for f in flips):
        raise _bad(task_id, f"variant {name} flips is not a list of strings")
    if not isinstance(clauses, dict) or not all(isinstance(k, str) and isinstance(v, str) and len(v) <= MAX_CLAUSE_CHARS
                                                for k, v in clauses.items()):
        raise _bad(task_id, f"variant {name} clauses must map strings to texts of at most {MAX_CLAUSE_CHARS} characters")
    if not isinstance(edits, list) or not edits:
        raise _bad(task_id, f"variant {name} edits is not a non-empty list")
    reference = root / "tasks" / task_id / "oracle" / "solutions" / "reference"
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"file", "old", "new"} or not all(isinstance(v, str) for v in edit.values()):
            raise _bad(task_id, f"variant {name} has an edit that is not {{file, old, new}} strings")
        try:
            rel = safe_relpath(edit["file"])
            for part in rel.parts:
                prop.check_segment("overlay component", part, OVERLAY_COMPONENT)
        except (OverlayError, ValueError) as exc:
            raise _bad(task_id, f"variant {name} edit file: {exc}") from exc
        target = reference / rel
        text = target.read_text(encoding="utf-8") if target.is_file() else ""
        if not edit["old"] or text.count(edit["old"]) != 1:
            raise _bad(task_id, f"variant {name} edit does not apply (`old` must occur exactly once in reference/{rel.as_posix()})")
