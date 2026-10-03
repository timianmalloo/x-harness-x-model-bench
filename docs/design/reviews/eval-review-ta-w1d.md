---
id: review-eval-ta-w1d
title: "W1-D engine identity design review: Test Architect lens"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 gate reviews"
tags: [review, test-architect, evaluation-campaign, wave-1, w1-d]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Test Architect (Adversary Mode) review of W1-D against W0 rev 2 sections 6, 9, 10, 12 and R-87..R-93. The direction
  test has five red fixtures and the engine tests are well chosen. BLOCK on the launch recheck wiring (no test fails
  when cli.py stops passing the check) and on the G2 coverage half (no red fixtures, and the check is not specified
  to take a root). The telemetry reclassification section is provisional (Owner request pending).
---

# Test Architect review: W1-D `docs/design/eval-identity.md` (branch `design/eval-identity`, `71a15a0b`)

Session `rv-ta-bd-e1e4`, 2026-10-03. Checked against W0 rev 2 sections 6, 9, 10 (G2, G3), 12 and ADR-0017 section 7, plus code opened for this review: `engine.py:395-410, 534`, `cli.py:168`, `tests/test_architecture.py:44-52, 85-110, 220-240`, and a count of `src/harness_bench` on the design branch (69 files, 3 non-`.py`; the 28 run and 41 grade split holds). Verified = opened or run; Inferred = reasoned. **Section 4.2 and ruling 6 (`telemetry/*`) are provisional** while `req-01M41DJ56WN77QNKFCW34GMG3A` is open; finding 4 says what must hold either way.

## The points checked

| point | result |
| --- | --- |
| G2 file coverage has red fixtures | **No.** Tests run on the real tree; green on arrival: finding 2. |
| G2 import direction has red fixtures | Five fixtures (module level, lazy, relative, allowed pair, `cli.py` exempt). Two import forms and the stale allowlist case are missing: finding 3. |
| Launch recheck has a test that can fail | Engine tests exist with a fake check. **Nothing fails if `cli.py` never passes the real check**: finding 1. |
| `identity_check_ms` has a test that can fail | Named, but the assertion that would fail is not specified: finding 5. |
| HB-IDN-001 has a test that can fail | The stop test and `test_errors.py` row cover it. The stop-row assertions are loose: finding 6. |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 5, 9 (service row `cli.py` "one kwarg"), 12 | **The recheck is a control that cannot fail at its seam.** The engine takes an injected `identity_check`; `cli.py` must pass `identity.launch_check(root, plan)`. Every engine test uses a fake; `test_run_edit_stops_launch_grade_edit_does_not` calls `launch_check` without the engine. A `cli.py` that omits the kwarg (or passes it only for non-campaign plans) leaves every test green and the freeze unenforced, which is the exact failure ADR-0017 section 7 exists to prevent. The kwarg is also owned by X-C, not X-D. `EngineConfig(` is built at `cli.py:168` today with no such field. | blocking | `cli.py:168`; 5 "cli.py passes ..."; 12 engine rows | Add one end-to-end test (X-C/X-D joint, named in the design): a campaign plan built through the CLI path, a run-side file edited after plan, `bench run` stops with `HB-IDN-001` and no `cell.launch_intent`. Add the mutant "cli drops the kwarg" to `tests/mutations/cli.json` with that test named. | Verified |
| 2 | 8 G2 (a), 12 G2 rows | **The coverage half has no red fixtures.** `test_every_src_file_has_a_class` and `test_no_stale_class_entries` run on the real tree, where the design records 0 unclassed and 0 stale, so they are green on arrival and nothing shows they would catch a new file. The checker is not specified to take a root and a `CLASSES`/`PLANNED` pair, so a fixture cannot be built. Fixtures needed: a new `.py` file; a new non-`.py` file (`.json`, `.js`); a key neither on disk nor in `PLANNED`; a key on disk and also in `PLANNED`. Only `test_unclassified_file_refused` (HB-IDN-002, one non-`.py` case) fails on a synthetic input. | blocking | 8 "Red fixtures for (b)" (none for (a)); 12 G2 (a) row | Specify `unclassed(root, classes, planned)` and `stale(root, classes, planned)` as pure functions; four red fixtures on `tmp_path` trees; the real-tree test calls them with the real table. | Verified (design text) |
| 3 | 4.1, 8 G2 (b) | The direction test has five fixtures but not: `import harness_bench.grade.x as g`; `from harness_bench import grade` (W0 G3 lists these two plus the relative form as its red set); a stale `RUN_IMPORTS_GRADE_ALLOWED` pair (listed, no longer imported), which must fail or the allowlist only grows; an import under `if TYPE_CHECKING:` (the design says lazy imports count; state whether typing-only ones do). Fixtures must run against a synthetic `CLASSES`, not the real one, or the telemetry ruling changes what they prove. | major | 4.1, 8 | Add the three fixtures and the stale-pair case; take `classes` as a parameter. | Verified (design text) |
| 4 | 4.2, ruling 6 (provisional) | Whichever way the Owner rules, the direction test is the only thing that shows the table is consistent: telemetry `run` needs 0 new edges; telemetry `grade` needs the 6 run-to-grade edges listed. The design states 6 edges but no test pins the count or the three modules (`driver`, `engine`, `profiles`). If the ruling flips, the allowlist must change in the same commit. | minor | 4.2, 14 | After the ruling, add a test that the real-tree edge set equals the allowlist exactly (extra and stale both fail). That is finding 3's stale case on the real tree. | Inferred (ruling open) |
| 5 | 5 `identity_check_ms`; 12 `test_launch_intent_carries_identity_check_ms` | The check runs in the loop before `_launch`, and `cell.launch_intent` is appended inside `_launch` (`engine.py:534`). The design does not say how the measured value reaches that row. With a fake check, a mutant that records `0`, a constant, or the previous launch's value passes unless the test controls the clock. | major | `engine.py:403-405, 534`; 5 | Specify the hand-off (a field set by `_identity_ok`, read by `_launch`). The test injects a fake monotonic clock giving distinct durations per launch, asserts each intent row carries its own value, that the stop row carries the stopping check's value, and (with `test_non_campaign_run_has_no_check_and_no_field`) that the field is absent, never `0`. | Verified |
| 6 | 5, 12 `test_a_drifted_file_stops_launching_with_a_named_diff` | The assertion list is "running cells finish, no later intent, exit 3". It does not say the stop row's `code` equals `HB-IDN-001`, that `diff` equals the named strings, or that the code is in `RUN_CODES`; `_stop_launching` also gains `**fields` with no test that other stops (HB-RUN-004, circuit breaker) are unchanged. The raising-check path records a different `reason` with the same code; its test should assert both. | major | 5 pseudocode; 12 | Assert `code`, exact `diff` list and `reason` on the stop row for drift and for raise; add a regression check that the existing `_stop_launching` rows are unchanged. | Verified (design text) |
| 7 | 5 Budget | "p95 <= 250 ms warm ... a breach is a finding, not a gate." Nothing can fail on it. It has a measurement path (the E1 demo), which is acceptable if the demo output is a required exit item. | minor | 5 | State in the E1 exit evidence that median and max of `identity_check_ms` are reported; no test needed. | Inferred |
| 8 | 6, 12 last rows | `test_grading_started_records_the_grade_identity` (X-F) asserts the hash changes with a `grade/*.py` edit and not an `engine.py` edit. It does not assert absence on a non-campaign pass, which 6 requires. | minor | 6 "Only on a campaign run" | Add the negative case. | Verified (design text) |

## What holds up (no finding)

Class counts match the tree (69 files; top level 24, gateway 8 + 2 schemas, grade 14, report 10 + `report.js`, scripted_user 5, telemetry 5). The torn-read, unreadable-component, fail-closed and CRLF cases each have a node that fails on its mutant, and the mutation file names three. The leak test pins SEC F11 with sentinels. The two guard entries (`SUBPROCESS_CALLERS`, the R-60 case) carry fixtures that are red on arrival. The surface list (9) covers store through compute reader.

## Gate

`GATE W1-D · Test Architect · BLOCK · 8 findings (rv-ta-bd-e1e4, 2026-10-03)`

Clearing conditions: findings 1 and 2 (each a control with no failing case). Findings 3, 5 and 6 should be resolved in the same follow-up; 4 is re-checked after the Owner ruling; 7 and 8 may be recorded.

## Revision 2 re-review (2026-10-03)

Session `rv-ta-d2-e1e4`. Target: `docs/design/eval-identity.md` rev 2 on `design/eval-identity` (`7f04613b`). Opened for this review: the design, `tests/test_cli.py:247-277`, `src/harness_bench/cli.py:120-177`, `plan.py:369-376`. Floor (README 2a) checked per named test: assertion that fails today, red fixture, real wiring, adjacent-pair mutant, allowlist against the tree.

| round-1 finding | rev 2 | result |
| --- | --- | --- |
| 1 real wiring | T-25 real `cmd_run` + mutant on the kwarg line | **Open, see R2-1: the stated `assume:` is false** |
| 2 G2 coverage | pure `unclassed`/`stale` take the table; T-8, T-9, T-10 fixtures; T-10b real tree | Cleared. Each fixture is red against the skeleton stubs (`[]`). |
| 3 direction forms | 6 forms in T-12, T-12b allowed/exempt, T-12c stale pair, `classes` a parameter | Cleared |
| 4 edge set pinned | T-12d: edges equal the 3 `config.py` pairs; mutant `telemetry/*` as grade gives 6 extra | Cleared |
| 5 `identity_check_ms` | hand-off `self._check_ms`; T-30 fake clock 7/11/13; T-29 absent not 0; T-31 once per tick | Cleared |
| 6 stop-row assertions | T-26 exact row, T-28 reason, T-32 other stops unchanged | Cleared |
| 8 grade hash on non-campaign | X-F row asserts absence | Cleared |
| R-94 | T-3 (run class), T-4 (gateway grade), T-12d (3 pairs); each has a mutant swapping the class | Cleared |
| 2 s launch cap, once per tick | T-16 (fake clock jumps 3 s), T-31 (counting fake, p=3) | Cleared |

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| R2-1 | 12 T-25 | **The `assume:` is false.** The T9-2 fixture does not reach the engine: it replaces `engine.Engine` with `_FakeEngine` (`monkeypatch.setattr(engine, "Engine", _FakeEngine)`), writes `plan.json` as `{}`, and stubs `plan.load_confirmed`, `preflight.check`, `status.build`. A test built on it passes with the kwarg dropped, which is blocker 1 again. The design's fallback ("gains the missing launcher stub") understates the gap: the rebuilt fixture must keep the real `Engine`, write a real confirmed plan (campaign block set, `plan_hash` re-stamped, because `load_confirmed` rejects any edit, `plan.py:374`), carry at least one cell, and stub only `preflight.check`. The edited file must be a run-class `src/` file, not a task file: a changed task stops `cmd_run` itself with `HB-USR-002` (`cli.py:134-136`) before the engine, which would pass the mutant. | major (blocks the build of T-25, not the design) | `test_cli.py:247-277`; `cli.py:134-136, 168-172`; `plan.py:374` | Replace the `assume:` with: "the T9-2 fixture stubs `engine.Engine` and cannot be reused; T-25 builds its own: real confirmed plan with one cell and a campaign block, real `Engine`, only `preflight.check` stubbed, edit a run-class file". The stop row is read from the run's `events`, so the assertion is on the real engine's output. | Verified (opened) |
| R2-2 | 12 T-25 vs 5 | T-25 needs a no-drift twin: without it a plan that fails to reach launch for any other reason (bad fixture, preflight) also shows zero intents and a non-zero exit. | minor | T-25 asserts zero intents | Add the twin with one intent as the control; it also proves the fixture reaches the engine. | Inferred |

`GATE W1-D · Test Architect · PASS WITH CONDITIONS · 2 findings (rv-ta-d2-e1e4, 2026-10-03)`

Conditions: the R2-1 text is corrected before X-D builds T-25 (a design edit, no new test). R2-2 may be recorded. The hard veto is not exercised: every other correctness claim has a failing-today test and a mutant, and T-25 has a verification path once R2-1 is applied.
