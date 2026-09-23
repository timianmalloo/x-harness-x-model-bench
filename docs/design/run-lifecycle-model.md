---
id: "design-run-lifecycle-model"
title: "Design: run lifecycle model (models/run_lifecycle.tla)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton (S-13)"
tags: [benchmark, tla, model-checking, runner, lifecycle]
links:
  - { to: arch-harness-bench, rel: implements }
  - { to: adr-0007-run-engine, rel: implements }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: adr-0013-native-cells, rel: implements }
  - { to: spec-harness-bench, rel: implements }
review-by: "2027-03-22"
summary: >-
  The TLA+ model of one run's lifecycle, the proof obligation the run engine is built against (US-44).
  TLC checks 16 safety invariants at the US-44 bounds (3 cells, parallelism 2, 1 engine crash) and at
  small bounds with `bench grade` contending, grading mutual exclusion at 2 passes, and 5 liveness
  properties at 1 cell; each of 21 seeded-bug variants is rejected by its own target checked alone,
  and a witness shows every cell can finish.
  A mapping table binds every model action to the engine's ledger events, and a conformance test keeps
  the two in step.
review-suggested: []
---

# Design: run lifecycle model

- **Status:** Draft; the design gate passed with conditions at round 3 (below).
- **Spec / architecture:** `docs/specs/harness-bench.md` US-44 (and US-15–US-19, US-45); `docs/architecture.md` "Lifecycle model obligations"; ADR-0006, ADR-0007.
- **Delivery phase:** Phase 1 · walking skeleton, first component (the spec orders the model before the runner). Nothing is mocked: the model is complete for the whole lifecycle. The engine implements a subset in phase 1 (no stop, decision or resume handling), and the conformance test covers the implemented subset (spec US-44, amended wording "for the states implemented at the current milestone").
- **Author / date:** Claude Code (Opus 5.5) for @timianmalloo, 2026-09-23.

## Responsibility

State the run lifecycle precisely enough that its safety and liveness claims are machine-checked before any engine code exists, and keep the engine honest afterwards.

It is **not** the engine, and it does not model: the agent's work inside a cell, telemetry, graders' semantics, or the network. Those have no concurrency that the model's invariants depend on.

## Contracts

**Exposed:**
- `models/run_lifecycle.tla`: the spec, `Spec == Init /\ [][Next]_vars /\ Fairness`.
- `models/run_lifecycle.safety.cfg`: 3 cells, parallelism 2, 1 crash, 1 grading pass, only the engine grading, `SYMMETRY Symmetry` (cells and passes), the 16 invariants.
- `models/run_lifecycle.grading.cfg`: 2 cells, parallelism 2, 1 crash, 2 grading passes, the engine and `bench grade`, symmetry, the grading invariants.
- `models/run_lifecycle.liveness.cfg`: 1 cell, 1 crash, 2 pass ids, only the engine grading, no symmetry, the 5 temporal properties.
- `tools/check_models.py`: exit 0 only if (a) the real design passes every configuration it runs, (b) the reachability witness `NotAllCellsFinished` is violated (the run can finish), and (c) every seeded variant is rejected by its named invariant or property, **checked alone** (TLC stops at the first violation, so another invariant could otherwise pre-empt the target). `--quick` skips the US-44-bounds safety run; `--deep` adds it at 2 crashes. The constant `Graders` selects whether `bench grade` runs beside the engine.
- **The action ↔ event mapping (the conformance contract with the engine):**

| Model action | Engine behaviour and ledger event (`events.entity_kind` · transition) | Phase |
| --- | --- | --- |
| `WriteIntent(c)` | cell · `cell.launch_intent` (fsynced; phase 5 adds `job_name = hb-<run>-<cell>-<attempt>` for resume) | 1 |
| `StartCell(c)` | the driver creates the cell's Job Object (kill-on-close, breakaway not allowed, handle not inheritable), spawns the ACP adapter suspended with an explicit handle list, assigns it, resumes it → attempt · `attempt.process_started{pid, created_at, build, build_hash}` | 1 |
| `StartFails(c)` | working-copy, home, build-check or spawn failure; if assignment failed, the suspended process is terminated and confirmed gone first → cell · `cell.outcome{failed(workspace \| spawn \| build changed)}` | 1 |
| `QueuePromptSent(c)` | the worker puts `prompt_sent` on the engine queue and **blocks** on an ack | 1 |
| `PersistPromptSent(c)` | the engine thread appends and fsyncs cell · `cell.prompt_sent`, then sets the ack | 1 |
| `SendPrompt(c)` | the worker, holding the ack, writes ACP `session/prompt` once (no event) | 1 |
| `CellExits(c)` / `CellDies(c)` | at `end_turn` or adapter EOF the engine terminates the job; the job's active-process count reaching 0 is the exit (the engine re-issues `TerminateJobObject` until it does) | 1 |
| `EngineKill(c)` | budget or handshake deadline → `TerminateJobObject` (no event yet) | 1 |
| `RecordExit(c)` | after the job reports no active process → cell · `cell.outcome{completed \| timed_out \| failed(cause) \| stopped}` | 1 |
| `Archive(c)` | cell · `cell.archived{archive_attempt, archive_hash}` (the cell's job has no active process) | 1 |
| `DeleteWorkspace(c)` | cell · `cell.workspace_deleted` | 1 |
| `GradeStart/GradeCell/GradeEnd` | grading · `grading.started`, score rows, `grading.completed`, under `grade.lock`, each process with its own `grading_id`. The engine starts its one pass only when every cell has ended and been archived (or was never launched because of a stop), and ends it only after grading every archived cell; `bench grade` may run a pass at any time | 1 |
| *(internal progress, no model action)* | cell · `cell.workspace_built`; attempt · `attempt.handshake_done` — stutter steps for the model; used for phase timings | 1 |
| `StopCell(c)` | stop → terminate every running cell's job; `cell.outcome{stopped}` recorded by `RecordExit` after the job is empty; unlaunched cells stay unstarted | 2 |
| `WriteControl(k)` / `ApplyStop` / `ApplyAnswer` / `RemoveControl(k)` | control file (temp + rename) / control · `control.applied{uuid}` / file removed | 2 |
| `RaiseDecision` / `TimeoutDefault` | decision · `decision.opened` / `decision.resolved{default}` | 2 |
| `Crash` / `Resume` | process death / run · `run.resumed{epoch}` | 5 |
| `ReconcileKill(c)` / `ReconcileRecord(c)` / `ReconcileDone` | open each recorded job by name; terminate it and wait for 0 active processes; not found means the tree is gone (with kill-on-close none should survive) / cell · `cell.reconciled{crashfail \| relaunchable}` / run · `run.reconciled` | 5 |

**Consumed:**

| Dependency | Pin | Confidence |
| --- | --- | --- |
| TLA+ tools | `tla2tools.jar` v1.7.4, sha256 `936a2620…0e88`, fetched from the tlaplus GitHub release by `check_models.py` into gitignored `.tools/` | Verified: ran this session |
| Java runtime | ≥ 11; JDK 21 on the workstation. CI uses `actions/setup-java` (Temurin 21) | Verified locally; CI Inferred until the first CI run |

## Patterns

- **Executable specification / model checking** (Lamport). The design artifact is the TLA+ spec itself.
- **Seeded-fault (mutation) testing of the model.** One `BUG` constant switches each guard off. A variant that passes proves the model cannot see that defect: a vacuity check, the model's analogue of D1 mutation testing.
- **History variables** (`prompts`, `wasStopped`, `applyCount`, `gradeCount`, `flags`) record what happened, so invariants can speak about forbidden events. Guards never read them; a guard reading history hid a defect twice (see the confidence ledger).
- **Reachability witness.** An invariant expected to be violated (`NotAllCellsFinished`) proves the checked space reaches a finished run, so safety is not passing on a stalled model.
- **Symmetry reduction** for safety only (TLC's symmetry is unsound for liveness).
- **Solution-Selection Ladder:**
  - The spec requires TLC (US-44), so this is the minimum.
  - One model file, three configurations, one stdlib Python script.
  - No new Python dependency; the jar is fetched pinned and hash-checked, not vendored.

## Data shapes

The model's variables mirror the ledger (ADR-0006):

| Model variable | Ledger meaning |
| --- | --- |
| `intent`, `promptSent`, `outcome`, `archived`, `deleted` | `events` rows per cell |
| `controlApplied` | `control.applied` rows |
| `decision`, `resolutions` | decision transitions |
| `passState`, `graded` | grading pass transitions and score rows |

State the ledger cannot know is modelled separately:
- physical: `proc` (the cell's process tree), `killRequested`;
- process memory, lost on a crash: `queued`, `pendingSend`, `killReason`;
- the engine: `engine`, `epoch`, `launchEpoch`.

History variables are read only by invariants, never by guards: `prompts`, `wasStopped`, `applyCount`, `gradeCount`, `flags`.

**Configurations:**

| Configuration | Bounds | Checks | Runs |
| --- | --- | --- | --- |
| Small bounds (derived from `safety.cfg`) | 2 cells, parallelism 1, 1 crash, 1 pass; the engine and `bench grade` | all 16 invariants | Every CI run |
| `run_lifecycle.safety.cfg` (US-44 bounds) | 3 cells, parallelism 2, 1 crash, 1 pass; only the engine grades; symmetry over cells and passes | all 16 invariants | Nightly CI, and locally before any engine change that touches a transition |
| `--deep` | as `safety.cfg`, 2 crashes | all 16 invariants | On demand (stopped unfinished at 170 M states; no result) |
| `run_lifecycle.grading.cfg` | 2 cells, parallelism 2, 1 crash, 2 passes; the engine and `bench grade`; symmetry | `TypeOK` and the 3 grading invariants, including `AtMostOneActivePass` | Every CI run |
| `run_lifecycle.liveness.cfg` | 1 cell, 1 crash, 2 pass ids; only the engine grades; no symmetry | 5 temporal properties | Every CI run |
| Seeded variants | small bounds (the grading or liveness configuration where the defect needs it) | each variant's target alone | Every CI run |

- **Liveness at 1 cell:** the three properties are per cell, and cells interact only through the parallelism guard. That guard never binds when parallelism ≥ cells, which was already true of the earlier 2-cell configuration. The 2-cell run was stopped after 14 minutes of state growth.
- **Why the engine grades alone at 3 cells:** with `bench grade` as well, the US-44-bounds run had not finished after 10 minutes at 43 GB. Grading contention is about the lock, not the cell count, so it is checked at small bounds (every invariant) and in the grading configuration (two passes).
- **Variant exceptions:** `no_lock` uses the grading configuration (it needs two passes). `reconcile_no_wait` runs at parallelism 2 (it needs a free slot beside an orphan). Liveness variants use the liveness configuration with only their target property.

## Error & concurrency model

The model *is* the concurrency model:
- one engine process (crash and resume);
- a worker queue and an ack barrier between each worker and the engine thread;
- cells that can exit before or after their prompt and die asynchronously after a kill. The model also lets a cell run on while the engine is down; with kill-on-close none does, so the model checks a superset;
- an environment writing control files;
- a concurrent `bench grade` process contending for `grade.lock` with its own passes.

Crash semantics:
- process memory (`queued`, `pendingSend`, `killReason`) and the engine's hold on `grade.lock` are lost (the OS releases the file lock);
- the ledger survives; with kill-on-close, the cells do not.

Kill semantics: kill first, confirm the cell's job is empty, then record the outcome. Reconciliation confirms that every recorded cell process of the run is gone, whatever its recorded state, before any launch.

## Failure-mode analysis

| Failure mode | From which choice | Disposition | How addressed | Detection | Test |
| --- | --- | --- | --- | --- | --- |
| Vacuous model: an invariant holds only because the model cannot reach the bad state | Abstract modelling | prevent + detect | One seeded variant per invariant and per property, each asserted rejected by its own target | `check_models.py` prints `FAIL <bug> NOT rejected` | 21 variants, all rejected by their own target checked alone; `test_every_checked_property_has_a_seeded_variant`; `test_variant_config_checks_only_its_target` (defect class MOD-A) |
| A guard reads a history variable and hides a defect | History variables | prevent | Guards read only ledger, physical or process state | The `relaunch_prompted` variant | Found twice and fixed: `SendPrompt` (v1), then `QueuePromptSent` (v2); now the volatile `queued` / `pendingSend` |
| Two guards enforce one invariant, masking a seeded bug | Defence in depth in the model | prevent | One guard per mechanism, or the variant removes every guard for it | `exceed_parallelism`, `reconcile_no_wait` | Found three times and fixed: parallelism (v1); `ignore_orphans` replaced by `NoLaunchBesideOrphan`; `reconcile_no_wait` now removes both waits |
| A variant made vacuous by a later fix | Model revision | detect | Re-run every variant after each model change | `archive_live` after kill → record | Found and fixed: `archive_live` redefined as archiving once a kill is requested |
| Actions too atomic (kill and record, persist and send, in one step) | Model granularity | prevent | v2 splits kill → confirm → record and queue → persist → send, so a crash can fall between each pair | `record_without_kill`, `send_before_persist` | Design gate round 1 (Distributed Systems) |
| Failure paths missing (budget kill, failure before the prompt, grading contention) | Model scope | prevent | `EngineKill`, `StartFails`, `CellExits` before a prompt, `RecordExit`; the grading configuration at 2 passes | `launch_after_outcome`, `no_lock` | Design gate round 1 (Test Architect) |
| Safety passes only because the run stalls early | `CHECK_DEADLOCK FALSE` | detect | Reachability witness `NotAllCellsFinished`, expected violated | The `witness` line | Every run |
| Model and engine drift apart | Two artifacts | detect | Mapping table above; an engine test replays the event sequences from the engine's tests against a Python transcription of the phase-1 guards, and rejects a seeded out-of-order ledger | Test failure in CI | `test_engine_conforms_to_lifecycle_model` (phase 1) |
| State explosion makes CI slow | Bounds | mitigate + accept | Three configurations; symmetry; the second pass and `bench grade` kept out of the 3-cell run; CI runs `--quick` on each push and the US-44 bounds nightly | Script timing lines, flushed per line | Measured: `--quick` ≈ 3 min; US-44 bounds 5 min 37 s |
| Bounds too small to show a real defect | Finite bounds | accept | Safety at the US-44 bounds (3 cells, parallelism 2, 1 crash). Two crashes are not checked to completion. Two passes and `bench grade` are checked at 2 cells; liveness at 1 cell. Residual risk stated. | — | — |
| The tla2tools download is tampered with | Fetched dependency | prevent | sha256 pin; a mismatch deletes the file and fails | Script exit | `test_corrupted_tla_jar_is_deleted_and_refused` |
| The TLC result is misread (exit 0 on violation) | Tool output | prevent | The script asserts on TLC's text ("Invariant X is violated") and on `violated` / `Error:` absence, not on the exit code alone | — | Every variant run exercises it |

## Adversarial analysis (STRIDE-lite)

| Trust boundary | STRIDE threat | Disposition | Control / rationale | Negative test |
| --- | --- | --- | --- | --- |
| The tla2tools.jar download | T: a substituted jar changes check results or runs code in CI | mitigate | Pinned release URL + sha256; delete on mismatch | `test_corrupted_tla_jar_is_deleted_and_refused` |
| CI runner executing the jar | E: third-party code in CI | accept (ADR-0012) | Upstream TLA+ tools, pinned by hash; CI job permissions `contents: read` | — |

## Privacy analysis (LINDDUN-lite)

This component touches no personal data. Checked: the model, its configurations and the check script process only abstract model values; no run data or transcript is read.

## Telemetry

The check script prints one line per run: result, label, distinct states, seconds. CI keeps the log. The line is load-bearing (O12): CI fails on any `FAIL` line through the exit code. There are no runtime spans; this is a build-time control.

## Test plan (Testing Strategy)

| Trigger | Directive | Here |
| --- | --- | --- |
| — | D0 hygiene | Always: no dead code; the script is lint-clean. |
| T1 | D1 (the model's mutation analogue) | The 21 seeded variants, each rejected by its named target checked alone; the forward and reverse variant-coverage tests. |
| T2 | D2 | TLC explores every interleaving within the bounds (exhaustive, stronger than properties sampled at random); the witness proves the explored space reaches a finished run. |
| T3 | D3 | Trace-replay conformance: the engine's recorded event sequences replay against the phase-1 guards, and a seeded out-of-order ledger is rejected. |
| T8 | D7 | Not applicable: no mocks. |

**CI:** the `models` job in `.github/workflows/ci.yml` runs `actions/setup-java` (Temurin 21), then `python3 tools/check_models.py --quick` on every push (liveness, grading, small-bounds safety, witness, every variant), and `python3 tools/check_models.py` nightly (adds the US-44 bounds). The US-44-bounds run also runs locally before any engine change that touches a transition.

## Conformance notes

- **LOA:** the model is the evidence for P8 (idempotency at side-effect boundaries) and C6 (idempotency keys), and for ADR-0011's C6 and C10 rows.
- **Deviation:** none.

## Confidence ledger

| Claim | Evidence | Label |
| --- | --- | --- |
| TLC v1.7.4 runs on JDK 21 on the workstation | Ran this session | Verified |
| Liveness (5 properties) holds at 1 cell / 1 crash | `check_models.py --quick`: 57,344 distinct states, 5 s | Verified |
| Grading invariants hold at 2 cells / 1 crash / 2 passes, engine and `bench grade` | `check_models.py --quick`: 16,325,776 distinct states, 63 s | Verified |
| All 16 invariants hold at small bounds with `bench grade` contending | `check_models.py`: 4,503,440 distinct states, 12 s | Verified |
| All 16 invariants hold at the US-44 bounds (3 cells, parallelism 2, 1 crash, engine grading), with symmetry | TLC: 386,254,609 states generated, 77,212,448 distinct, depth 49, 5 min 37 s, "No error has been found"; the same 77,212,448 states (242 s) after the coordinator was removed | Verified |
| Every cell can finish graded and deleted | Witness `NotAllCellsFinished` violated as expected | Verified |
| Every seeded variant is rejected by its own target, checked alone | `check_models.py`: 21 of 21 `ok` | Verified |
| Safety at 2 crashes, 3 cells | Stopped after 8 min at 170,716,518 distinct states, queue still growing | Not verified (residual) |
| A new invariant pre-empted two older variants' targets | Both still printed "violated", but by `NoOutcomeWhileRunning`; fixed by checking each target alone | Verified (MOD-A) |
| Guards on history hid `relaunch_prompted` twice; overlapping guards hid a seeded defect three times | Variant runs reported `NOT rejected`; each fixed and re-run | Verified |

## Flagged risks & residual unknowns

- The model abstracts the operating system as always answering (spawn, `TerminateJobObject`, job queries). Failures there are handled by the engine's failure taxonomy (ADR-0007), not by the model.
- A defect that needs 2 crashes at 3 cells, more than 3 cells, or `bench grade` or 2 grading passes together with 3 cells, is outside the checked bounds. US-44 requires 1 crash; the 2-crash run is on demand (`--deep`) and has not completed.
- Liveness is checked at 1 cell. A liveness defect that needs two cells contending for a slot is outside the bounds.
- The first CI run will confirm the Java setup on the hosted runner (Inferred until then).

## Status & next action

See `docs/design/phase1-walking-skeleton.md` (the rest of phase 1).

## Gate record

Recorded with the phase-1 walking-skeleton design's gate (one council for both): `docs/design/phase1-walking-skeleton.md`, "Gate record". It passed with conditions at round 3 on 2026-09-23, and every hard veto was cleared by its lens, none by the author. The model changes from the gate were:
- `Graders`;
- the engine's grading rule;
- `NoOutcomeWhileRunning`, `PromptedCellsEnd` and `ArchivedCellsGetGraded`, with their variants;
- variants checked against their target alone;
- the 3-cell run at the US-44 bounds.

---
**Handoff:** → `/implement` (the CI job; the engine conformance test lands with the engine).
