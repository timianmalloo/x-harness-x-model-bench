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

from dataclasses import dataclass, field
from pathlib import Path

EXPECTED = "tests/fixtures/gate/expected-counts.yaml"


@dataclass
class Report:
    run: str
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def gate(run_dir: Path, grade, **kwargs) -> Report:
    return Report(run_dir.name)  # red: not built
