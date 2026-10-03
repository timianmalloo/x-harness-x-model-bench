---
id: brief-eval-x-h1
title: "Brief X-H1: power, verdicts, dominance, ring gates (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-power-verdicts, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: adr-0020-power-and-verdicts-stdlib, rel: depends-on }
review-by: "2026-10-17"
summary: "X-H1 builds power.py, verdicts.py and gates.py of W1-H rev 2 (stdlib only, pure functions) under W0 rev 6 on Grok grok-4.7 high, in three turns: power, then verdicts and gates as two parallel turns, each red and green in one turn."
---

# X-H1: power, verdicts, gates

**Harness** Grok via `coord-runner` (Leader, R-87), `grok-4.7`, `--reasoning-effort high`, `XAI_API_KEY` removed · **contract** `x-h1.contract.json` (turn a; b and c reuse it with the suffix `b`, `c`) · **deadline** 2,400 s per turn (see below) · **dispatch** three turns, each red then green · **budget** 3 x 60 calls · 250k · 3 dispatches · 4 h · **fallback** a red-only end: the green follow-on runs as Claude Sonnet (`model: sonnet`, served `claude-sonnet-5-5`) in the same tree (R-92 is the Owner review).

**Why 2,400 s.** X-G1's catalog track (one small file) used all 1,200 s with red and green committed. These turns write 300 to 600 lines of source and 40 to 60 tests each, plus a by-hand mutant run. 1,200 s would end them red-only (Inferred from X-G1's wall time; not measured on this size).

**Design:** `docs/design/eval-power-verdicts.md` (W1-H rev 2, on `main`; sections 3, 5, 7, 11, 13 bind you). **W0 rev 6** wins over the design: §3 (the NA rule), §8 (whole), §9 (grade class), §11 (HB-PWR-001), §13. **ADR-0020 + Amendment 1.** **R-93, R-96** in `docs/notes/rulings.md`. **Reviews:** `docs/design/reviews/eval-review-{ta,pat,sim}-w1h.md` (no SEC or DS review of W1-H exists).

## Turns and owned paths
| turn | session · branch | files you own | joins before |
| --- | --- | --- | --- |
| **a power** | `x-h1a-e1e4` · `build/eval-x-h1a` | `src/harness_bench/power.py`, `tests/test_power.py`, `tests/mutations/power.json` | b and c start |
| **b verdicts** | `x-h1b-e1e4` · `build/eval-x-h1b` | `verdicts.py`, `tests/test_verdicts.py`, `tests/mutations/verdicts.json` | X-C, X-H2 |
| **c gates** | `x-h1c-e1e4` · `build/eval-x-h1c` | `gates.py`, `tests/test_gates.py`, `tests/mutations/gates.json` | X-C, X-E |

b and c are independent (disjoint files; b reads `power.level_for` from a, c reads nothing from a or b) and run in parallel, inside the cap of two Grok dispatches. **Not yours:** `report/*` (X-H2), `cli.py` (X-C), `readiness` (X-E), `registry`/`errors.py` rows (X-D1: `HB-PWR-001` must already be in the registry), `bench/metrics.yaml`, `tests/test_architecture.py`.

## Depends on
W1-H rev 2 gated and on `main` ✓; **X-D1 joined** (`HB-PWR-001` in `errors.py`, the grade-class rows for the three modules); **X-G1 joined** (catalog 0.7.dev); **X-A1a joined** (`plan.cell_arm`, W0 §5; see the contradiction note); **ADR-0020 Amendment 1 on `main`**. If any is missing, stop and report which (README §1 step 5).

## Rules for all three turns
- **Red protocol (design §11 intro, RV-TA 3).** Red commit 1: skeletons with the final signatures that return a value **outside the expected domain** (the design lists them: `level_for` returns `(Decimal(-1), "unimplemented")`, `analyse` rows with `n = -1`, `label_for` returns `None`, `statement_for` returns `"unimplemented"`, `verdict` returns the interval `(Decimal(1), Decimal(-1))`, `collect` returns `([], [("unimplemented", "")], {})`, `pilot` returns `[GateItem("unimplemented", "")]`, `admission` returns `{task: (-1, "unimplemented")}`). Red commit 2: the tests; each fails on an assertion about a value. Green commit: the implementation. Report SHA, node and failing assertion per red commit.
- **Pure stdlib.** `statistics.NormalDist`, `math`, `decimal`, `hashlib`, `random` via `stats.rng`. No I/O, no new dependency (ADR-0020 §5). Grade class (W0 §9): no run-class module may be imported by these files except as the direction rule allows.
- **Mutants** go in `tests/mutations/<module>.json` (repo find/replace format); each entry lists **parametrize node ids** (`test_label_for_boundary_table[L8]`), never a bare function. Run `python tools/mutate_check.py tests/mutations/<name>.json` by hand before the green commit; every mutant is killed, or a recorded reason per survivor. `tests/test_mutate_check.py` proves each `find` occurs once.
- **Python.** Use `python`/`uv run`, never `python3`. Windows paths.

## Turn a: power (`power.py`)
**Work:** `PAIRING`, `LEVEL_RULES`, `level_for`, `n_unpaired_exact`, `n_paired_exact`, `_snap`, `mde_for`, `analyse` (design §3.2, §5). `PowerResult` carries `alpha_per_test`, `level_rule`, `reachable_mde`; inputs add `slots` (required) and `planned_reps_per_task` (optional).

**Acceptance items**
1. Red first, per the protocol above.
2. 93 / 53 / 115 pinned **exactly** as integers, with the hand formula holding the literal z constants inside the test file, and the seeded-wrong one-sided variant that must fail beside the real run (design §11.1; ADR-0020 §6). `ceil` must not become `round` (114.2488 is the case).
3. **R-96 condition 1 and RV-PAT W1-H 1:** one `LEVEL_RULES` table keyed by method; `level_for` is its only reader; `holm` returns `alpha/m` and the sentence `"alpha/m (Bonferroni; Holm's first step)"` verbatim; `bonferroni` and `none` as in design §3.2. `test_level_rule_table`.
4. **R-96 condition 2, power side (RV-TA R-96 note):** `test_holm_is_sized_like_bonferroni` (holm, m 45, gives 115; `none` gives 53). The `holm` to `alpha` mutant is listed here and in turn b.
5. **RV-TA W1-H 8:** `_snap(x) = ceil(x - 1e-9)` is a one-line helper with `test_snap_at_the_integer_edge` (two edge inputs, two mutants).
6. **RV-SIM W1-H 7:** `sd` and `rep_spread` are validated (numbers >= 0) and not echoed; no `descriptive` field.
7. `HB-PWR-001` names the field for every guard in design F1 (alpha, power, mde, m, method, pairing, `psi < mde^2`, tasks, `slots` absent or 0, `planned_reps_per_task` 0, `sd`, `rep_spread`); one table row per guard (`test_power_inputs_each_invalid_field_is_named`).
8. `cells`/`hours`/`tokens` reference table (2,430 / 4,230 / 5,220; 44.02 / 76.63 / 94.57 h at 2 slots), `reachable_mde` (`mde_for(len(tasks) * planned_reps_per_task)`, `None` when absent), `assumed` labelling, `alpha`/`power` echoed exactly.
9. RV-TA W1-H 1 form for the mutant file: parametrize ids; mutants for `ceil`, `alpha/m`, `holm` mapping, `ceil(n/tasks)`, `_snap` epsilon, bisection bounds.

## Turn b: verdicts (`verdicts.py`)
**Work:** `alpha_per_test`, `resamples_for`, `seed_for`, `label_for`, `statement_for`, `VerdictSpec`, `collect`, `verdict`, `VerdictLabel`, `Pair`, `Ratio` (W0 §8; design §3.2, §5). The cell's arm is read with `plan.cell_arm(cell)` only.

**Acceptance items**
1. Red first, per the protocol.
2. **`label_for` rule table L1..L10 and `statement_for` table D1..D7** exactly as the design renumbers them after RV-TA 1 and RV-SIM 1, 2 (`and` to `or` is killed by L8 and L9; D7 carries `r` 0.9 and kills a `lo`-reading statement).
3. **RV-TA W1-H 2:** `test_normal_approximation_400_pairs` uses tolerance 0.005; `test_golden_interval_and_draws` is the second killer of the `B*alpha/2` mutant.
4. **`seed_for` is 60 bits** (`[:15]`): `test_seed_for_is_a_legal_params_seed` with the S2 row (`e1746a8b...effc` gives 878446374899272100, constructs `stats.Params`), the hypothesis range check, and one test per key field that changes the seed (W0 §8 rev 3; ADR-0020 Amendment 1).
5. **R-96 conditions 2 and 3, RV-PAT W1-H 2:** `test_holm_verdict_interval_equals_bonferroni` (same seed and pairs give equal `interval`, `level`, `alpha_per_test`; `method` echoes `"holm"`; `level_rule` differs; `none` is narrower). `alpha_per_test(prereg)` calls `power.level_for` and defines no second table (`test_level_rule_table`'s verdict leg).
6. **RV-PAT W1-H 5:** `VerdictSpec` refuses `min_pairs < 1` with HB-USR-002.
7. **RV-SIM W1-H 8:** E1 accepts `Decimal(0)` or `Decimal(1)` only (HB-USR-002 otherwise); `collect` has no `primary` parameter. Duplicate `(task, rep)` refused. Input order never changes a verdict, and the **label invariant** (RV-SIM 4: every `Verdict.label == label_for(...)`) sits inside that test.
8. **NA is never a dropped cell (W0 §3; RV-SIM W1-H 9 declined, guard kept):** every cell is a pair half or an `excluded` `(cell_id, reason)`; `2 * pairs + excluded == cells in scope` (hypothesis, on real `CellView`s); `na_counts` is derived in the one NA branch and `sum(na_counts.values())` equals the NA-branch entries; `test_check_tampered_is_listed_not_dropped`. **No NA count and no `level_rule` enters `label_for`.**
9. Empty stratum gives `inconclusive (not recorded)` with the reason `task <id>: 0 pairs recorded`; `n_pairs >= min_pairs` still holds. Ratio `None` (never 0) when a denominator is 0 or a token count is unrecorded; tokens via `views.sum_tokens`.
10. **Coverage (RV-TA W1-H 5):** commit the S4/S5 scripts as test bodies: `test_coverage_golden[effect|ratio]` (slow; counts 936 and 948 of 1,000, `random.Random(20261003)`) and `test_coverage_band[effect|ratio]` (slow; N = 4,000, coverage in [0.93, 0.97]). Docstrings say: the golden is a regression pin on this Python's stream, the band is the method claim. A golden failure with a green band is a stream change; a band failure is the R-H2 finding, recorded, never a re-seed.
11. The word `dominates` appears in `verdicts.py` only. The sweep S-2 test is X-H2's (its brief, item 11, carries the assumption); you add no allowlist.
12. Mutants for every adjacent rule pair in `verdicts.json`, parametrize ids (`and` to `or`, `<` to `<=` at each boundary, `alpha/m` to `alpha`, `holm` to `alpha` listed here and in turn a, `[:15]` to `[:16]`, each seed-key field dropped, stream key shared, sort removed, `20` to `10` in `resamples_for`).

## Turn c: gates (`gates.py`)
**Work:** `GateKind` (nine members), `GateItem`, `EMPTY = MappingProxyType({})`, `ring_items`, `pilot`, `pack_regression`, `admission` (W0 §8; design §3.2, §5).

**Acceptance items**
1. Red first, per the protocol.
2. **W0 rev 6 R6-13, verbatim:** `gates.pilot(view, hidden_test_disagreements: Sequence[str], unbiased_failures: Sequence[str], *, expected_na=EMPTY)`. `EMPTY` is `MappingProxyType({})`, never `None`. `expected_na` is keyword-only (`TypeError` if passed positionally); the three-argument call is valid. The readers X-E builds return `list[str]` or raise; the call site (X-C) converts a raise, so `pilot` never sees a missing list. Per R-96 ruling 2 ("the pilot's HB-USR-002 on `None` stands") `pilot` still refuses a `None` for either list with HB-USR-002 (`test_pilot_refuses_unread_lists`). One line, ruled, kept.
3. **RV-SIM W1-H 3 and RV-TA W1-H 4:** nine kinds, one `cell-lost` (blocked, failed or infrastructure/benchmark cause); `bnd-a-loss` (code `HB-CELL-107`) wins over `cell-lost` on the one shape where they differ (code 107, outcome `failed`); `test_every_gate_kind_has_a_red_fixture` asserts `set(FIXTURES) == set(GateKind)`.
4. **RV-TA W1-H 3:** `test_clean_view_passes` fails against the skeleton by assertion (`pilot(...) == []`).
5. `check-tampered` beats `primary-not-recorded`; `grader-error` once per cell; `metric-not-recorded` honours `expected_na`; `task-no-primary` means "no `property_check_pass` row at all", not "value None"; `hidden-tests-nondeterministic` and `suspend-detector-blind` one item per id; output sorted by `(kind, ident)`, unique, order independent (hypothesis).
6. **`admission(view, tasks, off_arm="off")` per W0 §8 / RV-SIM W1-H 10:** all off-arm cells 1 gives `(0, "saturated")`; all 0 gives `(0, "floor")` by exact int equality (R-85); else `(1, "")`; an NA primary in any off-arm cell raises HB-USR-002; rows A1..A5 including the `off_arm` argument honoured. *assume:* a task with no `off_arm` cell also raises HB-USR-002. Confirm: X-C's `admit` pre-check (W1-C §5). Breaks if false: such a task is admitted with no data.
7. `pack_regression`: `regression signal` iff `hi < 0`; `no regression detected at <mde>`; `Result withheld: ring is missing <arm>.`; no value matches `better|worse|dominates` (EVX-6). Seed `seed_for(ring_hash, prop, "ring", (incumbent, candidate))`.
8. Mutants in `gates.json`, parametrize ids (`all` to `any` in `admission`, `off_arm` ignored, precedence swaps, `blocked` dropped, `every` to `any` for `metric-not-recorded`, keyword-only dropped, `hi < 0` to `<=`).

## Known gap (Coordinator note, include in your report)
**N=4,000 coverage is unmeasured: the design's coverage claim at N=4,000 resamples has no measurement behind it. Add one seeded coverage simulation test (or mark the claim Inferred in the docstring and report it); do not assert a coverage number nobody measured.** Turn b item 10 is that test: run it, report the measured value, and write the band only as a claim the run supports. If the run lands below 0.93, report it as the R-H2 finding.

## Contradictions between the design and W0 rev 6 (W0 wins)
- **Failed reader (W0 rev 6.1, RV-TA: the design's `None` carrier at `eval-power-verdicts.md:205` is withdrawn).** Code against W0 §8 rev 6: the readers raise HB-USR-002 and `gates.pilot` takes `Sequence[str]`, never `None`. Design F13 and section 6 treat a `None` list as the signal. W0 rev 6 (R6-13): readers return `list[str]` or raise HB-USR-002 with a reason; `pilot` takes `Sequence[str]`. Your `pilot` follows rev 6 (item c2). The report-side third state is X-H2's.
- **Cell arm.** The design reads `views.cell_arm` with a `cell.pack` fallback. W0 §5 and W1-A define `plan.cell_arm`, and G1 (X-A1b) forbids reading `pack`. Use `plan.cell_arm`; do not write a `cell.pack` fallback.
- **Gate count.** The design's summary said ten kinds; the enum has nine (RV-SIM 3). Nine.

## Exit
README §3 join gate per turn (`ruff`, the full non-credential suite, `uv run python tools/mutate_check.py --touched main`, `docs-graph.py validate`, each on its own line). **Grok join rule (R-92 c1):** `python tools/grok_served_model.py <the dispatch's session dir>` exits 0 and its output goes in the Tracks row. Known state: on a deadline-killed session the reader currently exits 2 ("not recorded"); a fix is briefed separately. Until it lands, the Leader may read the `model_id` of each `assistant` row in `chat_history.jsonl` by hand and record the ids. Report per README §4, with the measured N = 4,000 coverage value and any defect-class text.
