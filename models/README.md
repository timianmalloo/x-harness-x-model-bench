# Formal models of the benchmark itself

TLA+ specs that TLC checks in CI. They are written before the code they describe, and that code's states and transitions must map onto them one to one (spec US-44).

| File | Models | Checks | Design |
| --- | --- | --- | --- |
| `run_lifecycle.tla` | One benchmark run: write-ahead launch intent, the prompt ack barrier, kill → confirm → record, stop, one decision request, crash and resume with reconciliation, archive-then-delete, and grading passes under `grade.lock` | Safety invariants, liveness properties and a reachability witness; every invariant and property has a seeded-bug variant that TLC must reject | `docs/design/run-lifecycle-model.md` |
| `coordination_protocol.tla` | *Not yet written.* The pack's coordination protocol as `coord-core.py` implements it: leases (claim, release, `except`), seats, mail, leader designation | Taken from the pack's own docs and tests, never inferred from our reading of the code alone. Starts from the G1 reference model. | S-14 |

`protocol_conformance` (grader `coordination`) will replay each run's coordination ledger as a trace against `coordination_protocol.tla`. Toolchain versions are recorded in the run fingerprint (spec S-12).

Configurations:
- `run_lifecycle.safety.cfg`: safety at the US-44 bounds.
- `run_lifecycle.grading.cfg`: grading mutual exclusion at two passes.
- `run_lifecycle.liveness.cfg`: liveness at one cell.

Run `python tools/check_models.py` (`--quick` for small bounds only, `--deep` to add 2 crashes). The script fetches the pinned `tla2tools.jar` into `.tools/` and checks its sha256. It needs Java 11 or later.
