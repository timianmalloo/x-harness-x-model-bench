---
id: run-report-e2e4
title: "Run report - Evaluation Campaign E2-E4 (Leader epoch 18), draft for the Leader's review"
type: doc
status: draft
owner: "@timianmalloo"
tags: [coordination, run-report, evaluation-campaign, e2, e3, e4]
links:
  - { to: coordination-e2e4, rel: relates-to }
  - { to: coordinator-log, rel: relates-to }
  - { to: coordinator-log-c52, rel: relates-to }
  - { to: coordinator-log-c53, rel: relates-to }
  - { to: defect-classes, rel: relates-to }
  - { to: rulings-register, rel: relates-to }
  - { to: proof-eval-campaign-convergence, rel: relates-to }
review-by: "2026-10-21"
summary: >-
  The E2-E4 run from measured sources only (the audit log, the join entries, the Leader's run notes, the Coordinator
  logs). Every track joined; the ten final records are ready; P1-P4 are pushed and P5 is pending. Measured: 35.8 h from
  the plan's join to the last join, against 15-20 h Inferred; 3 of 19 external turns ended with no follow-on; 34 requests,
  all resolved; Rulings 107-113; 41 defect classes registered. The per-join recount fell from 25.0-38.2 min
  single-process to 9.4-16.2 min at -n 4, with FLAKE-A and MPATCH-A reds. Open: P5, Ruling 112 dormant, the walk flake's
  cause, the --dist loadscope proposal, macOS. The t1regress declaration was settled by the operator on 2026-10-07
  (accept as declared; c53).
---

# Run report: E2-E4 (Leader `leader-e1e4`, epoch 18)

**Status: draft for the Leader's review** (Coordinator #52, 2026-10-07). The per-track planned-vs-actual table is in the plan, `docs/coordination/coordination-e2e4.md`, section *Planned vs actual (Stage 7)*. It is not repeated here.

**Sources.** Every figure names its source, or says "not recorded". No figure is an estimate.

- **A**: `docs/audit/audit-log.jsonl`.
- **J**: a join entry's `recount_seconds`. This is the final, green recount only.
- **N**: the Leader's run notes (`e2e4-run-notes.md` in the session scratchpad), cited by the clock label on the line. Those labels mix time zones, so no wall clock is computed from them.
- **C**: `docs/coordination/coordinator-log/c<n>.md`.

Tokens and tool calls are **not recorded** for the tracks, except J1a (80 of 320 calls) and J1c (48 of 320) (A).

## Headline

| figure | value | source |
| --- | --- | --- |
| tracks joined | all 16 plan rows except X-PACK phase 2 (it joins in P5); plus 9 unplanned tracks (one, X-START, was withdrawn by Ruling 113) | J; plan section |
| ten final records | all ready; Ruling 113 condition 3: 0 start-bound ends in 517 host starts, maximum `start_ms` 264 | C51 |
| wall clock, plan join to last join | **35.8 h** (`join-c-w0` started `2026-10-05T15:07:51Z`; `join-x-cv` started `2026-10-07T02:41:05Z` and ran 743 s); the plan said 15-20 h (Inferred) | A |
| external turns | 19 (Codex 9, Agy 7, Grok 3); **3 ended complete with no follow-on** (LGa, LGb, G3 r2) | N |
| requests | 34 raised (27 seams to the Coordinator, 7 DRs to the Owner); **34 resolved**, 7 of them late by Coordinator #52 | `coord request list --status all`; `c52.md` |
| rulings | 107-113 (7) | `docs/notes/rulings.md` |
| defect classes registered | 41 (list below) | `docs/lessons/defect-classes.md` |
| Coordinator sessions | #29-#52 (24) | C |

## Tracks: the harness and model planned vs the one that ran

Served ids, as read back: Codex `gpt-6.1-sol` (from the Codex rollout record; `config.toml` says `gpt-6-sol`, N "14:40"), Agy `gemini-3.8-flash-high`, Grok `grok-4.7-build` (G3 r2), Sonnet `claude-sonnet-5-5`, Opus `claude-opus-5-5`, Owner `claude-fable-5-1`.

| reason the harness changed | tracks | source |
| --- | --- | --- |
| **RUN-IDENTITY / IDN-A**: a new run identity at prepare, or a same-id retry refused | J1a: new identity `x-j1a2`. K2a: RUN-STARTED, then Sonnet. K1d parts 2-3: Sonnet. K2b parts 2-3: Sonnet | N "08:13", "10:07", "16:15", "02:35" |
| **Context splits** (by plan, or by the compile's split rule) | J1d (107k), J1e (128k), K1b, K1c (K6 to Sonnet), K1d part 1 (151,818), K2b part 1 (159,037 > floor 39,611 + 60k) | N |
| **CEIL-A**: a ceiling passed, or a threshold set below the measured floor | J1c (input 230k > 200k); X-RS (reading phase 124,265 > 100k); X-TE9 (95,651 > 60k). Measured fresh-session floor: about 68k for Sonnet (N "09:35": 67,948) | N; C37, C46 |
| **Deadline** (3,300 s) | A3a, A3b, J2b (Agy), K1a (Codex) | N |
| **RUN-B**: a false RUN-LEADER | LGc (Agy), cancelled at 1,298 s | N "14:03" |
| **SERVE-A** / **XPORT-A** | G3 attempt 1 (served `grok-4.6`); K2a (`initialize`) | N "10:36", "10:07" |
| **Ruling 108** (the Agy revisit trigger) | A3c moved to Sonnet; LGc stayed on Agy | `rulings.md` R-108 |
| **FALLBACK-A** | K1a's Codex worker launched Claude Code Sonnet sessions itself (fan-out cap 0 broken) | N "03:40"; C41, C42 |

## Pushes

| batch | range | when (N label) | note |
| --- | --- | --- | --- |
| P1 + P2 (one push) | `37ec0585..95130d8f` | "00:23" | the gate ring ran twice: the first run (79 min) refused to stamp (PROBE-A); the re-run passed with `HB_GATE_RUNS` pinned, stamp `f5f5c7a7` |
| P3 | `95130d8f..d6e9a87d` | "04:20" | no ring |
| P4 | `d6e9a87d..d96220c0` | "01:00" | ring 84 min, stamp `a362a326`; the push was **denied twice by the auto-mode classifier** and then pushed by the operator with a `!` command |
| P5 | pending | - | the batch started on `b4e19e28` (N "05:55"); X-PACK phase 2, c51, c52 and the ledger join after it |

## The recount timing change (`-n 4`)

The operator approved the `-n 4` per-join recount for measurement (decision 4, about 07:45 on 2026-10-06). It applied from `join-x-k1c`; `join-x-retier` still read the old `join.json` (N "12:25").

| mode | joins | `recount_seconds` (final green recount) | total | source |
| --- | --- | --- | --- | --- |
| single-process | 27 (`join-x-i5` .. `join-x-retier`) | 1,501-2,295 s (**25.0-38.2 min**), median 1,772 s (29.5 min) | 48,083 s (13.36 h) | J |
| `-n 4` | 11 (`join-x-k1c` .. `join-x-cv`) | 563-972 s (**9.4-16.2 min**), median 758 s (12.6 min) | 8,565 s (2.38 h) | J |

*Erratum to the brief's figure:* the brief said "25-32 min serial". The measured single-process range reaches 38.2 min (`join-x-rdy-2`, 2,295 s; its pytest time was 1,911.71 s, N "09:06"). Without `join-x-rdy-2` and `join-x-retier` the maximum is 34.4 min (`join-x-g3`, 2,065 s).

**The reds `-n 4` brought** (each cost one more recount that is **not** in `recount_seconds`):

- **FLAKE-A under load:**
  - `join-x-k1c`: WinError 32 in `atomic.make_writable` (N "13:55");
  - `join-x-rs`: the four E1 walk tests, then WinError 32 again (N "22:00", "22:25");
  - batch P4: a false mutation survivor that did not reproduce 2 of 2 (N "18:35", "18:55").
  - Coordinator #48 named three mechanisms (c48): WIN-A's delete shape (measured), TIME-B's start bound (Inferred, later not supported by X-START's spike) and a load-caused setup ERROR. X-FLAKE landed the `make_writable` backoff (F1), the walk diagnostic (F2) and the survivor label (F3).
- **MPATCH-A:** `join-x-alarmfix`'s first recount went red on `test_property_loopback`'s order test. `monkeypatch.delitem` re-inserts the key at the end, and only a shared `-n 4` worker exposes the reorder. It reproduced deterministically in one process, and the Leader fixed the test (N "05:00").

## Defect classes registered this run (41)

One line each, in register order. The register is `docs/lessons/defect-classes.md`.

- **c29**
  - REG-C: a register-class merge driver on a non-JSONL file commits conflict markers with exit 0.
  - ATTR-A: `coord install` never removes stale merge attributes.
  - PRIM-A: a seat writes into the primary checkout.
  - CONF-A: a bare `from conftest import` resolves to another directory's conftest.
  - EOL-A: a Python text-mode edit on Windows rewrites an LF file as CRLF.
  - MEAS-B: a check that records only the first hit makes keep-or-drop decisions undecidable.
- **c32**
  - PIN-B: a test pins another task's version hash.
  - IDN-A: the run identity changed at prepare without a recompile.
  - LOCK-A: a long join holds the suite lock during a worker's gate window.
- **c33**
  - FPR-A: a run's fingerprint is read in another environment than the run's.
- **c35**
  - CANON-A: a design specifies a field type the ledger's canonical form refuses.
- **c36**
  - FLAKE-A: a test that fails under load and passes alone is written off without a measured repro.
  - ROUTE-A: a routing rule keyed on the harness alone.
- **c37**
  - CEIL-A: a worker passes its context ceiling and detects it late.
- **c38**
  - QUOTE-A: a design's table of sanctioned readers is cited by section, not quoted.
  - CACHE-B: an unidentified sweep empties a shared ring cache.
  - PATH-B: a long scratch path breaks git on Windows.
- **c39**
  - REL-A: a test spells a release-coupled label.
  - PROBE-A: a gate-input probe that degrades to skip.
  - OPER-A: an item that needs the operator's resources is reported "not run" from turn to turn.
- **c40**
  - SHAPE-A: a readiness or discrimination rule written for the check-based shape misjudges the check-less shape.
- **c41/c42**
  - FALLBACK-A: the Leader-only fallback is rendered into the worker's brief, and the worker executes it.
  - EVID-A: a grader writes its evidence but drops the pointer.
- **c44**
  - SPIKE-B: an operator-run spike depends on a host property it never reads.
- **Leader**
  - VERB-A: a restatement labelled as the operator's verbatim words.
  - TMPENV-A: a test assumes where `tmp_path` lives.
- **c45**
  - FIXT-C: a crash-window fixture that cannot reach its row's state.
  - INJ-A: a test sets a parameter on an in-memory copy that the code re-reads from disk.
  - ORD-A: segments ordered by file name, not by ordinal.
  - MARK-B: one strict-xfail marker spans every parameter.
- **c46**
  - CONSUME-A: reported ready because the producer's gate passed, while the consumer refuses it.
  - IDEM-A: an idempotency key bound to a mutable container.
  - HOOK-A: a commit command that silently bypasses the hook floor.
- **c47**
  - ERRATA-A: an erratum edits a registered meaning cell.
  - SIM-C: two row-by-row simplifications compound, so a proof loses its control.
  - APPLY-A: a validator and its applier decode one input differently.
- **c49**
  - ID-A: a new identifier allocated without reading its register.
- **c50**
  - RECID-A: a `src/`-changing join sequenced after the identity-keyed records it makes stale.
- **Leader**
  - MPATCH-A: `monkeypatch.delitem` reorders a module dict for later tests.
- **c51**
  - DIAG-A: a runtime failure attributed to a cause with no record of the failing instance.
- **c52**
  - DEV-A: a repo-local edit to a pack-managed file has no deviation note, so it surfaces only as an update conflict (the RUN-B leader-check retry, retired upstream at rev 99).

## Rulings 107-113 (Owner `owner-fable`, `claude-fable-5-1`)

| ruling | question | outcome |
| --- | --- | --- |
| 107 | DR-15: `cell.turn_ended` duration, given that the canonical form has no floats | (a) granted: `turn_ms`, an int in ms |
| 108 | DR-16: the Agy revisit trigger fired | (b) granted, bounded: LGc stays on Agy; A3c goes to Claude Code Sonnet; every external closing entry carries start, end, served id and tokens or "not recorded" |
| 109 | DR-1: hidden-tests assertion (1) on check-less variants | (A) granted, bounded by (1') |
| 110 | the five W1-K classifier mutants | (b) kept in `resume.json` |
| 111 | RS2's batch id on a grown batch | (b) the batch is frozen at first send |
| 112 | the probe host's start bound under load | (B) granted, bounded by a measured load reading; **now dormant** (R-113) |
| 113 | DR-START-1, after X-START's spike | (a) X-START withdrawn; R-112 dormant; condition 3 is a join-time watcher on the records' `hosts.jsonl` |

## Open items carried forward

1. **P5**: the batch, the push, then X-PACK phase 2, c51, c52 and the ledger. This report is a draft until then.
2. **Ruling 112 is dormant.** The trigger to re-open it is a reference start-bound end on a gate host (R-113). The watcher is R-113 condition 3; its read at the X-CV join was 0 of 517 (c51).
3. **The walk flake's cause is open** (TIME-B's 2026-10-06 instance is dormant by R-113; DIAG-A). X-FLAKE F2's assertion diagnostic records the next instance.
4. **The `--dist loadscope` proposal** (c48) is waiting for the operator.
5. **The alarm-task fix has landed:** X-ALARMFIX `ee1b0e11`, joined in `join-x-alarmfix` (J 775).
6. **macOS is deferred** by the operator (the plan's Not in scope).
7. Also open in the register: the FLAKE-A load-repro tool; CACHE-B's sweeper (unidentified); R-109's optional per-variant `reds` key; S-J4 (waived by the operator, OPER-A); the DEV-A sweep after P5.

**2026-10-07 (Coordinator #53): the `t1regress` declaration (RW1, RW2) is settled and leaves this list.** The operator answered "A" (accept as declared) to the Leader's question "RW t1regress: is the variant valid as declared?". The final records show `t1regress` `hidden_tests_pass` 0, `pass_at_1` 0, `turn1_tests_pass` 1, clause `turn1`, as declared. Errata: Ruling 109 condition 4 (`docs/notes/rulings.md`) and W1-L section 6.2 (`docs/design/eval-property-tasks.md`). No code change, no re-record; RW1 and RW2 stay ready. The decision is in the plan's *Operator decisions, 2026-10-07* and `c53.md`.
