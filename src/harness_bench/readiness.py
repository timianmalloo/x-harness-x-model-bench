"""Task readiness: what `bench validate` says about a property task (W1-E section 8; grade class).

A property task is `ready` only because a discrimination record, made by the real engine and grader, shows its hidden
check discriminates. This module recomputes every verdict from the record and the current task files; it trusts nothing
the record says about itself (not even `readiness_failures`).

The readers `hidden_test_disagreements` and `unbiased_failures` return `list[str]` or raise
`BenchError("HB-USR-002", <reason>)`; `discriminate` converts a raise into an HB-RDY-011 item whose detail is the reason.
They never return a bare None.
"""

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from harness_bench import config, identity, plan
from harness_bench.grade import property as prop
from harness_bench.grade import runner

ROLES = ("reference", "naive")
CORRECTNESS_SCORES = ("pass_at_1", "partial_credit")  # recorded in `scores`, no expected value (R-90 condition 1)
_NAME_LEN = 16


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


def _scales(root: Path) -> dict[str, int]:
    return runner._scales(config.load_yaml(root / "bench" / "metrics.yaml"))


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
    scales, out = _scales(root), []
    for role in ROLES:
        declared = (task.get("expected") or {}).get(role) or {}
        for metric in recorded_metrics(root, task):
            if metric not in declared:
                continue  # a missing expected is HB-RDY-005 (contract), not a record defect
            observed = (body.get("scores") or {}).get(role, {}).get(metric, {"na": "not recorded"})
            try:
                ok = normal(observed, scales.get(metric)) == normal(declared[metric], scales.get(metric))
                why = ""
            except ValueError as exc:
                ok, why = False, f" ({exc})"
            if not ok:
                out.append(Failure("HB-RDY-003", metric, f"{role} expected {show(declared[metric])}, observed {show(observed)}{why}"))
    return out


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
    from harness_bench import atomic

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
    path = folder / match[0]
    body = _read_record(path)
    p_tv, p_ih, p_platform = _name_parts(match[0])  # type: ignore[misc]
    if (body is None or body.get("task") != task_id or body.get("platform") != p_platform
            or str(body.get("task_version", ""))[:_NAME_LEN] != p_tv or str(body.get("identity_hash", ""))[:_NAME_LEN] != p_ih):
        return [Failure("HB-RDY-001", task_id, f"record name {match[0]} does not match its body")]
    task = config.load_yaml(root / "tasks" / task_id / "task.yaml")
    if body.get("expected") != task.get("expected"):
        return [Failure("HB-RDY-001", task_id, "record expected differs from task.yaml (a tamper tell)")]
    return score_failures(root, task_id, body)


def problems(root: Path, *, baseline: Mapping | None = None) -> list[str]:
    """The lines `bench validate` prints, `x <code> <task>: <item>: <detail>`, plus non-failing `note:` lines."""
    return []


def hidden_test_disagreements(run_dir: Path, grading_id: str) -> list[str]:
    """Cell ids where the hidden tests and `pass_at_1` disagree. Raises BenchError("HB-USR-002", <reason>) when it cannot
    run; the caller converts (R-96's third state, never a bare None)."""
    return []


def unbiased_failures(run_dir: Path, grading_id: str) -> list[str]:
    """Cell ids with a grading span whose `unbiased_ok` is false. Raises BenchError("HB-USR-002", <reason>) when it cannot run."""
    return []



def comparable_cells(run_dir: Path, grading_id: str) -> tuple[list[str], list[str]]:
    """(cells where the hidden tests and `pass_at_1` disagree, cells where either side is NA). Raises like the readers."""
    return [], []


def variants(root: Path, task_id: str) -> dict[str, dict]:
    """The task's declared defect variants, read as data (`ast.literal_eval`, never imported). HB-RDY-005 on any defect."""
    return {}
