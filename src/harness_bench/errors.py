"""The closed failure taxonomy: one definition of cause -> stable code -> attribution (ADR-0007 section 6).

A cell's non-completed outcome carries exactly one Cause. An infrastructure or benchmark cause makes the
cell `invalid (...)`, so it is never scored against a harness. Run-level codes (preflight, ledger, grading,
validity, security, usage) live in RUN_CODES. Every code here is stable: it appears in logs, the ledger and
`bench status`, and a test pins each design-table row.
"""

from __future__ import annotations

from enum import Enum

ATTRIBUTIONS = ("agent", "harness", "infrastructure", "benchmark", "none")


class Cause(Enum):
    # name = (code, attribution, label shown in reports)
    timed_out = ("HB-CELL-301", "agent", "timed_out")
    blocked_permission = ("HB-CELL-201", "agent", "blocked (permission)")
    blocked_auth = ("HB-CELL-202", "harness", "blocked (auth)")
    adapter_crash = ("HB-CELL-105", "harness", "failed (adapter crash)")
    protocol = ("HB-CELL-107", "harness", "failed (protocol)")
    provider = ("HB-CELL-108", "infrastructure", "failed (provider)")
    model_unavailable = ("HB-CELL-116", "benchmark", "failed (model unavailable)")
    handshake_timeout = ("HB-CELL-104", "infrastructure", "failed (handshake timeout)")
    workspace = ("HB-CELL-113", "infrastructure", "failed (workspace)")
    spawn = ("HB-CELL-114", "infrastructure", "failed (spawn)")
    build_changed = ("HB-CELL-115", "infrastructure", "failed (build changed)")
    memory = ("HB-CELL-103", "infrastructure", "failed (memory)")
    disk = ("HB-CELL-112", "infrastructure", "failed (disk)")
    host_suspended = ("HB-CELL-106", "infrastructure", "failed (host suspended)")
    unclassified = ("HB-CELL-199", "none", "failed (unclassified)")

    def __init__(self, code: str, attribution: str, label: str) -> None:
        self.code = code
        self.attribution = attribution
        self.label = label

    @property
    def invalidates(self) -> bool:
        """Infrastructure and benchmark causes are never scored against a harness."""
        return self.attribution in ("infrastructure", "benchmark")


RUN_CODES: dict[str, str] = {
    "HB-PRE-002": "an agent instruction file (CLAUDE.md, .claude/CLAUDE.md, AGENTS.md, GEMINI.md, .github/copilot-instructions.md, .github/instructions/**/*.instructions.md) in or above the cells root",
    "HB-PRE-003": "free disk below 20 GB, or below the projected need",
    "HB-PRE-005": "long paths not enabled (Windows LongPathsEnabled, git core.longpaths)",
    "HB-PRE-007": "a planned harness build is missing from the tools folder, or its hash differs",
    "HB-PRE-008": "Copilot instruction list failed or pack-off loaded repository instructions",
    "HB-RUN-001": "ledger append failed: launching stopped, run incomplete",
    "HB-RUN-002": "a kill unconfirmed after 5 minutes (retries continue; the slot stays held)",
    "HB-RUN-003": "teardown refused: the run's lock is held by a live engine",
    "HB-RUN-004": "free space below the floor: launching stopped, running cells continue",
    "HB-RUN-005": "run lock held: another engine is running this run",
    "HB-RUN-006": "run stopped by the operator (bench stop, or a decision answered stop): running cells stopped, no new launch",
    "HB-RUN-007": "spend cap reached: the run stopped (the spend_cap default or answer)",
    "HB-LED-001": "torn tail repaired by its writer",
    "HB-LED-002": "chain or seal break",
    "HB-LED-003": "duplicate key or second outcome",
    "HB-LED-004": "abandoned grading segment (warning; skipped by views)",
    "HB-LED-005": "archive_hash does not match the attempt's archive_files rows",
    "HB-LED-006": "warning: grading.completed records no heads (written before ruling R-2); only its seals are checked",
    "HB-GRD-001": "grade lock held",
    "HB-GRD-002": "grading step timeout",
    "HB-GRD-003": "grader failed or returned malformed output: its metrics are NA with the exception type, and the pass continues",
    "HB-GRD-004": "grading pass incomplete: a (cell, metric) row is missing, duplicated or outside the applicable set; the pass is not completed",
    # review w3-gwi-1 A1: the live-run refusal takes its own code; HB-GRD-003 keeps its one meaning (R-65)
    "HB-GRD-005": "a run is live (lock liveness alive or stalled): judge model calls refused before any spawn",
    "HB-VAL-001": "validity: no model call",
    "HB-VAL-002": "validity: model mismatch",
    "HB-VAL-003": "validity: not recorded (the usage record is missing or unreadable)",
    "HB-VAL-004": "validity: tools denied by hook",
    "HB-VAL-005": "warning: model_calls tokens differ from the ACP turn total, or the check did not run",
    "HB-VAL-006": "warning: executed-build check skipped (no agent_version, or no recorded self-report)",
    "HB-VAL-007": "validity: build mismatch (the session's agent_version differs from the pinned build's recorded self-report)",
    "HB-VAL-008": "validity: out-of-profile tool called (a class-other tool call executed)",
    "HB-VAL-009": "warning: out-of-profile attempt refused (the driver counted a permission request, or a native hook denied it)",
    "HB-SEC-001":"credential value found in a report to be published",
    "HB-USR-001": "unknown run id",
    "HB-USR-002": "invalid input",
    "HB-TEL-001": "native-record field missing: NOT_RECORDED",
    # The model gateway's judge lookups (design phase3-gateway-judges section 17; review w3-gwi-1 A2: one registry).
    "HB-GW-001": "judge unavailable: CLI error, timeout, provider error, breaker open, or a store write error other than a lost race",
    "HB-GW-002": "invalid output",
    "HB-GW-003": "served model not the pin",
    "HB-GW-004": "blinding scan hit",
    "HB-GW-005": "store entry invalid, or not matched by its storing row",
    "HB-GW-006": "tool event in a judge call",
    "HB-GW-007": "judge not qualified",
    "HB-GW-008": "artifact over the bound or not UTF-8",
    "HB-GW-009": "withheld: sensitive content",
    "HB-GW-010": "leftover credential copy (a verify error)",
    "HB-GW-011": "judge build changed",
}

_ALL_CODES = set(RUN_CODES) | {c.code for c in Cause}


class BenchError(Exception):
    """A failure with a stable error code (Observability Standard: every failure carries a code)."""

    def __init__(self, code: str, message: str) -> None:
        if code not in _ALL_CODES:
            raise ValueError(f"unknown error code {code!r}")
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
