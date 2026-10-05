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
    # W0 rev 5 §11: all reserved E1 rows precede the dependent build tracks.
    "HB-LED-007": "create-once conflict: a create-only file exists with different bytes (determinism defect; never overwritten)",
    "HB-IDN-001": "engine identity drift: launching stopped; the stop event names the differing components",
    "HB-IDN-002": "a `src/` file has no run/grade class",
    "HB-PLN-001": "launch-balance bound violated (EV-17)",
    "HB-PLN-002": "arm or role binding invalid (unbound role, a pack on `off`, a duplicate arm, more than one `off`)",
    "HB-PLN-004": "plan refused by its kind: a measurement plan names a task that is not `ready` or (rev 5, SR-E1 2) a `synthetic` combo, or a discrimination plan names a `stub` (names every task and its status, and every synthetic combo) (rev 3, SR-1)",
    "HB-PLN-005": "a single-pack reader got a plan with two or more pack-bearing arms (names the arms; `plan_pack`, section 5). Raised only by `board.compare` in E1 (rev 4); X-A3 retires it in E3 when `board.compare` reads comparison pairs (rev 3, RV-PAT W1-A 1)",
    "HB-PWR-001": "power-analysis inputs invalid (names the field)",
    "HB-CHK-001": "check output invalid",
    "HB-CHK-002": "invalid (check tampered)",
    "HB-CHK-003": "check exceeded its bound",
    "HB-CHK-004": "grading step spans a host suspend: NOT_RECORDED, re-run next pass",
    "HB-GRD-007": "grading pass of a campaign run refused: `campaign.lock` is held (rev 2, RV-DS 8)",
    "HB-RDY-001": "no discrimination record for the current task version",
    "HB-RDY-002": "the record's engine identity differs from the current one (or the baseline)",
    "HB-RDY-003": "a metric differs from its declared expected value (names metric, expected, observed)",
    "HB-RDY-004": "discrimination record stale against its run (`<metric> copy <a>, run <b>`)",
    "HB-RDY-005": "property-task contract field missing or invalid (EV-1), including a check `env` name outside the allowlist",
    "HB-RDY-006": "prompt states a listed latent-requirement term (names term and line)",
    "HB-RDY-007": "property pair rule violated: not two tasks, or one base (DR-T1)",
    "HB-RDY-008": "check declares a container runtime or a Linux-only tool",
    "HB-RDY-009": "a frozen task value differs from the canonical function's output (HASH-A)",
    "HB-RDY-010": "a discrimination re-run at an existing key disagrees with the stored record (determinism defect; names metric, stored, new) (rev 2, RV-DS 2)",
    "HB-RDY-011": "discrimination trial untrustworthy: a trial cell has a check NA row (HB-CHK-001..003), a span with `unbiased_ok` false, a hidden-test reader that disagrees or raised (rev 6, R6-13), or a case `outcome: timeout` that `expected` and the declared `flips` do not name (rev 6.1); an NA equal to a declared `expected: {na}` is exempt (rev 5, SR-E1 4; W1-E §8.4)",
    "HB-CMP-001": "campaign lock held",
    "HB-CMP-002": "command refused in the campaign's current state (names the item and an action)",
    "HB-CMP-003": "campaign verify failed (chain, name ≠ hash, or a changed committed file; names it)",
    "HB-CMP-004": "refused: a campaign run's `grade.lock` or (rev 6, R6-4) its run lock is held (names the lock)",
    "HB-CMP-005": "unknown campaign id",
    "HB-CMP-006": "baseline refused (ADR-0017 §3; names the unmet precondition)",
    "HB-CMP-007": "defect fix refused (ADR-0017 §4: class absent, before-hash mismatch, or an unnamed component)",
    "HB-CMP-008": "registration refused (pilot gate, pilot coverage, or an MDE not accepted)",
    "HB-CMP-009": "pre-registration frozen: a grid run is attached (rev 2)",
    "HB-CMP-010": "campaign run refused: the run is not attached, or its plan's `prereg_hash` is not the registered one (rev 2, RV-DS 1). Rev 4: also `attach` refused on a prereg-hash mismatch or a drifted tree, a pilot plan with no matching `ring_run.attached`, and a `plan_hash` mismatch. Rev 6 (R6-6): a plan whose `kind` is not `measurement`, or with a `synthetic` combo",
    "HB-PRE-002": "an agent instruction file (CLAUDE.md, .claude/CLAUDE.md, AGENTS.md, GEMINI.md, .github/copilot-instructions.md, .github/instructions/**/*.instructions.md) in or above the cells root",
    "HB-PRE-003": "free disk below 20 GB, or below the projected need",
    "HB-PRE-005": "long paths not enabled (Windows LongPathsEnabled, git core.longpaths)",
    "HB-PRE-007": "a planned harness build is missing from the tools folder, or its hash differs",
    "HB-PRE-008": "Copilot instruction list failed or pack-off loaded repository instructions",
    "HB-RUN-001": "ledger append failed: launching stopped, run incomplete",
    "HB-RUN-002": "a kill unconfirmed after 5 minutes (retries continue; the slot stays held)",
    "HB-RUN-003": "teardown refused: the run's lock is held by a live engine",
    "HB-RUN-004": "free space below the floor: launching stopped, running cells continue",
    "HB-RUN-005": "run lock held: another engine is running this run; retry if no run is live",
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
    "HB-GRD-006": "a grading step's own upward-discovering tool (uv, pip, dotnet, ...) could reach this repository's project file: the grading root sits in or under a directory with a pyproject.toml or .python-version",
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
    # design section 11 as amended by R-72 item 4: checked only when the labels file exists, all or none
    "HB-CAL-001": "labels do not match the manifest",
    # phase 4 statistics (design phase4-statistics section Seams Z-2; R-78 condition 7)
    "HB-STA-001": "statistics input spans more than one grading pass of one run",
    "HB-STA-002": "runs not comparable: every difference named",
    "HB-STA-003": "--resamples below 2000 in bench report (US-36, R-78 condition 7)",
    # phase 4 report, R7 (design phase4-report.md section 8; ruling R-81 condition 3): bench report --summaries
    # mirrors the judge gateway's own live-run refusal (HB-GRD-005) at its own call site.
    "HB-SUM-001": "bench report --summaries refused: a run is live (lock liveness alive or stalled)",
    # D&P Architect review (R7, before the final commit): a second concurrent `bench report --summaries`
    # for the same run is refused rather than racing SegmentWriter.reopen and breaking the segment's chain.
    "HB-SUM-002": "summary_records write lock held: another bench report --summaries is writing this run's summaries",
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
