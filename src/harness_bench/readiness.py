"""Task readiness: what `bench validate` says about a property task (W1-E section 8; grade class).

A property task is `ready` only because a discrimination record, made by the real engine and grader, shows its hidden
check discriminates. This module recomputes every verdict from the record and the current task files; it trusts nothing
the record says about itself. Skeleton (E0): every function returns the empty, well-formed answer.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Failure:
    code: str  # "HB-RDY-003"
    item: str  # "exploit_probes_blocked"
    detail: str  # "reference expected 1.0000, observed 0.0000"


def contract_failures(root: Path, task_id: str) -> list[Failure]:
    """HB-RDY-005..008 for one task: what needs no run."""
    return []


def record_failures(root: Path, task_id: str, *, baseline: Mapping | None = None) -> list[Failure]:
    """HB-RDY-001..004, 010, 011 for one task: what the discrimination record must show."""
    return []


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
