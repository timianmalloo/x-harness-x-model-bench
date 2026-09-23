# Formal models of the benchmark itself

TLA+ specs that TLC checks in CI. They are written before the code they describe, and that code's states and transitions must map onto them one to one. None exist yet.

| File | Models | Invariants it must check | Spec |
| --- | --- | --- | --- |
| `run_lifecycle.tla` | One benchmark run: cells move through intent → bootstrap → run → capture → grade → record → teardown, up to 4 in parallel, with crash and resume | The coordinator session never runs a cell. Nothing is deleted before its archive is verified. Each cell is graded exactly once. Resume after a crash is idempotent. No more than `parallelism` cells run at once. | S-13 |
| `coordination_protocol.tla` | The pack's coordination protocol as `coord-core.py` implements it: leases (claim, release, `except`), seats, mail, leader designation | Taken from the pack's own docs and tests, never inferred from our reading of the code alone. Starts from the G1 reference model. | S-14 |

`protocol_conformance` (grader `coordination`) replays each run's coordination ledger as a trace against `coordination_protocol.tla`.

Toolchain: TLA+ tools on a pinned JDK, versions recorded in the run fingerprint (spec S-12).
