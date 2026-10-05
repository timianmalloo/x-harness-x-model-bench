"""The campaign record: one ledger per campaign, one lock, one fold (W1-C rev 2 under W0 rev 6; ADR-0016, ADR-0017, ADR-0018 11).

SKELETON (red protocol, W1-C section 13): final signatures, neutral wrong values. The behaviour lands in the green commit.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from harness_bench import ledger

FIELDS: Mapping[str, Mapping[str, str]] = {  # exact field sets besides kind, campaign_id and the stamp; s=str, i=int, d=dict
    "campaign.created": {"question": "s"},
    "baseline.recorded": {"identity_hash": "s", "bench_commit": "s"},
    "defect_fix.admitted": {"defect_class": "s", "commit": "s", "changes": "d", "scope": "s"},
    "power.recorded": {"role": "s", "input_hash": "s"},
    "ring_run.attached": {"ring_hash": "s", "run_id": "s", "plan_hash": "s"},
    "pilot.passed": {"run_id": "s", "grading_id": "s", "gate_input_hash": "s"},
    "admission.decided": {"task": "s", "admitted": "i", "reason": "s"},
    "registered": {"prereg_hash": "s"},
    "grid.attached": {"run_id": "s", "plan_hash": "s"},
    "concluded": {},
    "abandoned": {"reason": "s"},
}
HOUSEKEEPING = frozenset({ledger.TAIL_REPAIRED})
FREE_TEXT = frozenset({("campaign.created", "question"), ("abandoned", "reason"), ("admission.decided", "reason")})
TEMP_MIN_AGE_S = 3600
CAMPAIGN_ID = r"^[a-z0-9][a-z0-9-]{0,39}$"


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    detail: str
    level: str = "error"


@dataclass(frozen=True)
class CampaignState:
    campaign_id: str
    state: str
    rows: tuple[dict, ...]


@dataclass(frozen=True)
class RunFacts:
    run_id: str
    plan_present: bool
    plan_hash: str
    plan_campaign_id: str | None
    plan_prereg_hash: str | None
    plan_run_identity_hash: str | None
    plan_ring_hash: str | None
    grade_identity_hash: str


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    reasons: tuple[str, ...]


@dataclass
class Session:
    root: Path
    campaign_id: str
    state: CampaignState
    swept: list[Path]
    skipped: list[Path]


def validate_id(kind: str, value: str) -> str:
    return value


def campaign_dir(root: Path, campaign_id: str) -> Path:
    return root / "bench" / "campaigns" / campaign_id


def lock_path(root: Path, campaign_id: str) -> Path:
    return campaign_dir(root, campaign_id) / "campaign.lock"


def fold(rows: Sequence[Mapping], campaign_id: str = "") -> CampaignState:
    return CampaignState(campaign_id, "draft", ())


def read(root: Path, campaign_id: str) -> CampaignState:
    return CampaignState(campaign_id, "draft", ())


def effective_identity(root: Path, state: CampaignState, upto_seq: int | None = None) -> dict:
    return {"schema": "", "components": {}}


def check_fix(effective: Mapping, changes: Mapping) -> None:
    return None


def eligibility(state: CampaignState, effective: Mapping, run: RunFacts, first_grid: RunFacts | None) -> Eligibility:
    return Eligibility(False, ())


def run_facts(run_dir: Path, grading_id: str) -> RunFacts:
    return RunFacts(run_dir.name, False, "", None, None, None, None, "")


def verify(root: Path, campaign_id: str) -> list[Finding]:
    return []


@contextmanager
def session(root: Path, campaign_id: str, *, others_extra: Sequence[tuple[Path, str]] = (), wait_s: float = 0.0,
            create: bool = False) -> Iterator[Session]:
    yield Session(root, campaign_id, CampaignState(campaign_id, "draft", ()), [], [])


def _append(sess: Session, kind: str, **fields) -> dict:
    return {}


def sweep_folder(cdir: Path, folder: Path, lock) -> tuple[list[Path], list[Path]]:
    return [], []


def create(root: Path, campaign_id: str, question: str) -> str:
    return ""


def status_text(root: Path, campaign_id: str) -> tuple[str, list[Finding]]:
    return "", []
