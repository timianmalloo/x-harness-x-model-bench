---
id: brief-eval-x-d
title: "Brief X-D: engine identity, launch recheck, E1 registry rows (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-identity, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-D builds identity.py, the E1 errors.py rows, the guard entries and the engine launch recheck of W1-D rev 2 on Codex gpt-6.1-sol, in two dispatches, each red and green in one turn."
---

# X-D: engine identity and the launch recheck

**Harness** Codex via `coord-runner` (Leader, R-87), `gpt-6.1-sol`, effort high, codex-cli 0.160.0 (R-88 condition 1: Q0 qualified Codex before W1-D's gate; README §5) · **contract** `x-d.contract.json` (D1; D2 reuses it with the suffix `2`) · **deadline** 3,300 s per dispatch · **budget** 200 calls · 200k · 2 dispatches · 3 h · **fallback** a red-only end or a failed read-back: the green follow-on runs as Claude Sonnet (`model: sonnet`, served `claude-sonnet-5-5`) in the same worker tree (R-87 Option 1; R-88 is the Owner review).

**Design:** `docs/design/eval-identity.md` (W1-D rev 2, on `main`, `301a8705`), with ADR-0017 *Amendment 1* (R-94). **W0 rev 5** (rev 4 plus the rev-5 change table; your rows: §6 `for_task`, `builds=None`, the `profiles/<h>` set; §11 HB-RDY-011, HB-PLN-004 text). **W0 rev 4:** sections 6 (identity API, launch recheck, **the `campaign_check=` keyword**), 9, 10 (G2, G2b, G3, D3 as a two-path frozenset), 11 (every E1 row, **registry first**), 12, 13.

## Owned paths (E1 hub owner, W0 §13)
`src/harness_bench/identity.py` (new), `engine.py` (E1), `errors.py` (E1), `grade/runner.py` lines 108-112 only (`catalog_hash` becomes an import from `identity`), `tests/test_identity.py` (new), `tests/test_engine.py` (E1), `tests/test_architecture.py`, `tests/import_graph.py` (new), `tests/mutations/engine.json` (E1), `tests/mutations/cli.json` (the "cli drops the kwarg" mutant only).

## Dispatch D1 (`x-d1-e1e4`, `build/eval-x-d1`): the first commit every other track waits on
One turn: a red commit, then a green commit.
- `errors.py`: **every** E1 row of W0 §11 (HB-LED-007, HB-IDN-001/002, HB-PLN-001/002/004/005, HB-PWR-001, HB-CHK-001..004, HB-GRD-007, HB-RDY-001..011 (rev 5 adds HB-RDY-011, SR-E1 4), HB-CMP-001..010 with HB-CMP-010's rev 4 meaning; HB-PLN-004 with its rev 5 text, which also names a `synthetic` combo in a measurement plan). The registry rejects an unknown code (`errors.py:118`), so X-A1, X-B1, X-C, X-E, X-F and X-H1 test their codes only after this joins.
- `identity.CLASSES` seeded for every existing `src/` file (69 at W1-D's scan) and every planned module of W0 §9; `telemetry/*` run, `gateway` a grade component (R-94); G2 (`test_every_src_file_has_a_class`, with the `unclassed`/`stale` red fixtures T-8..T-10b) and G2b (direction test; `RUN_IMPORTS_GRADE_ALLOWED` holds exactly the three `config.py` pairs, T-12d).
- `tests/import_graph.py` extracted from `test_architecture.py:98-99`; G3 over the W0 §9 "yes" set with its three red fixtures; `SUBPROCESS_CALLERS = frozenset({"procs.py", "grade/bench_check.py"})` through the alias resolver; the R-60 set gains `grade/property`.
- `catalog_hash` moved to `identity.py`; `grade/runner.py:108-112` becomes the import (your only hunk in X-F's file).

## Dispatch D2 (`x-d2-e1e4`, `build/eval-x-d2`), after D1 joins
- **W0 rev 5 §6 (SR-E1 3):** `manifest(root, tasks, builds=None)` writes **no** `builds/*` key; `profiles/<h>` covers every `h` in `profiles.HARNESSES` (plan-independent); `for_task(m, task)` drops every `builds/*` key and every `tasks/<id>` except `tasks/<task>`. Test: `identity_hash(manifest(root, [t], builds=None)) == identity_hash(for_task(manifest(root, [t, u], builds=b), t))`, with the mutant "`for_task` keeps `builds/*`".
- `manifest`, `identity_hash`, `side`, `diff`, `launch_check` (W0 §6; `manifest` takes `plan["builds"]`, imports no `tools` module); R-94 pins T-3 (`telemetry/normalize.py` edit moves run side only) and T-4 (`test_gateway_is_a_grade_component`).
- `engine.py`: the recheck when a campaign run starts and before each `cell.launch_intent`; `run.launch_stopped{code: HB-IDN-001, reason, diff}`; `identity_check_ms` on the `cell.launch_intent` row via `self._check_ms`, absent (not 0) when no check ran.
- **`campaign_check: Callable[[], None] | None` (W0 rev 4 §6, RV-DS W1-C 2):** called once, after the run lock (`engine.py:374`) is held and before the first `cell.launch_intent`; a raise stops the run before any launch. Test with a fake callable. X-C writes the real function and the `cli.py` line.

## Acceptance items (design tests and live gate conditions)
1. **RV-TA W1-D rev 2, R2-1/R2-2:** T-25 builds its own fixture (a real confirmed plan with one cell and a campaign block, a real `Engine`, only `preflight.check` stubbed, a `src/` run-class file edited) and its no-drift twin T-25b; the mutant "cli drops the kwarg" in `tests/mutations/cli.json`.
2. **RV-TA 2, 3:** pure `unclassed`/`stale` take the table (T-8..T-10, T-10b); T-12 with six import forms, T-12c the stale pair, T-12d the edges equal the three pairs.
3. **RV-TA 5, 6; RV-SRE 1, 3, 4:** `identity_check_ms` via a fake clock (T-30), absent not 0 (T-29); the check once per tick with a 2 s cap (T-16, T-31); the stop row exact (T-26, T-28, T-32).
4. **RV-TA 7, RV-SRE 8 (E1 exit evidence, at the demo):** the demo reports median, max and the cold value of `identity_check_ms`.
5. `test_side_partitions_every_component`; the manifest carries no `os.environ` value and no path (RV-SEC 11).
6. The differ names `grade/formal.py changed` (plan exit evidence).

Not yours: `Status.stop_reason`/`stop_diff` (X-C, W0 rev 4 §6), `grading.started` fields (X-F).

## Exit
README §3 join gate per dispatch; served model read from the Codex native record. Report per README §4.
