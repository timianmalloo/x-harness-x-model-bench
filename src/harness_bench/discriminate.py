"""bench discriminate: run a task's reference, naive and defect variants as synthetic cells through the real engine,
archiver and grading pass, and write the create-once discrimination record (W1-E; ADR-0016 section 4; R-98; grade class).

The record body is a pure function of its key (task version, engine identity, platform): it holds no run id, grading id,
clock, duration or path, so a retry at an unchanged key writes equal bytes and is a confirmation. Skeleton (E0): `run`
plans and runs nothing and returns `outcome: "skeleton"`; the launcher forwards the whole environment (the wrong value
the E1 allowlist test is red against).
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from harness_bench.synthetic_agent import SYNTHETIC_VERSION

AGENT = Path(__file__).with_name("synthetic_agent.py")


@dataclass(frozen=True)
class Result:
    outcome: str  # written | confirmed | skeleton
    record_path: Path | None = None
    run_id: str | None = None
    notes: tuple[str, ...] = ()


class SyntheticLauncher:
    """The engine's Launcher for the synthetic harness: a stdlib ACP process; no login, no usage record."""

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
        return {"version": SYNTHETIC_VERSION}

    def seed(self, home: Path, cell: dict) -> None:
        home.mkdir(parents=True, exist_ok=True)

    def clean(self, home: Path) -> None:
        return None

    def argv_env(self, cell: dict, home: Path, traceparent: str):
        return [sys.executable, str(AGENT)], dict(os.environ, HB_SYNTH_OVERLAY=str(self.overlays[cell["combo"]]),
                                                  TRACEPARENT=traceparent)

    def records(self, home: Path, session_id: str) -> list[Path]:
        return []

    def read(self, path: Path):
        raise NotImplementedError("the synthetic agent writes no native record")


def run(root: Path, task_id: str, *, runs: Path, cells_root: Path, upstream_root: Path | None = None) -> Result:
    """One discrimination trial of `task_id`. Skeleton: plans and runs nothing, writes no file."""
    return Result(outcome="skeleton")
