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
- **This record is current while `git diff 2263575 HEAD -- src/harness_bench/ledger.py src/harness_bench/views.py src/harness_bench/grade` is empty** (T7's check). A later change to those modules needs a re-run. *Superseded by the addendum below.*

## Addendum: T11 (`views.verify`, 2026-09-24)

*Transcribed by the Coordinator from track T11's report.*

Track T11 changed `views.py` inside `verify` only. `git diff 2263575 HEAD -- src/harness_bench/views.py` is one hunk in `def verify`, +4/-1. `ledger.py` and `grade/**` are unchanged. So the record above stays current for them and for every other function in `views.py`.

| item | value |
| --- | --- |
| tool | cosmic-ray 8.7.0; `PYTHONUTF8=1`; an absolute interpreter path per shard |
| `src` SHA | `bdcd2ef`. Survivors were re-run at `98414f5`, and `git diff --quiet bdcd2ef 98414f5 -- src` exits 0 |
| scope | `verify` only, `views.py:427-466` by AST line range: 98 of 790 mutants. The rest were marked SKIPPED |
| tests | `test_views`, `test_verify`, `test_grade` (`-x -q -p no:cacheprovider`); the baseline passed 132 in every shard |
| execution | 4 detached worktrees `C:/Projects/bench-test/cr-t11-{0..3}`, in-scope mutants split `idx % 4`. `git status -- src` was clean in each after every phase, and the worktrees were removed |
| result | 98 mutants, 93 killed, 5 survived and all equivalent; 0 timeout, 0 incompetent, **0 open** |

Phase 1 at `bdcd2ef`: 90 killed, 8 survived. Three survivors were real gaps, and `98414f5` kills them:
- `views.py:446:19` Eq_GtE, two jobs: a warning returned before `load()` and the archive checks;
- `views.py:464:15` ExceptionReplacer: the first bad archive raised instead of being reported.

Both are also pinned in `tests/mutations/views.json`.

**Flag:** T2's record lists neither of those `verify` mutants as equivalent, so it counted them killed. Under these three test files they survived. The likely cause is T2's survivor re-run with extra test files; this is not verified. They are now killed by `test_verify.py` itself.

**Equivalent (T11):**

| id | location | operator | mutant | argument |
| --- | --- | --- | --- | --- |
| T11-E1 | `views.py:439:24` | Eq_Is | `if fact is "events" and report.sealed:` | `fact` comes only from the module constant `FACTS`. Its identifier-like literals are interned like `"events"`, so `is` is `==` |
| T11-E2 | `views.py:443:19` | Eq_Is | `if any(f.level is "error" for f in out):` | as E28: `level` is only the literal `"error"` or `"warning"`, checked by grepping every `Finding(` in `src` |
| T11-E3 | `views.py:443:19` | Eq_Is | as T11-E2 | as E28 (a second job, as E30) |
| T11-E4 | `views.py:446:19` | Eq_Is | as T11-E2, the second check | as E28 |
| T11-E5 | `views.py:446:19` | Eq_LtE | `if any(f.level <= "error" for f in out):` | as E29 |

T2's E28–E32 at `views.py:440/443` now sit at `443/446`, three lines lower.

**This record, with this addendum, is current while `git diff 98414f5 HEAD -- src/harness_bench/ledger.py src/harness_bench/views.py src/harness_bench/grade` is empty.** *Superseded by the T12 re-run below.*

## Re-run with bytecode off (T12, TOOL-A): this supersedes the counts above

*Run by track T12 and transcribed by the Coordinator. Setup as in `mutation-record-t1.md` (T12):*
- *cosmic-ray 8.7.0 with `PYTHONDONTWRITEBYTECODE=1`, in 16 shards;*
- *`src` at `ceed6c1`, each module run with its recorded command;*
- *survivors re-run with `mutate-and-test` at `a0c4f52`.*

*The Coordinator re-ran `ledger.py:115:21`, `ledger.py:225:30` and `views.py:365:18` with the named-test checker. All three survived at `ceed6c1` and were killed at `a0c4f52`.*

| module | mutants | killed | equivalent | open |
| --- | --- | --- | --- | --- |
| `ledger.py` | 379 | 375 (8 by new tests) | 4 | 0 |
| `views.py` | 790 | 630 (20 by new tests) | 160 (143 annotation, 17 argued) | 0 |
| `grade/**` | 643 | 535 (1 by a new test) | 108 (99 annotation, 9 argued) | 0 |

**Recorded killed, now survived** under each module's recorded command. Each is confirmed killed by `mutate-and-test` at `a0c4f52`, unless marked equivalent.
- **ledger (10):**
  - `115:21` Eq_Is and Eq_LtE;
  - `124:40` Add_BitOr and BitXor;
  - `129:44` Add_LShift;
  - `131:40` Add_BitOr and BitXor;
  - `225:30` Eq_Is;
  - **equivalent** `115:51` Eq_LtE: `tail <= b""` is `tail == b""`, because `b""` is the least bytes value;
  - **equivalent** `123:16` break → continue: `last` holds only on the final iteration and the loop has no `else`.
- **views (21 argued):**
  - `157:53`;
  - `185:36`: touching spans, where a split sum rounds 3330.5 ms differently;
  - `202:35`: the phase-1 timeout, `31e9 ** 1e9`;
  - `202:58`, `206:14`;
  - `249:73`, `249:104`, `254:64`;
  - `255:72` ×3;
  - `296:97`, `312:63`, `317:25`, `323:61`;
  - `339:88` (`or 1`);
  - `365:18`: `Finding` not frozen;
  - `412:12`, `418:41`, `439:24`;
  - **equivalent** `305:44` Eq_GtE: every other validity value sorts below "valid".
- **views annotations:** 143 survive, against 132 recorded. The extra 11 are equivalent.
- **grade (3 argued):**
  - `correctness.py:65:32`: only the exact `{python}` token is replaced;
  - **equivalent** `correctness.py:82:54` Eq_GtE: `passed = max(total - failed, 0) <= total`;
  - **equivalent** `runner.py:152:20` Eq_GtE: as E10, because `usage_source` is validated against `USAGE_SOURCES` at `profiles.py:103`.
- **grade annotations:** 99 survive, against 93 recorded. The extra 6 are equivalent.

The new tests are in `tests/test_ledger.py`, `tests/test_views.py`, `tests/test_verify.py` and `tests/test_grade.py` (commit `a0c4f52`).

**Corrections to this record:**
- **Duplicate rows.** E2, E5, E7, E9, E14, E18, E20 and T11-E3 repeat another row. At their `(file, line, column, operator)` there is only one job.
  - For E9, the other NumberReplacer job is `records[1]`, and it is killed.
  - E14 is most likely `ledger.py:115:21` Eq_Is, which is not equivalent past the small-int cache and is now killed (Inferred).
- **Annotation counts.** The per-line counts above cannot occur. Each `|` in an annotation yields 11 jobs, and all of them survive. The measured counts are:
  - `correctness.py:38` ×11;
  - `cost.py:19` ×11 and `:24` ×22;
  - `runner.py:122` ×22 and `:162` ×33;
  - `views.py` lines 118, 164, 205, 243, 278, 288 and 292: ×11 each;
  - `views.py` lines 153 and 228: ×33 each.
- **New mutants the record does not list:** none.

**Cause of the disagreements (Flagged: not verified).**
- **Not stale bytecode:** cosmic-ray 8.7.0 already sets `PYTHONDONTWRITEBYTECODE=1`.
- **Not the survivor re-run's extra test files.** With `test_status` and `test_engine` added at `ceed6c1`:
  - 32 of the 33 mutants that finished still survive;
  - `views.py:202:35` hangs.
- **Likely causes:**
  - killed counts derived by hand as total minus the listed survivors;
  - cosmic-ray reporting every timeout and every non-zero exit as KILLED (`testing.py:73-75`), so a hang or a collection error reads as a kill (class TOOL-B);
  - flaky kills.

**This record, with this re-run, is current while `git diff ceed6c1 HEAD -- src/harness_bench/ledger.py src/harness_bench/views.py src/harness_bench/grade` is empty.**
