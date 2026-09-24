---
id: "mutation-record-t2"
title: "Mutation record - track T2 (ledger, views, grade)"
type: decision-note
status: proposed
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [mutation, cosmic-ray, T2, ledger, views, grade]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  cosmic-ray 8.7.0 over ledger.py, views.py and grade/**, run natively on Windows at the track's final src: 1803
  mutants, 1546 killed, 257 survived, 0 timeout, 0 incompetent, 0 not-exercised-on-platform. Every survivor is an
  equivalent mutant with its diff and a one-line argument: 225 inside type annotations, 32 argued one by one.
---

# Mutation record: track T2 (ledger, views, grade)

**Result:** 1803 mutants. 1546 killed and 257 survived. Every survivor is dispositioned as an equivalent mutant below: 225 are annotation mutants and 32 have an individual argument. Nothing is open: no timeout, no incompetent mutant, and no mutant is not-exercised-on-platform.

## What ran, and where

| item | value |
| --- | --- |
| tool | `cosmic-ray` 8.7.0, via `uv run --with cosmic-ray==8.7.0` |
| platform | Windows 11, CPython 3.14.6, run natively. mutmut refuses native Windows (probe R13). |
| modules | `src/harness_bench/ledger.py`, `src/harness_bench/views.py`, `src/harness_bench/grade/` (every module) |
| `src` SHA | **`2263575`**. `git diff --quiet 2263575 9646248 -- src` exits 0, so this is also the `src` at the track's final test commit `9646248`. `ledger.py` and `views.py` are byte-identical from `512c6a7` onwards. |
| final test SHA | `9646248`: every surviving mutant was re-run against this commit's tests |
| config | `timeout = 180.0`; local distributor; `test-command = <shard>/.venv/Scripts/python.exe -m pytest -x -q -p no:cacheprovider <tests>` |
| tests per module | ledger: `test_ledger`, `test_verify`. views: `test_views`, `test_verify`, `test_grade`. grade: `test_grade`, `test_verify`, `test_views`, `test_cli`, `test_report`. Survivors were re-run with those plus `test_status` and `test_engine`. |

**Execution.** The run used 12 detached worktrees under `C:/Projects/bench-test/cr-t2-*`, each with its own venv and session. Each shard kept `job_index % n == k` of its module's mutants and marked the rest skipped in its own session. The shards ran in parallel, and cosmic-ray mutates files in place, one tree per shard. After every phase, `git status -- src` was clean in each shard. The shards were removed afterwards.

**Phases.**
1. Every mutant at `512c6a7`.
2. Survivors re-run at `4c8e9d9`, after survivor tests were added.
3. `grade/**` re-initialised and run in full at `2263575`, because the seam fix T2-12 changed `runner.py`. `ledger` and `views` survivors were re-run.
4. The remaining survivors re-run at `9646248`.

A mutant killed in an earlier phase stays killed: later commits only add or strengthen tests. The one test rewritten, T2-10, now asserts more.

**Two harness defects met and fixed along the way, not in this record's counts:**
- A relative interpreter path in `test-command` made `CreateProcess` fail. Every mutant came back INCOMPETENT. Fix: an absolute path per shard.
- cosmic-ray decodes pytest's stdout as UTF-8 while the cp1252 console wrote `é`. Six ledger mutants came back INCOMPETENT with `UnicodeDecodeError`. Fix: `PYTHONUTF8=1`. They were re-run and killed.

## Per module (final)

| module | mutants | killed | survived (all equivalent) |
| --- | --- | --- | --- |
| `grade/__init__.py` | 2 | 2 | 0 |
| `grade/correctness.py` | 140 | 132 | 8 (6 annotation, 2 argued) |
| `grade/cost.py` | 111 | 75 | 36 (36 annotation) |
| `grade/runner.py` | 390 | 330 | 60 (51 annotation, 9 argued) |
| `ledger.py` | 379 | 376 | 3 (3 argued) |
| `views.py` | 781 | 631 | 150 (132 annotation, 18 argued) |
| **total** | **1803** | **1546** | **257** |

Tests written to kill survivors are listed in `docs/proof/findings-T2.md` (T2-11). They are commits `ff27e06`, `4c8e9d9`, `2263575` and `9646248`.

## Equivalent mutants: inside a type annotation (225)

**Argument:** every module in scope starts with `from __future__ import annotations`, so an annotation is stored as a string and never evaluated at runtime. `views.turn_usage` reads `dataclasses.fields(...).name` only, never `.type`.

A mutation there (`list[dict] | None` → `list[dict] & None`, and so on) cannot change behaviour. The classifier (`ast`: `arg.annotation`, `FunctionDef.returns`, `AnnAssign.annotation`) placed each of these mutants inside an annotation span.

Count per annotated line:

- `grade/correctness.py`: 38 (×6)
- `grade/cost.py`: 19 (×13), 24 (×23)
- `grade/runner.py`: 122 (×22), 162 (×29)
- `views.py`: 118 (×12), 153 (×29), 164 (×10), 205 (×13), 228 (×35), 243 (×13), 278 (×9), 288 (×5), 292 (×6)

## Equivalent mutants: argued one by one (32)

The **mutated line** column is the mutant's diff: the original line is at the location given, and this is its replacement. Duplicate rows are distinct cosmic-ray occurrences of the same operator at the same position.

| # | at | operator | mutated line | argument |
| --- | --- | --- | --- | --- |
| E1 | `grade/correctness.py:80:13` | ReplaceComparisonOperator_Eq_LtE | `if total <= 0:` | `total` is parsed from `\d+`, never negative, so `<= 0` is `== 0`. |
| E2 | `grade/correctness.py:80:13` | ReplaceComparisonOperator_Eq_LtE | `if total <= 0:` | as E1. |
| E3 | `grade/runner.py:92:75` | ReplaceComparisonOperator_Eq_GtE | `named = {… for e in events if e["kind"] >= "segment.abandoned"}` | No other kind in `events` sorts at or after `segment.abandoned`. The kinds are `attempt.*`, `cell.*`, `run.*` (`engine.ENGINE_TRANSITIONS`), `grading.*`, `ledger.tail_repaired` and `segment.abandoned` itself. |
| E4 | `grade/runner.py:113:84` | ReplaceComparisonOperator_NotEq_Gt | `heads = {… for fact in PASS_FACTS if fact > "events"}` | `PASS_FACTS` is the fixed tuple (events, model_calls, tool_calls, scores), and every other fact sorts after `events`. |
| E5 | `grade/runner.py:113:84` | ReplaceComparisonOperator_NotEq_Gt | as E4 | as E4. |
| E6 | `grade/runner.py:113:84` | ReplaceComparisonOperator_NotEq_IsNot | `heads = {… if fact is not "events"}` | `"events"` is an interned identifier literal in both places, so `is not` is `!=` here. |
| E7 | `grade/runner.py:113:84` | ReplaceComparisonOperator_NotEq_IsNot | as E6 | as E6. |
| E8 | `grade/runner.py:126:55` | NumberReplacer | `ex = profiles.READERS[cell["harness"]](records[ -1])` | Guarded by `if len(records) != 1: return` two lines above, so `records[-1]` is `records[0]`. `test_two_native_records_for_one_session_are_na` kills the guard's own mutants. |
| E9 | `grade/runner.py:126:55` | NumberReplacer | as E8 | as E8. |
| E10 | `grade/runner.py:154:20` | ReplaceComparisonOperator_Eq_GtE | `elif source >= "native_record" and ex.missing:` | `usage_source` is validated against `profiles.USAGE_SOURCES = ("acp_turn", "native_record")`, and only `native_record` sorts at or after itself. |
| E11 | `grade/runner.py:159:98` | NumberReplacer | `cost.cost_usd(totals, self.prices, self.plan["created_at"][: 11])` | `created_at[:11]` is `YYYY-MM-DDT`. A `YYYY-MM-DD` effective date sorts at or before it exactly when it sorts at or before `created_at[:10]`. |
| E12 | `ledger.py:115:51` | ReplaceComparisonOperator_Eq_Is | `last = index == len(complete) - 1 and tail is b""` | `b""` is a singleton in CPython, so `tail is b""` is `tail == b""`. |
| E13 | `ledger.py:115:21` | ReplaceComparisonOperator_Eq_GtE | `last = index >= len(complete) - 1 and tail == b""` | `index` ranges over `enumerate(complete)`, so it never exceeds `len(complete) - 1`. |
| E14 | `ledger.py:115:51` | ReplaceComparisonOperator_Eq_Is | as E12 | as E12. |
| E15 | `views.py:54:74` | ReplaceComparisonOperator_Eq_LtE | `row = next((r for r in … if r["kind"] <= "grading.completed"), None)` | A pass's events segment holds `segment.abandoned`, `grading.started` and `grading.completed`. Grade writers are only created, never reopened, so it never holds `ledger.tail_repaired`. Of these kinds, only `grading.completed` sorts at or before `grading.completed`. |
| E16 | `views.py:149:95` | ReplaceTrueWithFalse | `dict(zip(key, k, strict=False))` | `k = tuple(r.get(f) for f in key)`, so both have the same length by construction. |
| E17 | `views.py:174:31` | ReplaceBinaryOperator_Mul_Div | `def busy_ms(calls: list[dict], /, positive: bool = False, …)` | The mutant only makes `positive` and `missing` positional-or-keyword. Every caller passes them by keyword. |
| E18 | `views.py:174:31` | ReplaceBinaryOperator_Mul_Div | as E17 | as E17. |
| E19 | `views.py:181:76` | ReplaceComparisonOperator_Eq_LtE | `… or end < start or (positive and end <= start) …` | `end < start` is already rejected by the term before it, so `positive and end <= start` adds nothing beyond `end == start`. |
| E20 | `views.py:181:76` | ReplaceComparisonOperator_Eq_LtE | as E19 | as E19. |
| E21 | `views.py:206:14` | ReplaceComparisonOperator_Eq_LtE | `if source <= "acp_turn":` | In the closed enum (`acp_turn`, `native_record`), only `acp_turn` sorts at or before `acp_turn`. |
| E22 | `views.py:258:22` | ReplaceComparisonOperator_Eq_LtE | `recorded = source <= "acp_turn" or calls is not None` | as E21. |
| E23 | `views.py:305:44` | ReplaceComparisonOperator_Eq_Is | `valid = [c for c in cells if c.validity is "valid"]` | `_validity` returns the literal `"valid"`, the same interned constant, so `is` is `==`. The other validity values are different strings. |
| E24 | `views.py:321:18` | NumberReplacer | `first = cells[ -1]` | A group is one (combo, pack). `config` refuses duplicate combo ids, and a combo names one harness and one model, so every cell in a group has the same combo, pack, harness and model. |
| E25 | `views.py:338:88` | ReplaceComparisonOperator_Gt_NotEq | `("=" if ranked.count(v) != 1 else "")` | `v` is in `ranked`, so `ranked.count(v) >= 1`, and `!= 1` is `> 1`. |
| E26 | `views.py:339:88` | NumberReplacer | `-(r.pass_at_1.value or -1)` | Rows are first split by `is None`, and a rate is at least 0. A rate of 0 maps to 1 instead of 0: still after every positive rate (each maps to `-v < 0`), and ties stay ties. |
| E27 | `views.py:381:12` | ReplaceContinueWithBreak | `break` | `engine-*` sorts before `grade-*`. Any other events segment is refused by `load()` (HB-LED-002), so `bench verify` exits 5 either way. |
| E28 | `views.py:440:19` | ReplaceComparisonOperator_Eq_Is | `if any(f.level is "error" for f in out):` | `Finding.level` is only ever the literal `"error"` or `"warning"` (interned constants), so `is` is `==`. |
| E29 | `views.py:440:19` | ReplaceComparisonOperator_Eq_LtE | `if any(f.level <= "error" for f in out):` | In (error, warning), only `error` sorts at or before `error`. |
| E30 | `views.py:440:19` | ReplaceComparisonOperator_Eq_Is | as E28 | as E28. |
| E31 | `views.py:443:19` | ReplaceComparisonOperator_Eq_Is | as E28, second check | as E28. |
| E32 | `views.py:443:19` | ReplaceComparisonOperator_Eq_Is | as E31 | as E28. |

## Residual

- **E12, E23 and E28–E32 rest on CPython interning.** They would become live on an implementation that does not intern those constants. The bench runs on CPython (measured here: 3.14.6). No other interpreter was tried.
- **E3, E10, E15, E21, E22 and E29 rest on closed sets:** event kinds, `USAGE_SOURCES` and finding levels. Adding a kind, a source or a level that sorts differently turns them into real mutants. Re-run cosmic-ray whenever one of those sets changes.
- **This record is current while `git diff 2263575 HEAD -- src/harness_bench/ledger.py src/harness_bench/views.py src/harness_bench/grade` is empty** (T7's check). A later change to those modules needs a re-run.
