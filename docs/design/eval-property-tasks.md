---
id: "design-eval-property-tasks"
title: "Design W1-L: the remaining property tasks (resilience, rework, no-guessing, simplicity; two each)"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation E2/E4: Wave 1 design slice W1-L (rework by X-RW in E2; the rest in E4)"
tags: [benchmark, property-tasks, resilience, rework, no-guessing, simplicity, evaluation-campaign, wave-1]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: design-eval-property-grader, rel: depends-on }
  - { to: design-eval-security-tasks, rel: depends-on }
  - { to: adr-0015-multi-turn-attempt-and-turn-snapshots, rel: depends-on }
  - { to: adr-0018-hidden-check-harness, rel: depends-on }
  - { to: adr-0019-catalog-0-7-property-metrics, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
  - { to: coordination-eval-wave1-briefs, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Eight tasks specified to the level an author can build without a question: for each of RS1/RS2 (resilience),
  RW1/RW2 (rework), NG1/NG2 (no-guessing) and SM1/SM2 (simplicity) a real MIT or Apache base at a pinned 40-hex
  commit (eight distinct bases, all imported under python -S), the latent requirement, the prompt shape, hidden tests
  with a wrong-app fixture for every test, the check or strategy, reference and naive shapes, expected values with
  provenance (Inferred until the real host reproduces them), and the seeded-defect variants that flip each probe,
  case clause or metric. Revision 2 applies the three first-round lens reviews and W0 rev 5: three new graders
  (noguess with hallucinated_symbol_errors per R-97; diffstats; rework) plus the resilience cases, the whole-tree
  simplicity counts with the outside-radius clause and v-laundered, verified_before_use not built in E4, skeleton-first
  commits for the helpers, and one parametrised task-test module. Gate: rev 2 pending RV-TA.
---

# Design W1-L: the remaining property tasks

**Status:** proposed, **revision 2**, gate in [Gate record](#gate-record). **Author:** W1-L, session `w1l-tasks-e1e4` (rev 1) and `w1l-tasks-r2-e1e4` (rev 2) (Claude Sonnet 5.5, `claude-sonnet-5-5`). **Grounded at:** rev 1 on `main` `d47965b1` (W0 revision 3); rev 2 merged `main` (W0 revision 5, rulings through R-98) into this branch. **Authored later by:** X-RW (RW1 in E2, RW2 in E4), X-RS, X-NG, X-SM (E4). No task file is written in this slice. Every change in rev 2 has a row in [Review disposition](#review-disposition).

## 1. Responsibility and boundaries

**One responsibility.** Specify eight property tasks so that their authors can write them without asking a question, and so that each task's hidden check decides its property mechanically. W1-I's S1/S2 design is the pattern; the lessons its reviews forced are applied here (section 14).

| It owns | It borrows by identity |
| --- | --- |
| the eight bases, pins, overlays, prompts, latent requirements | W0 section 2 `task.yaml` fields, section 3 the check contract, section 7 the metric ids |
| hidden tests, wrong-app fixtures, cases, variants, expected values | W1-F: `property.grade_cell`, `STRATEGIES`, `bench_check`, the classification order |
| the specification of three strategy helpers (`rework.py`, `noguess.py`, `diffstats.py`) | W1-G / X-G1: the eleven metric ids (catalog 0.7) |
| the seam requests of section 16 | X-E: `readiness.py`, the discrimination record; X-LB: loopback, fault kind; X-J2: `_changes.py` additions |

**Out of scope.** Writing `tasks/**`, the runner, the loopback fake (X-LB), any code. S1/S2 (W1-I). The `verified_before_use` producer (not built in E4, section 7.2).

## 2. Grounding

Labels: **Verified** = read or run by this slice. **Inferred** = reasoned; the confirming check is named.

| # | Fact | Source | Label |
| --- | --- | --- | --- |
| G1 | `ToolCall` is `{native_ordinal, name, tool_class (shell\|edit\|read\|other), start, end, ok, outcome_code}`; no argument, path or output is extracted. | `telemetry/__init__.py:61-69`, `grade/process.py:7-9`, `grade/drift.py:43-46` | Verified |
| G2 | A discrimination cell is a synthetic cell built from the oracle solution trees (EV-7), so it has no trajectory. | EV-7; W0 section 2 | Verified (text) |
| G3 | `scope_creep` counts lines added plus deleted in files **outside** `blast_radius` (`drift._in_radius`, private, one caller at `drift.py:131`; `_diff` over CRLF-normalised bytes). | `grade/drift.py:73,131` | Verified |
| G4 | `_changes.change_set(before, after)` returns `path -> added\|changed\|deleted`, build output excluded, CRLF normalised. | `grade/_changes.py:167-182` | Verified |
| G5 | Rework needs two graded trees: the final tree and the snapshot named in `graded_snapshots: [turn-1]`. | ADR-0015 section 8; W0 section 3 | Verified (text) |
| G6 | Not built in E1: `loopback`, `kind: fault`, `kind: static`, the `resilience` strategy, `rework`, `noguess`, `diffstats`. A task that declares one is NA `not built` for every metric. | W1-F section 4 | Verified (text) |
| G7 | W0 `measures` carries only non-derivable ids; resilience: `idempotency_violations`. `fault_suite_pass` is the grader's. | W0 section 3 | Verified (text) |
| G8 | Eight candidate bases (below) have licence files, a full 40-hex HEAD at 2026-10-03, and import under `python -S` (CPython 3.12.10). `humanize` (generated `_version`) and `python-slugify` (third-party `text_unidecode`) were rejected. | SP-L1 | Verified (3.12.10); **Inferred** for 3.14.6 |
| G9 | The authoring host has only CPython 3.12.10; the campaign pins 3.14.6. | `python --version` | Verified |
| G10 | W1-F's strategy table is `STRATEGIES: dict[str, Callable[[CellInput, GradeContext], dict[str, Score]]] = {"security": _hidden_check}`, keyed by `config.PROPERTY_NAMES`; one evidence file `property.json`; later helpers "each add one line". | `eval-property-grader.md` sections 3, 5.2, 5.7 | Verified |
| G11 | W0 rev 5 rules used here: `config.CHECK_PROPERTIES`, loopback shape (b) with `{fake_url}`, `_changes.product_lines(path) -> list[str]` and `in_radius(path, radius)` in X-J2's first E2 commit, the simplicity clause `outside_radius_lines`, `verified_before_use` not built, R-97. | W0 rev 5 sections 2, 3, 7, 13 | Verified (text) |

| task | base (repo @ commit) | licence (file) | `-S` import (SP-L1) |
| --- | --- | --- | --- |
| RS1 | `prometheus/client_python` @ `9cd073cb4dc6ee617eadf02dcdec94e0225eff0a` | Apache-2.0 (`LICENSE`, `NOTICE`) | ok |
| RS2 | `hynek/structlog` @ `91f44ae9031c80ad9c6045172f182803543ba6ba` (`src/`) | MIT OR Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`) | ok |
| RW1 | `xolox/python-humanfriendly` @ `6758ac61f906cd8528682003070a57febe4ad3cf` | MIT (`LICENSE.txt`) | ok |
| RW2 | `dbader/schedule` @ `82a43db1b938d8fdf60103bd41f329e06c8d3651` | MIT (`LICENSE.txt`) | ok |
| NG1 | `tkem/cachetools` @ `3c082c654c2804b9354e4b62dbd2994f1aac464d` (`src/`) | MIT (`LICENSE`) | ok |
| NG2 | `hukkin/tomli` @ `5a77b12a7a9f052ce5a20c335d2825658f6aea52` (`src/`) | MIT (`LICENSE`) | ok |
| SM1 | `msiemens/tinydb` @ `18d73a15066a04c77f19ae9a8c03d582bd344c0d` | MIT (`LICENSE`) | ok |
| SM2 | `jmespath/jmespath.py` @ `2812594e69d43098ef60f81f4efc404c071b0418` | MIT (`LICENSE`) | ok |

Every property pair is two different codebases (DR-T1); the eight are also distinct from each other and from S1 (microdot) and S2 (bottle). A later task may reuse a base across properties (RV-SIM 11); no rework now. The pins are `git rev-parse HEAD` of a fresh shallow clone on 2026-10-03; each task folder carries `NOTICE.md` and the upstream licence text, and `evidence.md` records the pin's `^{tree}` hash (the S1 rule).

Quoted rules this design rests on (DC-189):
- EV-3: "no call waits longer than the declared timeout plus the declared tolerance; retries per call are at most the declared maximum; no duplicate delivery produces a duplicate effect; the result is correct after the dependency recovers."
- EV-4: "`rework_ratio` = turn-1-added lines that turn 2 changed or deleted ÷ turn-1-added lines (non-test files inside the blast radius). Primary metric = 1 only when turn-2 tests pass, turn-1 tests still pass, and `rework_ratio` ≤ the task's declared ceiling."
- EV-5 (with the R-97 note appended in this revision): "`verified_before_use` (1 when a read of the API's source or docs, or a probe run, comes before the first edit that uses the API, by tool-call order)" and "`hallucinated_symbol_errors` is measured by the grading pass over the final tree: unresolved references to the vendored API (a static resolver for Python; the build log for a compiled language). R-97."
- EV-6: "Primary metric = 1 only when the hidden tests pass and each value is within the task's declared ceiling." and "they are counted by the existing `scope_creep` (US-30), not by `size_vs_reference`, so one line is never counted twice."
- W0 rev 5, section 7: "`new_abstractions` and `new_dependencies` count every non-test product file of the final tree" and "`property_check_pass` for a simplicity task also requires the added product lines in non-test files outside the radius to be at most `ceilings.outside_radius_lines`" (RV-TA W1-L 1, ruled).
- EV-7: "An expected value copied from a grader run is not provenance." and "A value derived by hand fails (HASH-A)" for a frozen value.

## 3. Data model (settled first)

**Bounded context.** Task authoring for property tasks, as W1-I section 3. New vocabulary: *fault case* (one declared schedule against a check-owned fake, outcome `passed|failed|timeout`), *effect* (what the fake records as applied, once per idempotency identity), *logical call* (one caller invocation, however many requests it sends), *turn-1-added line* (a product line the base-to-turn-1 diff adds), *vendored API* (an authored library in the base tree, unpublished), *member* (a name reachable from it), *product line* (section 5.1).

**Aggregate.** `PropertyTask`, root `tasks/<ID>/`, identified by its task version hash. **One invariant: the verdict on a solution depends only on that solution's behaviour or tree on fixed inputs, and every probe, case clause or metric branch is live, meaning some declared variant flips it and only it.** A branch no variant flips is a default result passing for evidence. Other aggregates are referenced by identity (discrimination record by `(task, task_version, identity_hash, platform)`).

**Durable representation. No new store.** Everything is a file in `tasks/<ID>/` (hashed into the task version; Type-2 by construction) or a row an existing writer writes (`scores`, `property.json`, the discrimination record). Grain table as W1-I section 3, with these additions:

| Item | Grain ("one file/row is exactly one ...") | Writer | Compute reader |
| --- | --- | --- | --- |
| `oracle/check/cases.yaml` (resilience only) | one declared fault-case list at one version | X-RS | grader (`cases.json`), readiness |
| schedule inside `check.py` | one fault schedule per case id | X-RS | the check |
| `turns/2.md`, `tests/turn1/`, `tests/turn2/` (rework) | one turn prompt / one turn's hidden tests | X-RW | runner (ADR-0015 section 1), `correctness.grade` per tree |
| `oracle/solutions/{reference,naive,alt}/` (rework: `turn-1/`, `turn-2/`) | one solution tree (after one turn) | the owning track | synthetic cells (X-E) |
| `oracle/variants.py`, `oracle/wrong_apps.py` | one literal table of `(file, old, new)` substitutions on the reference; a wrong-app entry also declares `reds`, the exact set of hidden test ids it turns red | each author | variant and wrong-app tests |
| `workspace/vendor/<lib>/**` (no-guessing) | one authored library, its source and README, **pristine** | X-NG | the agent (its working copy), the grader (restores this copy, section 7.0) |
| `size_reference_lines` frozen value (simplicity) | the reference's added product lines at one version | X-SM, produced by `_changes.product_lines` and `line_delta` (HASH-A) | readiness (equality with the function) |
| `property.json` `strategy.<name>` section | one helper's inputs and clause results for one cell | the helper, through `property.write_section` (SR-L5) | rebuild test, X-E |

**Measures and additivity (DM9, DM7).**

| Metric | Class | Derivation (one definition) |
| --- | --- | --- |
| `fault_suite_pass` | non-additive ratio | grader: passed ÷ fault cases (W0 section 3) |
| `idempotency_violations` | additive count | `measures` key from the check: sum over logical calls of `max(0, effects - 1)`, over cases |
| `rework_ratio` | non-additive ratio | `rework.grade`: section 6.1 |
| `turn1_tests_pass` | binary | `rework.grade`: hidden tests of turn 1 on the `turn-1` snapshot |
| `hallucinated_symbol_errors` | additive count | `noguess.grade`: section 7.1 (R-97) |
| `verified_before_use` | binary | **not built in E4**: NA `not built` for every cell (section 7.2) |
| `size_vs_reference` | non-additive ratio | `diffstats.grade`: added product lines in the radius ÷ `size_reference_lines` |
| `new_abstractions`, `new_dependencies` | additive counts | `diffstats.grade`: section 8.1, over the whole non-test tree |

**Single definitions.** Counting lives in `grade/_changes.py`, landed in **X-J2's first E2 commit** (SR-L4, granted; W0 section 13): `product_lines(path) -> list[str]` (the one rule, section 5.1) and `in_radius(path, radius)` (moved from `drift._in_radius`; `drift` imports it, its one caller unchanged). Rev 2 asks for two more beside them in that commit (SR-L6): `line_delta(old, new) -> (added: list[int], removed: list[int])` and `is_test_path(path)`. `rework` (E2) and `diffstats` (E4) import all four; nothing is defined twice. The radius partition makes EV-6's "never counted twice" structural: a line is in the radius (`size_vs_reference`) or outside it (the `outside_radius_lines` clause); `scope_creep` is `drift`'s and is never read here (R-90's refused grader coupling).

**Strategy fit with W1-F (G10; RV-PAT 4).** The registry lines, in `grade/property.py` (one line each, R-90 condition 4):

```python
STRATEGIES["rework"] = rework.grade            # E2, X-J2
STRATEGIES["no-guessing"] = noguess.grade      # E4, X-LG
STRATEGIES["simplicity"] = diffstats.grade     # E4, X-LG
STRATEGIES["resilience"] = _hidden_check       # E4, X-LB (W1-F's own line)
```

Keys are `config.PROPERTY_NAMES` (`rework`, `no-guessing`, `simplicity`, `resilience`). The three check-less helpers (W0: not in `config.CHECK_PROPERTIES`) have no cases, so they compute `property_check_pass` themselves: hidden tests (Kleene: false is 0, NA is NA) and then every ceiling clause; they may only narrow W0's predicate, never widen it. They write one object into the single `property.json` (`strategy.rework`, `strategy.no-guessing`, `strategy.simplicity`), not their own evidence files (RV-SIM 10, RV-PAT 4). What W1-F must offer is four small additions (SR-L5, section 16): `property.hidden_tests(inp, tree, label, overlay=None)`, `property.write_section`, the check-less sentence in section 5.7, and `procs.run` with `_env.grading_env` for a child process.

**Schema changes.** None. The catalog dependency is W1-G's (the metric ids and `property:` tags) plus X-G1's anchor_note edit (R-97 condition 3).

## 4. Delivery phasing and mock-substitutable seams

| Task | Becomes ready | Needs built first |
| --- | --- | --- |
| RW1 | E2 (X-RW) | multi-turn (X-J1); **X-J2's first commit** (`_changes.product_lines`, `in_radius`, `line_delta`, `is_test_path`), then `rework.py`; `graded_snapshots` |
| RW2 | E4 | as RW1 |
| RS1, RS2 | E4 | loopback (SP-LB result merged, X-LB), `kind: fault`, the `resilience` strategy, shape (b) (SR-L2, granted) |
| NG1, NG2 | E4 | `noguess.py` (X-LG), `_changes` four functions |
| SM1, SM2 | E4 | `diffstats.py` (X-LG), `_changes` four functions |

**Provisional markers (RV-SIM 9).** Sections 9 (cases, variants, fake caps, bounds) depend on SP-LB's merged result and X-LB, so they are **provisional (SP-LB, X-LB)**: the E4 author may re-cut cases if the fake's real behaviour differs, keeping the rules of section 9.1. Section 7 is firm on R-97. RW1 and the pins are firm.

**Mock-substitutable seams.** (1) `STRATEGIES[name]`: a missing helper is NA `not built` (W1-F). (2) Each helper takes plain values (`rework.measure(base, snap, final, radius)`, `diffstats.measure(base, final, radius)`, `noguess.unresolved(tree, radius, vendor)`), so X-LG and X-J2 test them on fixture trees without the runner. (3) The loopback fake is `bench_check.listen()`; X-RS develops `check.py` against a stand-in listener until X-LB lands.

## 5. Shared contracts

### 5.1 Product lines (the one counting rule)

`_changes.product_lines(path) -> list[str]` returns the file's lines (CRLF-normalised, decoded UTF-8) that are not blank, not comment-only, and not part of a docstring (found by `ast`: the first statement of a module, class or function, when it is a string expression, `lineno..end_lineno`). Only `.py` files; any other file gives `[]`. A file that does not parse keeps the blank/comment filter and skips the docstring rule (the strategies report the failure separately). `line_delta(old, new)` runs `difflib.SequenceMatcher(autojunk=False)` over two such lists and returns the indices of new lines added or replaced and of old lines removed or replaced. A product line of a changed file is *added* when it appears in `added`.

**Why docstrings are excluded (RV-SIM 7).** At the SM1 ceiling of `3.0000` over a 2-line reference, a 6-line docstring alone would bust it; the exclusion keeps an honestly documented solution passing. Nothing beyond blank, comment-only and docstring lines is excluded; `v-docstring` is the one test that proves it. *Residual R-S1:* a minimal solution can be padded with code on one line (`a; b`); the metric counts lines, not tokens, and the ceilings (section 8) carry slack for it.

**Test files.** `_changes.is_test_path(path)`: a path with a `tests` or `test` directory part, a name matching `test_*.py` or `*_test.py`, or `conftest.py`. One definition for rework, simplicity and the outside-radius clause.

### 5.2 `task.yaml` common fields

```yaml
schema: bench-task/1
scenario: 5
source: { kind: authored, upstream: "harness-bench property task on <repo>", repo: "<url>", commit: "<40-hex>", workspace_from: source, license: "<spdx>" }
language: python
graders: [correctness, property]          # R-90
property: { name: <one of 5>, latent_requirement: "<one sentence>", evidence_paths: [...], latent_terms: [...], primary_metric: property_check_pass, ceilings: {...}, fault_contract: {...} }
```

`workspace_from: source` and the overlay (`tasks/<ID>/workspace/`) follow E5 and S1. The overlay holds only docs and vendored libraries the task needs; it never edits an upstream file. **None of the eight declares `deliverable.build`**; the correctness runner runs `-S` with no site-packages, so a third-party import fails (`did not start`, a measured 0). Check-based properties (RS) hold `oracle/check/` and `cases.yaml`; the check-less ones (RW, NG, SM) hold **neither** (W0 rev 5, SR-L3, HB-RDY-005).

### 5.3 When a task may be `ready` (RV-TA 8)

For each property, `status` stays `draft` until a real-host discrimination record reproduces **every** value in `expected`. A `<...>` placeholder string, a number copied from a stand-in run, or an `expected` value of the wrong type is refused at `ready` by test `test_<id>_expected_is_literal_when_ready`. This binds the blocking items B-RW1, B-RW2, B-SM1 and B-SM2 (the committed-source hand counts) to a gate: a task with an open B-item cannot be `ready`. Because `verified_before_use` is `{na: "not built"}` for NG1 and NG2 (section 7.2), no discrimination run exercises it and no verdict may read it.

## 6. Rework tasks (RW1, RW2)

### 6.1 The strategy `rework.grade` (X-J2, E2)

Inputs: base tree, the `turn-1` snapshot, the final tree, `blast_radius`. Steps: (1) hidden tests of **turn 1** on the snapshot through `property.hidden_tests`, giving `turn1_tests_pass`; (2) hidden tests of turn 1 **and** turn 2 on the final tree (one run, both files; one result object per tree, RV-SIM 12), giving the primary's two test clauses; (3) for each non-test `.py` file in the radius: `T1` = `line_delta(product_lines(base), product_lines(snapshot))[0]`; `C` = the members of `T1` whose snapshot line index is in `line_delta(product_lines(snapshot), product_lines(final))[1]` (removed or replaced); `rework_ratio = Decimal(|C|) / Decimal(|T1|)` at scale 4, summed over files before dividing; `|T1| = 0` is NA `turn 1 added no product lines`. A cell that ends in turn 1 has the turn-2 metrics NA `turn 2 not reached` and `property_check_pass` 0 (EV-4). `property_check_pass = 1` iff turn-2 tests pass, turn-1 tests pass on the final tree, and `rework_ratio` ≤ the ceiling; hidden tests NA gives NA. The clause that decided is recorded in `strategy.rework.clause` (`tests|turn1|ratio`).

**Known blind spots (RQ-1, RV-TA 7).** The ratio sees only turn-1 lines that turn 2 *changes or deletes*, so insertion-only work scores 0. Three defences, each a test, and one named residual:
1. The turn-2 prompt is written so that any correct solution must change the turn-1 entry point (its behaviour is asserted through a call the turn-1 function must make).
2. The delegation test checks a **sentinel**: the recorder replacing the callee returns a unique object and the test asserts the entry point returns that very object (`is`), so a delegate whose result is discarded fails (variant `v-dead-delegate`).
3. `v-duplicate` (a sibling copy) must fail a turn-2 test, not merely score 0.
4. **Residual R-W1:** padding turn 1 with dead lines lowers the ratio (the denominator grows). `v-pad-turn1` is a named variant that is *expected to pass*: it records the known hole, and its test asserts `property_check_pass = 1` with a ratio below the reference's, so a future fix changes it knowingly. It is reported in the R-W1 line of every rework report, not hidden. The naive's ratio above the ceiling is a **target, not a guarantee** (B-RW1, B-RW2): X-RW writes the number from a hand count of the committed diff.

### 6.2 RW1: humanfriendly, a currency formatter

- **Base/pin/licence:** section 2. `blast_radius: ["humanfriendly/*.py"]` minus tests. `evidence_paths: ["humanfriendly/__init__.py"]`. Budget 60 (both turns).
- **Latent requirement:** "A formatter for one currency must keep the currency's symbol, decimals and separators in data, so a second currency adds data and not code paths."
- **Latent terms** (none in `prompt.md`): `currency`, `currencies`, `locale`, `euro`, `yen`, `EUR`, `JPY`, `per-currency`, `table`, `generalis`, `generaliz`.
- **Turn 1 (shape):** "Add `format_dollars(amount)` to `humanfriendly/__init__.py`. It returns US dollars with a thousands separator and two decimals, rounded half up: `format_dollars(1234.5)` is `'$1,234.50'` and `format_dollars(-5)` is `'-$5.00'`. It accepts an int, a float, a string number or a `Decimal`. Add tests to `humanfriendly/tests.py`."
- **Turn 2 (shape):** "Add `format_money(amount, currency)` for `'USD'` (`'$1,234.50'`), `'EUR'` (`'1.234,50 €'`) and `'JPY'` (`'¥1,235'`, no decimals, half up). An unknown code raises `ValueError`. `format_dollars(amount)` must now return `format_money(amount, 'USD')` by calling `format_money`."
- **Hidden tests, turn 1** (`tests/turn1/test_money1.py`): T1-1 `1234.5` gives `'$1,234.50'`; T1-2 negative; T1-3 half-up (`0.005` gives `'$0.01'`, `'2.675'` gives `'$2.68'`); T1-4 `Decimal`, `str`, `int` inputs below 1000; T1-5 zero. **Turn 2** (`tests/turn2/test_money2.py`): T2-1 EUR; T2-2 JPY; T2-3 unknown code raises; T2-4 negative EUR `'-1.234,50 €'`; T2-5 delegation: the test replaces `humanfriendly.format_money` with a recorder that returns a unique sentinel and asserts exactly one call with `(amount, 'USD')` **and** `format_dollars(amount) is sentinel`.
- **Wrong-app fixtures** (reference with one substitution; each turns exactly its declared `reds` red by `AssertionError`): `wa-nosep` [T1-1], `wa-noneg` [T1-2], `wa-halfeven` [T1-3], `wa-str` [T1-4], `wa-zero-blank` [T1-5], `wa-eur-prefix` [T2-1], `wa-jpy-decimals` [T2-2], `wa-noraise` [T2-3], `wa-eur-neg-prefix` [T2-4], `wa-nodelegate` [T2-5], `wa-dead-delegate` [T2-5].
- **Reference** (shape): a private `_CURRENCIES` table (symbol, decimals, position, group separator, decimal separator; USD only), one private `_format_money(amount, code)`, `format_dollars` calling it. Turn 2 adds the EUR and JPY rows, a public `format_money` that calls `_format_money`, and changes the one line in `format_dollars` to call `format_money`. **Naive** (shape): turn 1 one function with the `$`, two decimals and rounding inline; turn 2 rewrites it into `format_money` plus a body for `format_dollars`. **Alt** (a second correct solution, `oracle/solutions/alt/`): a dict-driven `_FORMATS` with a `Decimal.quantize` per code, different structure, same behaviour; it must score 1.
- **Expected** (provenance **Inferred**, a by-hand reading; the committed sources and stand-in count are X-RW's, blocking item B-RW1, gated by section 5.3):

```yaml
expected:
  reference: { property_check_pass: 1, turn1_tests_pass: 1, rework_ratio: "<X-RW, design target <= 0.1000>" }
  naive:     { property_check_pass: 0, turn1_tests_pass: 1, rework_ratio: "<X-RW, design target >= 0.6000>" }
ceilings: { rework_ratio: "0.3000" }
```

  The naive scores 0 because its ratio exceeds the ceiling, not because a test fails.
- **Variants flipping each branch:** `v-ratio-high` (table inlined into `format_dollars`, so turn 2 rewrites the body): flips the ratio clause only. `v-t1-regress` (turn 2 breaks T1-3): flips the turn-1-still-passes clause. `v-t2-short` (turn 2 not implemented, final = snapshot): flips the turn-2 clause. `v-duplicate`: fails T2-5. `v-dead-delegate` (`format_dollars` calls `format_money`, discards the result and returns its old body): fails T2-5 (sentinel). `v-pad-turn1` (turn 1 plus 20 dead lines in `format_dollars`): passes, ratio below the reference's (R-W1).

### 6.3 RW2: schedule, job failure handling

- **Base/pin/licence:** section 2 (`schedule/__init__.py`; tests `test_schedule.py`). `blast_radius: ["schedule/__init__.py"]`. `evidence_paths: ["schedule/__init__.py"]`. Budget 60.
- **Latent requirement:** "A failure policy added to a scheduler must sit behind one hook, so a second policy changes the hook's listeners and not the run loop."
- **Latent terms:** `hook`, `callback`, `observer`, `listener`, `policy`, `strategy`, `extensib`, `pluggable`, `subscribe`.
- **Turn 1 (shape):** "When a job raises, `Scheduler.run_pending()` must not stop. It keeps running the other due jobs and counts the failure: after the run `job.failures` is the number of consecutive failures of that job, reset to 0 by a success."
- **Turn 2 (shape):** "Add `Scheduler.on_failure(callback)`. Every failure calls each registered callback with `(job, exception)` in registration order. If any callback returns `False` the job is paused. A job that fails 3 times in a row is paused too. A paused job is not run again until `job.resume()`. The `failures` counter keeps working."
- **Hidden tests.** Turn 1: T1-1 other jobs run after a raising job; T1-2 two failures in a row give `failures == 2`; T1-3 a success after failures resets to 0. Turn 2: T2-1 callbacks in order; T2-2 callbacks get `(job, exc)` in that order; T2-3 pause after 3; T2-4 `resume()` re-enables; T2-5 the counter still works; T2-6 a callback returning `False` pauses the job after its first failure (the pause decision flows from a registered callback's **return value**, which a sibling `_notify` beside an untouched `try/except` cannot meet).
- **Wrong-app fixtures:** `wa-continue` [T1-1], `wa-count-once` [T1-2], `wa-noreset` [T1-3], `wa-order` [T2-1], `wa-args-swapped` [T2-2], `wa-pause2` [T2-3], `wa-noresume` [T2-4], `wa-counter-broken` [T2-5], `wa-ignore-return` [T2-6].
- **Reference/naive/alt shapes:** reference turn 1 keeps the failure count in `_record_failure(job, exc)` called from the run loop; turn 2 adds the hook list and has `_record_failure` iterate it, pausing on a `False` return or the third failure. Naive turn 1 inlines `try/except` and the counter in the run loop; turn 2 edits the same block for callbacks and pausing. Alt: a small `_FailureBus` class holding the callbacks, called from `_record_failure`.
- **Expected and ceiling:** as RW1 (`ceilings.rework_ratio` `"0.3000"`; numbers are X-RW's, blocking item B-RW2).
- **Variants:** `v-ratio-high` (loop edited in place), `v-t1-regress`, `v-t2-short`, `v-nohook-order` (flips T2-1), `v-ignore-return` (the loop calls callbacks but ignores their return: fails T2-6), `v-pad-turn1` (R-W1), `v-duplicate` (a second `run_pending_v2` with the new behaviour, the old one untouched: fails T2-6 or T2-3 by test).

## 7. No-guessing tasks (NG1, NG2) and the `noguess` strategy

### 7.0 The pristine vendored library (RV-PAT 2)

`workspace/vendor/<lib>/**` is in the agent's working copy, so the agent can add `RateLimiter` or `get` to it and make a guess "exist". Grading therefore restores the pristine copy: before the hidden tests and before the resolver, `noguess.grade` deletes `vendor/<lib>/` in the grading copy and copies `tasks/<ID>/workspace/vendor/<lib>/` (the task folder, part of the task hash) over it, through `property.hidden_tests(..., overlay=)` (SR-L5) and the same path handed to the resolver. The agent's edit to its own copy is invisible to the verdict. Variant `v-vendor-edit` (section 7.3) pins it.

### 7.1 `hallucinated_symbol_errors` (R-97, ruled; A granted, B refused)

**Meaning (R-97).** The number of distinct references, in the final tree inside `blast_radius`, to a member of the task's vendored API that the real library does not define. A grading-pass measure (source D), never a trajectory count. A name the agent defines itself is not a reference. **One producer per language (R-97 condition 1):** for Python, the static resolver below; for a compiled language, the correctness grader's `build.log` (compiler errors naming a missing member). *The build-log path is not built in E4* (no compiled no-guessing task exists): such a task scores NA `not built for <runner>`, never 0. `noguess.py`'s module docstring states both sentences.

**The Python resolver.** `ast` collection over every non-test `.py` file in the radius; a `SyntaxError` anywhere gives NA `syntax error: <path>`. References it can see:
1. Names in `from <lib> import a, b` (reference `lib.a`), and attribute chains rooted at an `import <lib> [as alias]` (the shortest unresolved prefix counts once).
2. **Typed receivers** (RV-TA 6): a local variable or `self.<attr>` assigned from a call whose callee resolved to a class (`g = lib.Gate(...)`, `self.g = lib.Gate(...)`), and a parameter annotated with a resolved class (`s: lib.MappingSource`). `x.m` then names `lib.Gate.m`. Flow-insensitive; a variable assigned two different classes is untyped.
3. Keywords at a call whose callee resolved (name form `<callee dotted>:<kw>`, for a class `lib.Cls.__init__:kw`), unknown to `inspect.signature` unless the callee takes `**kwargs`.

A member is *resolved* when `hasattr(cls, name)` or `name` is assigned as `self.<name>` in the class's source (so a documented instance attribute is not a false positive). A **child process** does the reflection: `python -S`, `sys.path` = the pristine vendor directory only, started through `procs.run` with `_env.grading_env()` (kill-on-close, bounded), receives the names (never agent code) and answers per name. The metric is the number of distinct unresolved names.

**Never 0 by failure (R-97 condition 2).** If the child cannot import the library, times out, or answers malformed, the metric is NA `resolver failed: <first stderr line>`; never 0. Red test `test_hse_resolver_failure_is_na` (X-LG).

**Residuals (R-N1).** The count is an under-count: dynamic access (`getattr(lib, name)`), a receiver of unresolved type (an unannotated parameter, a value returned by a call), and a one-line deliverable that never references the library (it reimplements it; it also fails the hidden tests) are invisible, and read 0 for a reason the reader must know. The pair (hidden tests and the count) reads correctly; the resolver never infers intent. The catalog's `anchor_note` wording ("build-log errors") is X-G1's edit (R-97 condition 3).

### 7.2 `verified_before_use`: not built in E4 (W0 rev 5; SR-L1 refused)

SR-L1's `target` (a path for read/edit rows, the first command word for the rest) gives a plausible wrong 0: Codex and Copilot read through shell calls (`cat vendor/...`), whose target is `cat`. W0 rev 5 rules the metric's producer **not built**: every cell records NA `not built`, and both `expected` roles declare `{na: "not built"}`. No telemetry change is made in E4 and nothing in this design reads `ToolCall`. The predicate, the `test_vbu_*` rows and the `target` column of the E7 list of rev 1 are deleted. Re-opening needs a new seam request with a design that gives every pre-edit row a per-harness attributable target, the per-cell NA `reads not attributable`, one test per harness through the real extraction on a recorded transcript, and a landing before the first baseline that includes an NG task (W0 rev 5's re-open trigger). Until then no verdict may read the metric (section 5.3).

### 7.3 NG1: cachetools plus the vendored `quotakit`

- **Base/pin/licence:** section 2. Overlay `vendor/quotakit/` (authored, MIT, with `README.md` stating the true contract). `blast_radius: ["src/cachetools/limiter.py", "src/cachetools/__init__.py"]`. Budget 45.
- **Vendored API (authored, unpublished).** Package `quotakit`: class **`Gate(max_per_window, window_seconds, *, clock=time.monotonic, mode="sliding")`**; method **`admit(cost=1) -> bool`**; exception **`QuotaExceeded`**. Conventional guesses, absent here: `RateLimiter(calls, period)`, `.acquire()` / `.allow()` / `.try_acquire()`, `RateLimitExceeded`, a fixed window by default. *Renamed:* `RateLimiter`→`Gate`, `acquire`→`admit`, `RateLimitExceeded`→`QuotaExceeded`. *Changed default:* `mode="sliding"`.
- **Latent requirement:** "Code that uses a vendored library must read its source or documentation and use only the members and defaults that exist." **Latent terms:** `read`, `documentation`, `docs`, `README`, `source`, `signature`, `docstring`, `verify`, `check the`, `look at`.
- **Prompt (shape):** "Add `src/cachetools/limiter.py` with `limit_calls(max_calls, per_seconds, clock=None)`, a decorator that lets the function run at most `max_calls` times in any window of `per_seconds`, using the `quotakit` package in `vendor/quotakit`. When the limit is reached the call raises `cachetools.limiter.LimitExceeded`. Add tests in `tests/test_limiter.py`."
- **Hidden tests** (`tests/test_limiter_hidden.py`, `vendor/quotakit` on `sys.path`, fake clock): N-1 allows `max_calls` calls; N-2 the next raises `LimitExceeded`; N-3 **sliding semantics** (calls at 0.0 and 0.9 of a 1.0 s window, `max_calls 2`: a third at 1.05 is allowed and a fourth at 1.2 is refused; a fixed-window guess differs at 1.2); N-4 `clock=None` uses the default clock; N-5 the result and name are preserved; N-6 `LimitExceeded` is not `quotakit.QuotaExceeded`.
- **Wrong-app fixtures:** `wa-extra-allowed` [N-1], `wa-no-raise` [N-2], `wa-fixed-window` [N-3], `wa-clock-none` [N-4] (passes `clock=None` through), `wa-wraps` [N-5], `wa-same-exception` [N-6] (aliases `QuotaExceeded`).
- **Reference:** builds `quotakit.Gate(max_calls, per_seconds, clock=clock or time.monotonic)`, calls `gate.admit()`. **Naive:** `from quotakit import RateLimiter, RateLimitExceeded` and `.acquire()`; the import fails, every hidden test fails, the resolver finds **two** unresolved names (the `.acquire` receiver is untyped). **Alt:** the same through `with`-free `functools.wraps` and a module-level gate registry; scores 1.
- **Expected (Inferred; the discrimination record is the measurement, R-97 condition 4):**

```yaml
expected:
  reference: { property_check_pass: 1, hallucinated_symbol_errors: 0, verified_before_use: { na: "not built" } }
  naive:     { property_check_pass: 0, hallucinated_symbol_errors: 2, verified_before_use: { na: "not built" } }
```

- **Variants:** `v-hallucinated` (reference plus `g = quotakit.Gate(...); g.try_acquire()` on an unreached branch): count 0 to 1 by the typed receiver, hidden tests green. `v-kw` (reference plus an unreached `quotakit.Gate(..., period=...)`): count 1 (`quotakit.Gate.__init__:period`). `v-default` (reference passing `mode="fixed"`): flips N-3, count 0. `v-vendor-edit` (reference plus an added `try_acquire` in the agent's `vendor/quotakit/quotakit/gate.py` and an unreached call to it): graded against the pristine copy the count stays 1; a mutant that resolves against the agent's copy reads 0 and turns the test red.

### 7.4 NG2: tomli plus the vendored `envkit`

- **Base/pin/licence:** section 2. Overlay `vendor/envkit/` (authored, MIT, README). `blast_radius: ["src/tomli/_interp.py", "src/tomli/__init__.py"]`. Budget 45.
- **Vendored API.** `envkit.MappingSource(mapping)`; method **`fetch(name, *, fallback=MISSING)`**; exception **`UnknownName`**. Conventional guesses: `EnvSource`, `.get(name, default=None)`, returning `None` or `""` for an unknown name. *Renamed:* `get`→`fetch`, `EnvSource`→`MappingSource`. *Changed default:* an unknown name **raises** `UnknownName` unless `fallback` is given.
- **Latent requirement / terms:** as NG1.
- **Prompt (shape):** "Add `tomli.loads_env(text, source)` in `src/tomli/_interp.py`, exported from `tomli`. It parses TOML as `tomli.loads` does and replaces `${NAME}` in every string value (including inside arrays and tables) with the value `source` gives for `NAME`, using the `envkit` package in `vendor/envkit`. `source` is an `envkit.MappingSource`. A name `source` does not know is an error. Add tests in `tests/test_interp.py`."
- **Hidden tests:** G-1 simple substitution; G-2 nested table and array strings; G-3 an unknown name raises `envkit.UnknownName`; G-4 `${A}${B}` adjacency; G-5 a string with `$HOME` and braces but no `${}` is untouched; G-6 non-string values untouched.
- **Wrong-app fixtures:** `wa-nosubst` [G-1, G-2, G-4], `wa-no-nested` [G-2], `wa-unknown-empty` [G-3], `wa-greedy-regex` [G-4], `wa-template` [G-5], `wa-int-str` [G-6].
- **Reference:** `source.fetch(name)` with `UnknownName` propagating. **Naive:** `from envkit import EnvSource`; `source.get(name, "")`. The resolver sees `envkit.EnvSource` (1); `source.get` has an untyped receiver and is not counted, so the count is **1** (R-97: "NG2 as declared"). **Alt:** a `re.sub` with a callback and a recursive walk; scores 1.
- **Expected (Inferred):** reference `{property_check_pass: 1, hallucinated_symbol_errors: 0, verified_before_use: {na: "not built"}}`; naive `{0, 1, {na: "not built"}}`.
- **Variants:** `v-hallucinated` (reference plus an unreached `envkit.EnvSource` reference: 1), `v-hallucinated-member` (reference plus an unreached `def f(s: envkit.MappingSource): s.get("x")`: 1, `envkit.MappingSource.get`; pins annotation typing), `v-default-guess` (catches `UnknownName` and returns `""`: flips G-3, count 0), `v-kw` (unreached annotated `s.fetch("x", default="")`: 1, `envkit.MappingSource.fetch:default`), `v-vendor-edit` (as NG1).

## 8. Simplicity tasks (SM1, SM2) and the `diffstats` strategy

### 8.1 `diffstats.grade` (X-LG, E4)

Inputs: the base tree, the final tree, `blast_radius`. Counts use `_changes.change_set`, `product_lines`, `line_delta`, `in_radius` and `is_test_path` (section 3).

- `size_vs_reference` = added product lines in non-test `.py` files **inside** the radius ÷ `size_reference_lines`, scale 4. `size_reference_lines` is frozen in `task.yaml` and equals the same function applied to the committed reference diff (HASH-A: readiness recomputes it; a hand count fails).
- `new_abstractions` = the number of `ClassDef` nodes in non-test `.py` files of the **whole final tree** minus those in the base tree, keyed by `(path, qualified name)` (RV-TA 10: `Protocol`, `ABC` and `dataclass` are classes like any other; no second count for a base class). W0 rev 5 section 7.
- `new_dependencies` = top-level imported module names across the whole final tree's non-test `.py` files, minus the base tree's, minus `sys.stdlib_module_names`, minus the package itself and relative imports (RV-SIM 6: no `pyproject` scan, no exemption table until a task needs one).
- `outside_radius_lines` = added product lines in non-test `.py` files **outside** the radius, over the whole tree. It is a clause, not a catalog metric (W0 rev 5): it is recorded in `strategy.simplicity` and never reads `drift`'s `scope_creep`.

`property_check_pass = 1` iff hidden tests pass and `size_vs_reference ≤ ceilings.size_vs_reference`, `new_abstractions ≤ ceilings.new_abstractions`, `new_dependencies ≤ ceilings.new_dependencies`, `outside_radius_lines ≤ ceilings.outside_radius_lines` (required, HB-RDY-005 if absent); the deciding clause is recorded (`tests|size|abstractions|dependencies|scope`). The hidden tests running first are in `property.hidden_tests` (SR-L5). The strategy has no `oracle/check/` (SR-L3).

### 8.2 SM1: tinydb, `Table.first`

- **Base/pin/licence:** section 2. `blast_radius: ["tinydb/table.py"]`. `evidence_paths: ["tinydb/table.py"]`. Budget 45.
- **Latent requirement:** "A small addition to a library must be the smallest code that meets the ask, with no new type, option or layer the ask never named." **Latent terms:** `minimal`, `simple`, `smallest`, `no extra`, `without adding`, `YAGNI`, `abstraction`, `configur`, `option`, `strategy`, `factory`.
- **Prompt (shape):** "Add a method `first(cond)` to `Table` in `tinydb/table.py`. It returns the first document that matches `cond`, or `None` when none matches. Add tests to `tests/test_tables.py`."
- **Hidden tests** (`tests/test_first_hidden.py`): F-1 first match in insertion order; F-2 `None` when no match; F-3 on an empty table; F-4 a query matching several returns only the first; F-5 the returned object is a `Document` with its `doc_id`.
- **Wrong-app fixtures:** `wa-last` [F-1, F-4] (returns the last: the two tests are one declared pair), `wa-raises` [F-2], `wa-empty-raises` [F-3], `wa-dict` [F-5].
- **Reference (exact):** `def first(self, cond): return next(iter(self.search(cond)), None)`: 2 product lines. `size_reference_lines: 2`. **Naive:** the same method plus an unrequested `FirstOptions` dataclass, a `FirstStrategy` ABC and a `ScanStrategy`: 3 new abstractions, about 25 product lines, all tests pass. **Alt (honest, 6 lines):** a `for` loop with an early `return` and a final `return None`; must score 1.
- **Ceilings:** `{size_vs_reference: "3.0000", new_abstractions: 0, new_dependencies: 0, outside_radius_lines: 4}`. `3.0000` admits the 6-line honest solution (`6 ÷ 2`, exactly on the ceiling); the outside allowance of 4 covers an incidental export line (assume A5).
- **Expected:** reference `{property_check_pass: 1, size_vs_reference: "1.0000", new_abstractions: 0, new_dependencies: 0}`. The reference's `1.0000` is `2 ÷ 2` by definition: a **tautology**, labelled so in `expected` provenance; it is not a discriminating observation (RV-TA 12). The naive and the variants carry the proof. Naive `{0, "<naive lines ÷ 2>", 3, 0}`: `new_abstractions` 3 by construction (three `ClassDef` nodes); the size ratio is X-SM's hand count (blocking item B-SM1; design requirement at least `6.0000`; section 5.3 gates it).
- **Variants (every metric and clause flips):** `v-bloat` (reference plus a 5-line helper `_first_or_none`: size 7, ratio `3.5000`, flips `size` only). `v-class` (reference plus one empty `class _Sentinel`: flips `abstractions` only). `v-dep` (reference using `import attr` in a dead branch: flips `dependencies` only; the import also fails nothing at test time since the branch is unreached). `v-docstring` (reference plus a 6-line docstring: must flip **nothing**, section 5.1). **`v-laundered`** (RV-TA 1; separates clause (b) from (a)): `first` in `table.py` becomes `from ._first import find_first` plus `def first(self, cond): return find_first(self.search(cond))`, and a new `tinydb/_first.py` holds 25 lines of plain functions, no class and no import. In-radius size is 3 lines (`1.5000`), abstractions 0, dependencies 0, so only `outside_radius_lines` (25 > 4) fails: `property_check_pass` 0, clause `scope`; a mutant that drops clause (b) turns the test red. **`v-laundered-class`** (the (a) half): the reference plus a new `tinydb/_first.py` holding one empty `class _Marker`. Its 2 outside lines are within the allowance, so only the **whole-tree** `new_abstractions` (1 > 0) fails, clause `abstractions`; a mutant that counts classes inside the radius only reads 0 and turns it red.

### 8.3 SM2: jmespath, `search_many`

- **Base/pin/licence:** section 2. `blast_radius: ["jmespath/__init__.py"]`. `evidence_paths: ["jmespath/__init__.py"]`. Budget 45.
- **Latent requirement and terms:** as SM1.
- **Prompt (shape):** "Add `search_many(expression, documents, options=None)` to `jmespath/__init__.py`. It returns a list with the result of `jmespath.search` for each document, in order, parsing the expression once. Add tests in `tests/test_search_many.py`."
- **Hidden tests:** M-1 order and values; M-2 empty list gives `[]`; M-3 `options` passes through (a custom function table changes the result); M-4 the expression is parsed once: the test wraps **`jmespath.parser.Parser.parse`** (the method, not `_do_parse`, because the parser caches parses) with a recorder and counts calls; M-5 an invalid expression raises `ParseError` even when `documents` is empty.
- **Wrong-app fixtures:** `wa-reversed` [M-1], `wa-none-empty` [M-2], `wa-noopts` [M-3], `wa-reparse` [M-4] (the red fixture for the recorder's target: without it the method name is unproven, assume A4), `wa-lazy` [M-5].
- **Reference (exact, 3 product lines):** `def search_many(expression, documents, options=None): parsed = compile(expression); return [parsed.search(d, options=options) for d in documents]`. `size_reference_lines: 3`. **Naive:** the same function wrapped by `BatchConfig` (dataclass), `BatchSearcher` and a `ResultCollector` Protocol: 3 abstractions, ratio expected at least 8. **Alt (honest, 9 lines):** an explicit loop with a result list; ratio `3.0000`, exactly on the ceiling; must score 1.
- **Ceilings/expected/variants:** as SM1 with `size_reference_lines: 3`; ceilings `{size_vs_reference: "3.0000", new_abstractions: 0, new_dependencies: 0, outside_radius_lines: 4}`. `v-bloat` adds a helper so the total is 13 product lines (`13 ÷ 3 = 4.3333`). `v-laundered` and `v-laundered-class` use `jmespath/_batch.py`.

## 9. Resilience tasks (RS1, RS2) and the `resilience` strategy (provisional: SP-LB, X-LB)

### 9.1 Check shape (shared)

`interface: loopback`, shape (b) of W0 rev 5 (SR-L2, granted): the **dependency is a check-owned fake** on `bench_check.listen()` (`("127.0.0.1", 0)`, asserted; ADR-0018 section 3), and the deliverable is a **client function**, an `app` of `kind: callable` whose request `args` use `{fake_url}`. The check measures the wall time of each probe-host call (request frame written to response frame read) and reads the fake's counters, which record request count, effect count and the **key or batch-id value** of every request (counts and ids, never bodies). Case `kind: fault`, outcomes `passed|failed|timeout`. `fault_suite_pass` = passed ÷ cases (grader). `idempotency_violations` = sum over logical calls of `max(0, effects - 1)` (a `measures` key). `property_check_pass` = hidden tests and `ran` and every case `passed` (W0).

**Case fields (RV-PAT 3):** `{id, schedule, expect: succeed|fail|either, final: bool, then: <second call> | null, bound_ms?}`. A fault case passes iff **all** its clauses hold; the record names the first that fails, in this order (`clause: time|requests|effect|result`):
1. **time:** the call returned or raised within `timeout_ms + tolerance_ms`.
2. **requests:** per logical call, `requests ≤ max_retries + 1`; and `requests == 1` for a `final: true` case (a final error, a 4xx, is not retried: RV-TA 5b).
3. **effect:** `either`: `effects ≤ 1`; `succeed`: the call returned the right value and `effects == 1`; `fail`: the call raised and `effects == 0`.
4. **result:** for a case with `then`, the second call after the fault clears returns the correct value (the id stored by the first effect, or a fresh one when none was applied).

**Which cases say what.** `succeed` only where the latent requirement makes it unavoidable (`f-5xx-burst`, `g-5xx-burst`: a client that retries transient failures within budget). A case where the prompt only promises "return or raise within 3 seconds" (`f-slow-first`, `f-lost-response`, `g-slow-first`, `g-lost-response`) is `either`: after a slow first response the effect is applied, and a correct call that raises at 3 s passes as well as one that retries with the same key. `fail` only where the fake never applies the effect (`f-5xx-persistent`, `f-4xx`, their RS2 twins). This is §13's "predicates accept sets of correct behaviours".

`fault_contract` (both tasks): `{timeout_ms: 3000, tolerance_ms: 500, max_retries: 2}`. **Numbers are in the prompt; the mechanisms are latent** (RQ-2): the prompt says a call returns or raises within 3 seconds and sends at most 3 requests, and never says how.

**Case bound (RV-DS 4 lesson).** Declared per case from the designed fault: cases that wait for the full budget have `bound_ms: 4500` (3000 + 500 tolerance + 1000 for host start and fake setup; host start measured 67 ms in SP-I3, Inferred for 3.14.6); quick cases omit it (interface bound). *Upgrade trigger:* X-RS measures the reference's `duration_ms` per case in the E4 spike and replaces any bound that is not at least 25 percent above the reference's slowest honest run. **Inferred.**

**Determinism (RV-TA 9).** Every schedule is a fixed list (which request number is delayed, dropped or answered 503); the seed is recorded and unused (`simplify:` no jitter; upgrade trigger: a case whose outcome depends on the order of two concurrent faults). Two ports never collide (port 0 per case). Test `test_rs_outcomes_are_stable`: the reference is graded three times with equal outcomes, and once beside a CPU busy-loop process with the same outcomes (the tolerance of 500 ms is the margin under test).

### 9.2 RS1: prometheus_client, a ledger-event client

- **Base/pin/licence:** section 2. Overlay `docs/ledger-service.md`: `POST /v1/events` with JSON `{"name": str, "value": number}`; 201 `{"id": int}`; an optional `Idempotency-Key` header: a second request with the same key returns 200 and the original `id` and creates no event; 5xx may be transient; 4xx are final. `evidence_paths: ["docs/ledger-service.md", "prometheus_client/exposition.py"]`. Budget 45.
- **Latent requirement:** "A call to a remote service must bound every attempt, retry only transient failures within the stated budget, and send a stable idempotency key so a replayed request takes effect once." **Latent terms:** `timeout`, `retry`, `retries`, `backoff`, `idempot`, `dedup`, `deduplic`, `transient`, `circuit`, `jitter`, `give up`, `exactly once`.
- **Prompt (shape):** "Add `prometheus_client/ledger.py` with `post_event(base_url, name, value)`. It sends the event to `<base_url>/v1/events` as described in `docs/ledger-service.md` and returns the new event's `id` as an int. It raises `LedgerError` when the service refuses or cannot be reached. A call must return or raise within 3 seconds and must send at most 3 requests to the service. Add tests in `tests/test_ledger.py`."
- **Hidden tests** (`http.server` on loopback inside the test): H-1 returns the `id` as int; H-2 sends a JSON body with `name` and `value`; H-3 a 400 raises `LedgerError`; H-4 connection refused raises `LedgerError`; H-5 a trailing slash on `base_url` is accepted; H-6 module import has no side effect.
- **Wrong-app fixtures:** `wa-id-str` [H-1], `wa-path` [H-2], `wa-swallow` [H-3], `wa-leak-urlerror` [H-4] (raises `urllib.error.URLError`), `wa-slash` [H-5], `wa-import` [H-6].
- **Cases (7):** `f-5xx-burst` (503, 503, 201; `succeed`); `f-5xx-persistent` (all 503; `fail`); `f-slow-first` (first response delayed 6 s, effect applied on arrival; `either`; bound 4500); `f-hang` (never answers; `either`; bound 4500); `f-lost-response` (effect applied, connection closed; a second request with the same key returns the stored result; `either`); `f-4xx` (400; `fail`, `final`); `f-recover` (call 1 against a hung service, then the fault clears, call 2 must return the correct `id`; `then`; bound 4500). `f-ok` is dropped: the happy path is H-1 (RV-SIM 4).
- **Reference:** `ATTEMPTS = 3`, a deadline of 2.9 s from the call; each attempt's timeout is the remaining time divided by the attempts left; retries on 5xx, connection reset and timeout; never on 4xx; one `Idempotency-Key` per call reused across its attempts. **Naive:** plain `urlopen` with no timeout, no retry, no key (passes all six hidden tests). **Alt:** a fixed 0.9 s per attempt with a 50 ms pause between attempts; passes every case (different timing, same bounds).
- **Expected (Inferred; hand-traced by case; the fake is X-LB's, so no run exists):**

```yaml
expected:
  reference: { property_check_pass: 1, fault_suite_pass: "1.0000", idempotency_violations: 0 }
  naive:     { property_check_pass: 0, fault_suite_pass: "0.4286", idempotency_violations: 0 }
# naive passes f-5xx-persistent (one 503, one request, raises quickly), f-lost-response (raises after one request, effect 1, `either`) and f-4xx = 3 of 7.
# It fails f-5xx-burst (raises; `succeed` needs the value), f-slow-first and f-hang (no timeout: the case bound ends it as `timeout`), f-recover (hangs).
# It never retries, so no call has two effects: violations 0.
```

- **Variants** (each one substitution on the reference; all hidden tests green, `deliverable == ran`; hand-traced in rev 2, **Inferred** until the first run, and a wrong set is red on first run, which is where the author finds it):

| variant | flips | clause | trace |
| --- | --- | --- | --- |
| `v-no-retry` (`ATTEMPTS = 1`) | `f-5xx-burst` | effect | one 503, raises, `succeed` wants the value; `f-slow-first` raises at ~3 s with effect 1 (`either`): passes |
| `v-no-timeout` (no per-attempt timeout) | `f-slow-first`, `f-hang`, `f-recover` | time | the 6 s delay or the hang outlasts the 4500 ms bound |
| `v-attempt-3s` (3.0 s per attempt, 3 attempts, no budget) | `f-hang`, `f-recover` | time | two hung attempts reach 6 s; `f-slow-first` attempt 1 ends at 3.0 s, attempt 2 answers at once: 3.0 s, within 3.5 s, not flipped |
| `v-retry-5` (`ATTEMPTS = 5`) | `f-5xx-persistent`, `f-hang`, `f-recover` | requests | 5 requests inside the 2.9 s budget |
| `v-no-key` (no `Idempotency-Key`) | `f-slow-first`, `f-lost-response` | effect | the retry creates a second event; violations 2 |
| `v-retry-4xx` (retry on every status) | `f-4xx` | requests | `final` wants exactly 1 request, three sent |
| `v-cache-error` (a module flag set by a failed call and never cleared) | `f-recover` | result | call 2 raises the cached error, the fake having recovered |

  `v-no-timeout` and `v-attempt-3s` differ on `f-slow-first` (RV-SIM 5, RV-TA 5a); the test asserts the set, the clause and, for the time clause, the maximum observed `duration_ms` band (above 3500 ms for both). `v-key-per-attempt` and `v-retry-forever` of rev 1 are removed: the first flips the same cases on the same clause as `v-no-key` and no input separates them (RV-TA 5d, RV-SIM 5); the second duplicated `v-retry-5` and `v-no-timeout`. A **crash variant** (every call raises) flips `f-5xx-burst` and `f-recover` and is rejected by the "hidden tests pass" clause (H-1 red; S1 lesson). Every case has a flipping variant: `f-5xx-burst` (`v-no-retry`), `f-5xx-persistent` (`v-retry-5`), `f-slow-first` (`v-no-timeout`, `v-no-key`), `f-hang` (`v-no-timeout`, `v-attempt-3s`, `v-retry-5`), `f-lost-response` (`v-no-key`), `f-4xx` (`v-retry-4xx`), `f-recover` (four) and the `result` clause (`v-cache-error`).

### 9.3 RS2: structlog, a batching log shipper

- **Base/pin/licence:** section 2. Overlay `docs/collector.md`: `POST /v1/logs` with `{"batch_id": str, "records": [..]}`; 200 `{"accepted": n}`; a repeated `batch_id` is accepted without applying it again; 5xx transient; 4xx final. `blast_radius: ["src/structlog/shipper.py"]`. `evidence_paths: ["docs/collector.md", "src/structlog/processors.py"]`. Budget 45.
- **Latent requirement:** "A shipper must bound every flush, keep a batch's identity stable across its retries, and keep unsent records after a failure so recovery delivers each record once." **Latent terms:** as RS1 plus `batch id`, `stable`.
- **Prompt (shape):** "Add `src/structlog/shipper.py` with `HttpShipper(base_url)`. Its `processor(logger, name, event_dict)` appends a copy of the event to an in-memory buffer and returns `event_dict` unchanged. `flush()` sends the buffered records in one batch to `<base_url>/v1/logs` as in `docs/collector.md`, empties the buffer on success and returns the number accepted. On failure `flush()` raises `ShipError` and keeps the records for the next flush. A flush must return or raise within 3 seconds and send at most 3 requests. Add tests in `tests/test_shipper.py`."
- **Hidden tests:** S-1 the processor returns `event_dict` unchanged and buffers a copy; S-2 `flush()` returns the accepted count and empties the buffer; S-3 a refused batch (400) raises `ShipError`; S-4 an empty buffer sends nothing; S-5 order is preserved. **Wrong-app fixtures:** `wa-nocopy` [S-1], `wa-keep` [S-2], `wa-ok4xx` [S-3], `wa-sendempty` [S-4], `wa-reverse` [S-5].
- **Cases (7):** `g-5xx-burst` (`succeed`); `g-5xx-persistent` (all 503; `fail`; `then`: after recovery a second flush delivers all records, applied once); `g-slow-first` (`either`); `g-hang` (`either`); `g-lost-response` (batch applied, connection closed; a retry must reuse `batch_id`; `either`); `g-4xx` (`fail`, `final`); `g-ordering` (records r1, r2 buffered, a flush fails, r3 added, a recovery flush; the collector sees r1, r2, r3 in order; `then`). `g-ok` is dropped (RV-SIM 4).
- **Reference:** `batch_id` created when the batch is formed and kept until success; per-flush budget as RS1; retry 5xx/reset/timeout; buffer cleared only after acceptance. **Naive:** one `urlopen`, a new `batch_id` per flush, buffer kept on exception (passes the hidden tests). **Alt:** fixed per-attempt timeouts of 0.9 s.
- **Expected (Inferred):** reference `{1, "1.0000", 0}`; naive `{0, "0.5714", 0}`: it passes `g-5xx-persistent` (the failed flush applied nothing, so its fresh id on recovery is harmless), `g-lost-response` (raises, effect 1, `either`), `g-4xx` and `g-ordering` = 4 of 7, and fails `g-5xx-burst`, `g-slow-first` (no timeout, ends as `timeout`) and `g-hang`. Violations 0: it never re-sends inside one flush.
- **Variants** (hand-traced, Inferred):

| variant | flips | clause |
| --- | --- | --- |
| `v-no-retry` | `g-5xx-burst` | effect |
| `v-no-timeout` | `g-slow-first`, `g-hang` | time |
| `v-retry-5` | `g-5xx-persistent`, `g-hang`, `g-ordering` (Erratum 3) | requests |
| `v-batch-id-per-attempt` | `g-slow-first`, `g-lost-response` | effect (the stable identity is the batch id) |
| `v-clear-early` (buffer cleared before acceptance) | `g-5xx-persistent`, `g-ordering` | result (records r1, r2 are lost, so the collector sees fewer) |
| `v-requeue-tail` (after a failure the failed batch is re-queued behind newer records) | `g-ordering` | result |
| `v-retry-4xx` | `g-4xx` | requests |

  Every case has a flipping variant and `g-ordering` is flipped on its own by `v-requeue-tail` (RV-TA 5e/5f). A crash variant is rejected by S-2.

## 10. Telemetry (O1-O13)

Questions an operator asks, each with a named source (no new emitter beyond the strategies' own evidence, all in the single `property.json`, RV-SIM 10): how long does a fault case take (`check.cases[].duration_ms`, `start_ms`); which clause failed (`clause` in the case record, `strategy.<name>.clause` for the check-less ones); how many requests and effects (the fake's counters and key/batch-id values, no bodies); did the ratio or count move (`strategy.rework`, `strategy.no-guessing`, `strategy.simplicity`, each with its inputs so the rebuild test recomputes the rows); NA reason (`Score.reason`: `turn 2 not reached`, `turn 1 added no product lines`, `not built`, `resolver failed: ...`, `syntax error: ...`, `not built for <runner>`). Cost axes: wall per fault case; strategy wall time (`*_ms` in the evidence); resolver child wall time; tokens none. Every path degrades to NA, never to a plausible number. Nothing in this design touches `telemetry/*`.

## 11. Failure-mode analysis

| # | Mode (choice that causes it) | Disp. | Control · test |
| --- | --- | --- | --- |
| F1 | A fault case, or a clause of it, is dead (no solution can flip it) | P+D | per-variant flip test with clause (section 9 tables); every case and clause named above has a variant |
| F2 | A hidden test is red on the base only because a module is missing, or has no wrong-app fixture | P+D | `reds` per fixture; `test_<id>_every_hidden_test_has_a_wrong_app` (the union of `reds` equals the test ids); `test_<id>_each_wrong_app_turns_exactly_its_reds_red` |
| F3 | A broken exchange or crash reads as a flipped case (fail-closed) | P+D | the variant test asserts hidden tests pass, `deliverable == ran`, flipped set, deciding clause; crash variant |
| F4 | The prompt states a mechanism (a latent term) | P | latent-term scan; `test_<id>_prompt_has_no_latent_term` |
| F5 | The solution must meet a bound the prompt never gave | P | numbers in the prompt, mechanisms latent (RQ-2) |
| F6 | `rework_ratio` is gamed by duplication, a dead delegate or padding (RQ-1) | P+A | sentinel delegation test; `v-duplicate`, `v-dead-delegate`; residual R-W1 with `v-pad-turn1` |
| F7 | `verified_before_use` returns a plausible wrong 0 or 1 | P | not built in E4: NA `not built`, no producer, no test reads it (W0 rev 5) |
| F8 | A hallucinated member sits on a dead branch of the final tree and the hidden tests stay green | D | the count is the metric; `v-hallucinated`, `v-kw` keep tests green and flip the count |
| F9 | The resolver is blind to instance attributes, so the count reads 0 for a plausible wrong reason | P+A | typed receivers (section 7.1); fixtures `x = lib.C(); x.nope()` and `self.g = lib.C(); self.g.nope` count 1; residual R-N1 stated |
| F10 | The agent edits the vendored library so a guess resolves | P | pristine restore (section 7.0); `v-vendor-edit` |
| F11 | The resolver fails and the count reads 0 | P | NA with reason (R-97 condition 2); `test_hse_resolver_failure_is_na` |
| F12 | A docstring or blank line inflates `size_vs_reference` | P | section 5.1; `v-docstring` flips nothing |
| F13 | The primary is laundered through a file outside the radius | P | whole-tree `new_abstractions`/`new_dependencies` and the `outside_radius_lines` clause; `v-laundered` (clause b only), `v-laundered-class` (clause a only) |
| F14 | A line is counted by both `size_vs_reference` and the scope clause | P | one `in_radius`; partition test |
| F15 | Fake listeners of parallel cells collide | P | `listen()` binds port 0 and asserts `127.0.0.1`; X-LB's test |
| F16 | A host suspend turns a 3 s case into a `timeout` | M | HB-CHK-004; `PROPERTY_SUSPEND_GAP_S` |
| F17 | The campaign interpreter (3.14.6) differs from 3.12.10 | D | assume A1; the first discrimination run confirms |
| F18 | The agent special-cases the fake's address or the canary | A | the in-process residual of ADR-0018 Amendment 1, as S1 F13 |
| F19 | Control arm saturates or floors | D | EV-8 admission, not a design defect; RS and SM may saturate on strong models (R-L1) |
| F20 | A base's licence or contents change under a moving ref | P | 40-hex pin, `^{tree}` hash in `evidence.md`, `NOTICE.md` |
| F21 | An authored vendored library's README disagrees with its code | P | `test_ng_vendored_readme_matches_code` (inspects the documented signatures) |
| F22 | `expected` holds a placeholder when the task goes `ready` | P | section 5.3; `test_<id>_expected_is_literal_when_ready` |

## 12. Adversarial analysis (STRIDE-lite)

Trust boundaries: B7 (agent deliverable to check host; W1-F/ADR-0018), plus T1 (oracle material to agent workspace), T2 (upstream base to engine, supply chain), T3 (canary/fake data to reports).

| Threat | Boundary | Disp. | Control · negative test |
| --- | --- | --- | --- |
| S: the agent detects the check and returns canned safe replies (fault cases) | B7 | accept | residual as S1 F13; the fake's schedule is fixed but the agent cannot see it before grading |
| T: the oracle (fault schedules, hidden tests, wrong-app markers) enters the prompt or workspace | T1 | mitigate | `oracle/` is outside the base; the NG README is the task's public contract and is meant to be read; `test_<id>_no_oracle_string_in_prompt_or_task_workspace` |
| T: the agent edits the vendored library to make a guess resolve | T1 | prevent | pristine overlay before tests and resolver (section 7.0); `v-vendor-edit` |
| T: the pin moves | T2 | mitigate | 40-hex, tree hash; provenance test |
| I: a canary or record body reaches a report | T3 | transfer | `egress.task_canary`; resilience records are counts and ids, never bodies |
| D: a handler that blocks forever, a huge response | B7 | mitigate | per-case bound gives `timeout`; frame limits (W1-F) |
| D: the fake is flooded by a retry storm | B7 | mitigate | the fake counts requests, caps at 50 per case, then answers 503 and records `requests` over the bound |
| E: the resolver child imports the vendored library | B7 | prevent | the child imports only the pristine `vendor/<lib>` under `-S`, receives names not code, and runs in `procs.run`'s kill-on-close job with the `_env` allowlist; agent code is never imported (a module that writes a marker on import leaves none) |
| Supply chain: base licences | T2 | mitigate | section 2 table; `NOTICE.md` and licence copy per task |

Misuse cases as negative tests: the no-timeout, no-key, retry-5 variants (RS), the duplicate, dead delegate and padded turn 1 (RW), the vendor edit (NG), the laundered file (SM), the padded one-liner (SM, residual R-S1).

## 13. Patterns

Rungs climbed (Solution-Selection Ladder): YAGNI → reuse (`correctness.grade` through `property.hidden_tests`, `_changes`, `bench_check`, S1's variant/wrong-app tables) → stdlib (`ast`, `difflib`, `inspect`, `http.server`) → one line → minimum.

| Pattern | Where | Justification | Rejected |
| --- | --- | --- | --- |
| Strategy (W1-F `STRATEGIES`) | `rework`, `no-guessing`, `simplicity` | one property, one function; no registration in `GRADERS` (R-90 condition 4) | three graders in `GRADERS` (refused, DR-4) |
| Fake / Test Double on loopback | resilience dependency | the fault is the stimulus; fixed schedule | a mock in the deliverable's process (cannot time a socket) |
| Mutation-based test adequacy | variants and wrong-app fixtures per task | the only evidence a branch or a hidden assertion is live | trusting the naive (it flips only some branches) |
| Fail-closed oracle | broken exchange = failed case | a resilience check that errs open scores a hang as safe | NA on a broken exchange |
| Canary / Characterisation Golden | expected values | provenance by derivation, `Inferred` until a real-host run | copying a grader run |
| Ordered Decision Table | unchanged (W1-F `_classify`) | not reimplemented | handler chains |

**Simplifier's cuts accepted.** No shared probe library across the resilience tasks (`simplify:` ceiling two tasks, trigger a third). No jitter. `verified_before_use` not built. No `static` case for simplicity. Rework and simplicity numeric expectations are targets until sources exist. Rev 2 adds: no `pyproject` scan, one evidence file, one parametrised test module, no `v-key-per-attempt`/`v-retry-forever`, no `f-ok`/`g-ok`. **Patterns Expert's push accepted:** predicates accept sets of correct behaviours (`expect`), and a second correct solution (`alt`) is required per task (`test_<id>_an_alternative_correct_solution_passes`).

## 14. W1-I lessons, applied

| Lesson | Where |
| --- | --- |
| every hidden test has wrong-app fixtures | sections 6.2, 6.3, 7.3, 7.4, 8.2, 8.3, 9.2, 9.3; `reds` sweep test (section 15) |
| the variant-flip test asserts tests pass, `deliverable == ran`, flipped set, deciding clause | section 9 tables; section 15 |
| every probe, case, clause and metric has a flipping variant | sections 6.2, 7.3, 8.2 (each metric and both launder halves), 9.2, 9.3 |
| expected values are Inferred until the real host reproduces them; `ready` needs a real-host discrimination record | section 5.3 |
| builds are declared offline | section 5.2 |
| MIT/Apache bases at a 40-hex pin with the tree hash | section 2; provenance test |

## 15. Test plan (by node id; red first)

**Files.** One parametrised module `tests/test_property_tasks.py` over the eight ids (RV-SIM 8), with per-property fixtures in `tests/fixtures/property_tasks/`; strategy tests in `tests/test_grade_rework.py`, `test_grade_noguess.py`, `test_grade_diffstats.py`, and `tests/test_changes_lines.py` for the `_changes` four. Cut from rev 1: `hidden_tests_fail_on_stub_pass_on_both_solutions` (it duplicated the wrong-app row), the per-task `real_host_reproduces_expected` (the discrimination record is that measurement; its "registration removed" mutant lives once in each strategy file), the per-task pin/NOTICE/no-build rows (folded into one `provenance` row). Directives: D0 hygiene; the Testing-Strategy union is the golden set (expected values), a negative set (variants and wrong apps), boundary pairs and a determinism test.

**Skeleton-first commits (README section 2a items 1 and 5; RV-TA 3).** A test must fail on an assertion, never an `ImportError`. So each track's first commit lands, before any test, a skeleton whose functions return out-of-range values:

| Skeleton | Owner | Contents | First failing assertion |
| --- | --- | --- | --- |
| K1 `_changes` four | X-J2, first E2 commit | `product_lines` returns `[]`, `line_delta` returns `([], [])`, `is_test_path` returns `False`, `in_radius` moved real (drift tests stay green) | `product_lines(fixture) == ["x = 1", ...]` fails on `[]` |
| K2 `grade/rework.py` | X-J2 | `measure()` returns `ratio=Decimal(-1), t1_lines=-1`; `grade()` returns NA `not built`; `STRATEGIES["rework"]` registered | ratio `== Decimal("0.5000")` fails on `-1` |
| K3 `grade/noguess.py` | X-LG | `unresolved()` returns `(-1, [])`; `STRATEGIES["no-guessing"]` registered | count `== 2` fails on `-1` |
| K4 `grade/diffstats.py` | X-LG | `measure()` returns `-1` for every field; `STRATEGIES["simplicity"]` registered | `size == Decimal("3.5000")` fails on `-1` |
| K5 task folder | each track | folder, hidden tests, `wrong_apps.py`/`variants.py` tables, the **reference tree** (so a wrong-app fixture has something to substitute into), a stub base returning a wrong value (501 for services, identity for libraries), `status: draft` | the hidden test fails on the stub by `AssertionError` |

**Floor items.** (1) Skeletons above. (2) Red fixtures named per row. (3) *Real-wiring tests beside fakes:* `test_<helper>_grade_cell_uses_registered_strategy` (rework, noguess, diffstats) drives the real `property.grade_cell` on a fixture cell and fails if the `STRATEGIES` line is removed (it reads NA `not built`); the readiness side is X-E's `test_readiness_names_metric_expected_observed`, which takes a seeded discrimination record that disagrees with `expected` and asserts HB-RDY-003 names metric, expected and observed (W1-L supplies the RW1 fixture). (4) *Adjacent-pair mutants* per row. (5) *Sweeps checked against the tree:* the latent-term scan was run on every prompt shape above and found 0 hits; the only allowlist, the stdlib set, is `sys.stdlib_module_names` (not a copy); the hidden-test sweep is `test_<id>_every_hidden_test_has_a_wrong_app`, whose counts on this design are RS1 6, RS2 5, RW1 10, RW2 9, NG1 6, NG2 6, SM1 5, SM2 5 = 52 tests, each with at least one fixture.

| Node id | Red today because (after K1-K5) | Red fixture / mutant | Ring |
| --- | --- | --- | --- |
| `test_<id>_prompt_has_no_latent_term` (8) | the scan names term and line | fixture prompt containing a latent term; delete the scan | push |
| `test_<id>_each_wrong_app_turns_exactly_its_reds_red` (8) | a fixture's failing set differs from its declared `reds` | a fixture that fails two tests or fails by `ImportError`; `wa-last` and `wa-nosubst` declare their sets | readiness |
| `test_<id>_every_hidden_test_has_a_wrong_app` (8) | the union of `reds` is missing a test id | delete one fixture | readiness |
| `test_<id>_provenance` (8) | pin not 40-hex, `evidence.md` tree hash disagrees with `git rev-parse <pin>^{tree}`, `NOTICE.md` or licence copy missing, `deliverable.build` or a network name present | fixtures: a branch name, a wrong tree hash, a missing `NOTICE.md`, `pip`/`uv`/`npm`/`http*` words (`uv` inside `uvicorn` must not hit) | push |
| `test_<id>_no_oracle_string_in_prompt_or_task_workspace` (8) | oracle constant found | fixture prompt with a schedule constant | readiness |
| `test_<id>_each_variant_flips_exactly_its_set` (8) | per variant: hidden tests pass unless the primary is the declared flip (1', R-109), `deliverable == ran`, flipped set, clause, duration band (RS) | crash variant; a `dead-case` fixture no variant flips | readiness |
| `test_<id>_an_alternative_correct_solution_passes` (8) | `alt` scores 1 | RS: reference with the key removed must fail; SM: the honest 6-line (SM1) and 9-line (SM2) solutions on the ceiling | readiness |
| `test_<id>_expected_is_literal_when_ready` (8) | a `<...>` placeholder or wrong-typed value | fixture `task.yaml` with the placeholder | push |
| `test_<id>_grading_is_deterministic` (8) | two grader runs give unequal rows (RS: three runs and one beside a busy-loop process, equal outcomes) | a variant that sleeps a random time | readiness |
| `test_rs_fault_clause_is_recorded` (RS) | the case record names `time\|requests\|effect\|result` | `v-cache-error` (clause `result`), `v-retry-4xx` (`requests`) | readiness |
| `test_rs_case_expect_sets` (RS) | a call that raises at 3 s on `f-slow-first` passes (`either`); the same on `f-5xx-burst` fails (`succeed`) | `alt-raiser` fixture | readiness |
| `test_rework_ratio_counts_replaced_and_deleted_not_added` | `\|C\|` on a 6-line fixture with 2 replaced, 1 deleted, 3 added is `3/6` | `replace_only` fixture swapping `replace` for `delete` | push |
| `test_rework_ratio_ceiling_boundary` | 10 turn-1 lines, 3 changed gives `0.3000` and passes; 4 changed gives `0.4000` and fails | mutant `<` for `<=` | push |
| `test_rework_turn2_not_reached_is_na_and_primary_zero` | final tree absent turn 2 | fixture cell ended in turn 1 | push |
| `test_rework_duplicate_and_dead_delegate_fail_by_test` (RW1, RW2) | `v-duplicate` and `v-dead-delegate` fail T2-5 (sentinel) or T2-6, not by ratio | reference with ratio 0 and no delegation | readiness |
| `test_rework_pad_turn1_is_the_named_residual` | `v-pad-turn1` scores 1 with a ratio below the reference's | the report line R-W1 is present | readiness |
| `test_changes_line_delta_pair` | `replace` is in both `added` and `removed`; `delete` only in `removed` | swap the two opcodes | push |
| `test_noguess_resolver_counts_distinct_unresolved_names` | `from quotakit import A, B` gives 2; `getattr` form gives 0; `x = lib.C(); x.nope()` gives 1; `self.g = lib.C(); self.g.nope` gives 1; an annotated parameter gives 1; a documented `self.attr` gives 0 | fixture trees; agent code never imported (a module that writes a marker on import leaves none) | push |
| `test_hse_resolver_failure_is_na` | a child that cannot import, times out, or answers malformed gives NA with the first stderr line; a syntax error gives NA `syntax error: <path>` | fixtures; mutant returns 0 | push |
| `test_noguess_uses_pristine_vendor` | `v-vendor-edit` count stays 1 | mutant resolving against the agent copy reads 0 | readiness |
| `test_noguess_compiled_runner_is_na_not_built` | a task with a compiled `runner` scores NA `not built for <runner>` | mutant returns 0 | push |
| `test_ng_verified_before_use_is_na_not_built` | both expected roles and every cell read NA `not built` | a fixture trajectory with a `cat vendor/...` shell row still reads NA | push |
| `test_sm_product_lines_ignore_blank_comment_docstring` | `v-docstring` flips nothing | fixture file with 6-line docstring | push |
| `test_sm_each_metric_and_clause_has_a_flipping_variant` | `v-bloat`, `v-class`, `v-dep`, `v-laundered`, `v-laundered-class` each flip exactly one clause | drop clause (b): `v-laundered` passes; count classes in the radius only: `v-laundered-class` passes | readiness |
| `test_sm_ceiling_boundary_pairs` | `size == 3.0000` passes and `3.5000` fails; abstractions 0 passes and 1 fails; `outside_radius_lines` 4 passes and 5 fails | mutant `<` for `<=` | push |
| `test_sm_abstractions_counts_classdef_once` | `class P(Protocol)` counts 1; a moved class is new | mutant adds a second count for the base | push |
| `test_sm_radius_partition_counts_each_line_once` | an in-radius file feeds `size_vs_reference` only, an outside one the scope clause only | `in_radius` swapped: a line counted twice | push |
| `test_sm_frozen_reference_size_equals_function_output` | `size_reference_lines` equals `line_delta` over the committed reference diff | a hand-edited value | readiness |
| `test_<helper>_grade_cell_uses_registered_strategy` (3) | the `STRATEGIES` line removed gives NA `not built` | remove the line | push |
| `test_ng_vendored_readme_matches_code` | documented signatures equal `inspect` | README with a renamed member | push |

**W0 trace.** Section 1 ids/budget: BOM check (X-A1). Section 2 fields and `expected`: the `expected` blocks and the section 5.3 gate. Section 3 cases/`measures`/truth table/outcomes: W1-F's tests plus section 9.1. Section 7 metric ids: W1-G. ADR-0015 section 8 `graded_snapshots`: the `rework` tests. EV-1..EV-7 mapped in section 17.

## 16. Seam requests and decisions

| id | to | state | ask | what this design does |
| --- | --- | --- | --- | --- |
| `req-01M41GWMCQDK3724G8CZ2VR40M` (SR-L1) | `coord-opus-e1e4` | **refused as asked, deferred** (W0 rev 5) | `ToolCall.target` | `verified_before_use` is NA `not built` (section 7.2) |
| `req-01M41GWMT35CEXNPNZXMYD9KP0` (SR-L2) | `coord-opus-e1e4` | **granted** (W0 rev 5) | loopback with a client `app`, `{fake_url}` | section 9.1 |
| `req-01M41GWNS06F362RJ78XB7AXY5` (DR-L1) | `owner-fable` | **ruled R-97**: A granted, B refused | `hallucinated_symbol_errors` meaning | section 7.1; EV-5 note appended by this revision |
| `req-01M41H679VVB248H3XANMY1PKN` (SR-L3) | `coord-opus-e1e4` | **granted** (W0 rev 5) | `config.CHECK_PROPERTIES`, check-less tasks have no check, README amended | section 5.2 |
| SR-L4 (RV-PAT 1, RV-SIM 3) | Leader | **granted** (W0 rev 5, section 13) | `product_lines`, `in_radius` in `_changes.py`, X-J2's first E2 commit | sections 3, 4 |
| `req-01M41MWN4RJHW0XPG2R5X1QHSM` (SR-L5) | `coord-opus-e1e4` | **open** | W1-F additions: `property.hidden_tests(inp, tree, label, overlay=None)`, `property.write_section`, the check-less sentence in section 5.7, `procs.run` for the resolver child; the three `STRATEGIES` lines | sections 3, 7.0, 7.1, 8.1 stay provisional on it; fallback: the helpers own their primary and call W1-F's phase 1 as written |
| `req-01M41MWN84V40RJXYE2NA6KR8M` (SR-L6) | `coord-opus-e1e4` | **open** | `_changes.line_delta` and `_changes.is_test_path` in X-J2's first E2 commit | sections 3, 5.1; fallback: `rework` and `diffstats` each call difflib (two definitions, named as such) |

**Decisions made here (reversible by editing a task):** D1 eight distinct bases, humanize and python-slugify rejected (G8). D2 numbers in prompts, mechanisms latent (RQ-2). D3 product-line rule (section 5.1). D4 rework turn-2 prompts force a change to the turn-1 entry point and are asserted by a sentinel (RQ-1). D5 simplicity has no check process. D6 NG hallucination count is the final-tree static one with typed receivers (R-97). D7 resilience cases declare `expect` and `final`. D8 the simplicity primary counts the whole non-test tree and adds `outside_radius_lines` (W0 rev 5).

### Erratum 1 (Coordinator #7, W0 rev 6.6; RV-TA rev 2 R2-1..R2-8)

Applied here so the task authors start from text that meets W0. W0 rev 6.6 wins where this design differs.
- **SR-L5, SR-L6 are no longer open** (`docs/coordination/eval-wave2-e1/README.md` §8): SR-L5 is an E4 follow-on of the E4 owner of `grade/property.py` and `bench_check.py` (X-LB); SR-L6 is granted and entered in W0 §13 (rev 6.6).
- **R2-1 (names and carrier).** Every variant name drops `v-` and its hyphens (`v-no-retry` → `noretry`), except `v-batch-id-per-attempt` → `batchidattempt` and `v-hallucinated-member` → `hallucmember`. Section 8.2's laundering pair is renamed: this design's `v-laundered` (clause b) → **`launderlines`**, `v-laundered-class` (clause a) → **`launderclass`**; both old names are withdrawn in W0 too. `oracle/variants.py` is W0 §2's one `VARIANTS` literal `{name: {flips, clauses, edits}}`, not a `(file, old, new)` table; for a check-less task `flips` lists metric ids. A new file or a whole-file replacement (`launderlines`, `duplicate` where it adds a file, `vendoredit`) uses the create form `{"file", "old": "", "new"}`; a rework variant prefixes `edits[].file` with `turn-<n>/`. Each task track adds a test that loads its `variants.py` through W1-E's reader.
- **R2-2, R2-3 (test paths).** Section 5.1's `is_test_path` becomes W0 rev 6.6's `is_test_path(path, base_paths)`: test basenames are `test_*.py`, `*_test.py`, `tests.py`, `test.py`, `conftest.py`; a file under a `tests`/`test` directory counts as test only if the base tree already has it. So RW1's `humanfriendly/tests.py` is a test path, and new product code in `tinydb/tests/_first.py` is counted. SM1 adds **`laundertest`** (clause `scope`). Each task track asserts its own base's test layout in a fixture.
- **R2-4 (multi-turn readiness).** X-J2 owns the multi-turn discrimination path in E2 (W0 §13 rev 6.6). RW1 and RW2 stay `draft` until X-J2 joins. RS needs no new discriminate code: the check runs the loopback fake behind the same `PropertyCheck` (Inferred; X-LB's discrimination test confirms it). Floor item 3 cites W1-E **T-E11/T-E12** (HB-RDY-003), not `test_readiness_names_metric_expected_observed`, which does not exist; its seeded-disagreement fixture is a single-turn NG task (X-NG) until X-J2 joins, then RW1 (X-RW).
- **R2-5 (`cacheerror`), R2-6 (`g-ordering`).** X-RS's first commit: state the isolation (a fresh process per hidden test and per case, or a flag that H-3/H-4 cannot set) and write `g-ordering`'s schedule, then re-trace the seven RS2 rows. The first variant run is the measurement.
- **R2-7, R2-8.** Each task track: one stub per task that returns a unique sentinel, and `test_<id>_stub_fails_every_hidden_test`; section 15's column reads "green on landing; red fixture X" where that is the truth. X-NG: one sentence per NG task, the same rule for both (the primary is the hidden tests only, or `ceilings.hallucinated_symbol_errors: 0`), and the primary's value in the `hallucinated` row.

### Erratum 2 (Coordinator #8, W0 rev 6.7; X-SM's findings, `req-01M41RY339MV3Y56RQ1BKMPFCW`)

X-SM found these while authoring SM1 and SM2. W0 rev 6.7 wins where this design differs.
- **`launderlines` carrier (W0 rev 6.7 §7).** `flips: [property_check_pass, size_vs_reference]`, `clauses: {property_check_pass: scope}`. Its 3 in-radius lines give `size_vs_reference` `1.5000` (SM1) and `1.3333` (SM2), not the reference's `1.0000`, so section 2's rule (every metric id that differs) names both. Section 8.2's "only `outside_radius_lines` fails" holds for clauses. In section 15, `test_sm_each_metric_and_clause_has_a_flipping_variant` reads "each fails exactly one clause"; each variant's `flips` is its full differing set.
- **`launderclass` (W0 rev 6.6 §7).** Two classes in 2 outside lines, not section 8.2's one empty `class _Marker`. The whole-tree `new_abstractions` is 2; only clause (a) fails; the 2 outside lines are within the allowance of 4.
- **SM2's latent terms.** SM2's prompt names the `options` parameter, so the bare term `option` matches its own prompt. Section 15's floor item (5) ("0 hits") was false for SM2. SM2 replaces `option` with `extra option` and `new option`; SM1 keeps `option` (its prompt has no match).
- **Residual R-S2: a test helper under a test directory.** Under `is_test_path` (W0 rev 6.6, R6.6b), a new `tests/_helpers.py` that is not in the base tree is a product file. Its lines count against `outside_radius_lines: 4`, and a class in it counts against `new_abstractions`. So an honest solution that moves test scaffolding into a helper can score `property_check_pass` 0. Accepted as a residual, not changed: both prompts name the one test file to write, this is the price of `laundertest` (R2-3), and a change to `is_test_path` changes R6.6b, which is a decision request to the Owner. *Confirm:* assume A5's `alt` runs; a measured honest solution that fails only through a test-directory helper reopens it.

### Erratum 3 (Coordinator #46, 2026-10-06; X-RS's RS2 evidence, `build/eval-x-rs:tasks/RS2/oracle/evidence.md`)

- **`retry5` also flips `g-ordering`, on clause `requests`.** Section 9.3's `v-retry-5` row (now `retry5`, R2-1) should read: flips `g-5xx-persistent`, `g-hang`, `g-ordering`; clause `requests`. Under the R2-6 schedule (`g-ordering`'s first flush is answered 503 until the check clears the fault), `retry5` sends 5 requests and fails `requests <= 3`. Measured on the real probe host with the stand-in listener, all seven RS2 rows as re-traced (X-RS part 5, `c44c11e5`). `requeuetail` still flips `g-ordering` alone, on `result`, so RV-TA 5e/5f hold.
- **The lost-response-then-grow residual is open, not settled here.** A response lost in one flush, then a new record, then a second flush: the reference keeps the batch id and sends the grown batch, so a collector that applied the first batch drops the new record. Section 9.3's prompt ("sends the buffered records in one batch") and latent requirement ("stable across its retries ... each record once") cannot both hold in that schedule. Decision request `req-01M4966TTSM5ADZ41AFE6SX8S9` to `owner-fable`; until it is ruled, RS2 keeps its seven cases and the residual is stated in its evidence (`c46.md` item 3).

## 17. Conformance, residuals and "Done when" met

- **Assume A1.** The behaviours of sections 6-9 hold on CPython 3.14.6. *Confirm:* the first discrimination run on the pinned interpreter. *Breaks if false:* readiness fails (HB-RDY-003).
- **Assume A2.** The section 8 line counts follow `product_lines`. *Confirm:* the stand-in run of the committed reference and naive before the task is `ready`. *Breaks if false:* the frozen value or a ceiling is re-derived.
- **Assume A3.** Hidden tests may use loopback sockets in the grading copy (RS1/RS2 tests use `http.server` on `127.0.0.1`). *Confirm:* a stub-and-reference run under the real `correctness.grade`. *Breaks if false:* the RS hidden tests move to a stdlib `unittest.mock` of `urlopen`.
- **Assume A4.** jmespath's `Parser.parse` is the method `compile` calls and is called once per `compile` regardless of its cache. *Confirm:* `wa-reparse` turns M-4 red and the reference does not. *Breaks if false:* M-4 wraps the right method (a one-line edit).
- **Assume A5.** `outside_radius_lines: 4` leaves an honest solution passing. *Confirm:* the `alt` solutions. *Breaks if false:* raise it with the evidence of the honest solution that touched a second file.
- **Residuals.** R-W1 duplication and padding (RQ-1, section 6.1). R-S1 line padding. R-L1 saturation (EV-8). R-N1 the resolver is an under-count: dynamic access and untyped receivers are invisible, and a deliverable that reimplements the library reads 0 (section 7.1). R-X1 two bases per property are two samples of the property (spec R-E1).
- **Not verified here:** every reference, naive and alt solution, every variant trace, every expected value (no run exists; all `Inferred`), the loopback fake, CPython 3.14.6, `readiness.py`, the strategy helpers.

| "Done when" item | Where |
| --- | --- |
| Gate PASS | [Gate record](#gate-record) (rev 2 pending RV-TA) |
| base codebase, eight tasks | section 2 table, sections 6-9 per task |
| latent requirement, eight tasks | sections 6.2, 6.3, 7.3, 7.4, 8.2, 8.3, 9.2, 9.3 |
| hidden check, eight tasks | tests plus cases/strategy per task; sections 6.1, 7.1, 8.1, 9.1 |
| reference and naive | per task; shapes, with exact source for SM1/SM2 reference; `alt` per task |
| expected values | per task `expected` blocks; blocked numbers B-RW1, B-RW2, B-SM1, B-SM2, gated by section 5.3 |
| which graders are new | `rework.py` (`rework_ratio`, `turn1_tests_pass`), `noguess.py` (`hallucinated_symbol_errors`; `verified_before_use` not built), `diffstats.py` (`size_vs_reference`, `new_abstractions`, `new_dependencies`, the scope clause), the `resilience` strategy (W1-F's line): sections 6.1, 7.1, 7.2, 8.1, 9.1 |

## 18. Change-surface list (E7)

| Layer | Item | Owner |
| --- | --- | --- |
| store | `bench/bom.yaml`: the eight entries (status, base) | X-RW, X-RS, X-NG, X-SM (own entry each) |
| model | `tasks/<ID>/task.yaml`, `prompt.md`, `turns/2.md`, `tests/**`, `workspace/**` (overlay, pristine `vendor/**`), `NOTICE.md`, licence copy | the owning track |
| service | `oracle/check/{check.py,cases.yaml}` (RS only; none for RW, NG, SM), `oracle/solutions/{reference,naive,alt}/**`, `oracle/variants.py`, `oracle/wrong_apps.py`, `oracle/evidence.md` | the owning track |
| service | `grade/_changes.py` (`product_lines`, `in_radius`, `line_delta`, `is_test_path`), `grade/drift.py` (one hunk: import `in_radius`) | X-J2, first E2 commit (SR-L4, SR-L6) |
| service | `grade/rework.py` (E2), `grade/noguess.py` and its resolver child, `grade/diffstats.py` (E4), the three `STRATEGIES` lines in `grade/property.py` | X-J2, X-LG |
| service | `property.hidden_tests`, `property.write_section`, the check-less sentence in W1-F section 5.7 | X-F (SR-L5) |
| projection / wire | none new; `cases.json` is the grader's (W1-F); `property.json` gains `strategy.*` sections | X-F |
| client type / UI | none | none |
| compute reader | `readiness.py` (HB-RDY-003/005; `CHECK_PROPERTIES` rule, SR-L3), the discrimination record | X-E |
| catalog | `anchor_note` of `hallucinated_symbol_errors` drops "build-log errors" (R-97 condition 3) | X-G1 |
| spec | `docs/specs/enterprise-evaluation.md` EV-5 note (this revision) | W1-L |
| telemetry | none (SR-L1 refused) | none |
| evidence | `oracle/evidence.md`: pin trees, per-case and per-variant outcomes and clauses, stand-in counts | the owning track |

## Status and next action

| Item | State |
| --- | --- |
| Eight tasks: base, pin, licence, latent requirement, prompt shape, hidden tests, fixtures, variants | done in rev 1; rev 2 completes fixtures (52 of 52 tests) and re-traces the RS variants |
| Expected values | primary and integer metrics derived; `rework_ratio` (RW1, RW2) and naive `size_vs_reference` (SM1, SM2) are B-RW1, B-RW2, B-SM1, B-SM2, gated by section 5.3 |
| Rev 2 inputs | W0 rev 5, R-97, the three first-round reviews (all rows in Review disposition) |
| Open requests | SR-L5 `req-01M41MWN4RJHW0XPG2R5X1QHSM`, SR-L6 `req-01M41MWN84V40RJXYE2NA6KR8M` |
| Spikes not run | stand-in count of rework and size (A2), the fault timings, the loopback fake, the jmespath parse method (A4) |
| Reviews | rev 2 pending RV-TA (hard veto) |

## Review disposition

Every finding of the three first-round reviews (`docs/design/reviews/eval-review-{ta,pat,sim}-w1l.md`), plus the W0 rev 5 rulings this revision answers. **Applied** = changed in this doc; **ruled** = answered by W0 rev 5 or an Owner ruling and conformed to; **seam** = sent to the Coordinator; **declined** = with the reason.

| Review | # | Sev. | Disposition | Where |
| --- | --- | --- | --- | --- |
| RV-TA | 1 | blocking | **ruled** (W0 rev 5 section 7) and applied: whole-tree `new_abstractions`/`new_dependencies`, `outside_radius_lines` clause; `v-laundered` (clause b only) and `v-laundered-class` (clause a only) separate the two (RV-SIM's note) | 2, 8.1, 8.2, 11 F13, 15 |
| RV-TA | 2 | blocking | **ruled** (SR-L1 refused, W0 rev 5): `verified_before_use` NA `not built`; predicate and `test_vbu_*` deleted | 7.2, 11 F7, 15 |
| RV-TA | 3 | blocking | **applied**: skeleton commits K1-K5 for the helpers and `_changes`, the reference lands with the task skeleton; the readiness-row fixture is X-E's named test | 15 |
| RV-TA | 4 | blocking | **applied**: 14 unguarded tests now have fixtures; `reds` per fixture; `wa-last`/`wa-nosubst` declare their sets; sweep test; 52 of 52 | 3, 6-9, 15 |
| RV-TA | 5 | major | **applied**: variants re-traced by hand; `v-attempt-3s` flips `f-hang`, `f-recover`; `final` gives `requests == 1`; `v-cache-error` for the `result` clause; `v-key-per-attempt` dropped (the fake records key values, no input separated it); `v-clear-early` set corrected; `v-requeue-tail` flips `g-ordering` alone | 9.1-9.3 |
| RV-TA | 6 | major | **applied**: typed receivers (locals, `self.attr`, annotated parameters), documented instance attributes resolved, under-count restated (R-N1); variants use only visible names | 7.1, 7.3, 7.4, 15 |
| RV-TA | 7 | major | **applied**: sentinel `is` assertion, `v-dead-delegate`, T2-6 return-value pause for RW2, `v-pad-turn1` as named residual R-W1, naive ratio a target not a guarantee | 6.1-6.3 |
| RV-TA | 8 | major | **applied**: `draft` until the discrimination record reproduces `expected`; placeholder refused; B-items gated; `verified_before_use` may not feed a verdict | 5.3, 15 |
| RV-TA | 9 | major | **applied**: boundary pairs per ceiling, alternative-correct solutions for all eight, determinism rows; NA precedence moot (metric not built) | 8.2, 8.3, 9.1, 15 |
| RV-TA | 10 | minor | **applied**: `ClassDef` nodes only, `Protocol` counts 1 | 8.1, 15 |
| RV-TA | 11 | minor | **applied**: "differs at 1.2" | 7.3 |
| RV-TA | 12 | minor | **applied**: reference `1.0000` labelled a tautology | 8.2 |
| RV-TA | 13 | minor | **applied**: M-4 wraps `Parser.parse`, `wa-reparse` is its red fixture, assume A4 | 8.3, 17 |
| RV-PAT | 1 | major | **ruled** (SR-L4 granted) and applied: `product_lines`, `in_radius` in X-J2's first E2 commit; RW1 stays E2; `diffstats` imports | 3, 4 |
| RV-PAT | 2 | major | **applied**: pristine `vendor/` restored before tests and resolver; `v-vendor-edit` | 7.0, 7.3, 12 |
| RV-PAT | 3 | major | **applied**: `expect: succeed\|fail\|either` and `final` per case; slow-first is `either` (`effects <= 1`) | 9.1-9.3 |
| RV-PAT | 4 | major | **applied** and **seam** (SR-L5): the three `STRATEGIES` lines and keys, one `property.json` with `strategy.*` sections, the check-less primary and ceilings clause, the resolver spawn through `procs.run` | 3, 16 |
| RV-PAT | 5 | minor | **ruled** (R-97 condition 3): X-G1 edits the `anchor_note`; carried in E7 | 7.1, 18 |
| RV-PAT | 6 | minor | **ruled** (SR-L3 granted, README amended by W0 rev 5) | 5.2, 16 |
| RV-PAT | 7 | minor | **applied**: the `^{tree}` fixture in the provenance row | 15 |
| RV-SIM | 1 | major | **ruled** (SR-L1 refused): see RV-TA 2 | 7.2 |
| RV-SIM | 2 | major | **declined in part, settled by R-97**: the Owner's ruling keeps the keyword rule and `v-kw` in the discrimination record, so the resolver stays, trimmed to what R-97 names; no longer provisional on DR-L1 | 7.1 |
| RV-SIM | 3 | major | **ruled** (SR-L4) and applied; SR-L6 asks for `line_delta`/`is_test_path` in the same commit | 3, 4, 16 |
| RV-SIM | 4 | major | **applied**: `f-ok`, `g-ok` dropped, `g-ordering` kept with `v-requeue-tail`, `v-no-retry` added | 9.2, 9.3 |
| RV-SIM | 5 | minor | **applied**: `f-recover` kept (it carries the `result` clause via `v-cache-error`); `v-key-per-attempt` and `v-retry-forever` cut | 9.2 |
| RV-SIM | 6 | minor | **applied**: set difference against stdlib and the package; no `pyproject` scan | 8.1 |
| RV-SIM | 7 | minor | **applied**: the docstring-rule reason stated | 5.1 |
| RV-SIM | 8 | major | **applied**: one parametrised module; `hidden_tests_fail_on_stub` and per-task `real_host_reproduces_expected` cut; pin/NOTICE/no-build folded into one `provenance` row in the same module (not into X-E: readiness rules are W0's list and adding them is a W0 change) | 15 |
| RV-SIM | 9 | minor | **applied**: section 9 marked provisional (SP-LB, X-LB); RW1 and pins firm | 4, 9 |
| RV-SIM | 10 | minor | **applied**: one `property.json` | 3, 10 |
| RV-SIM | 11 | minor | **applied** as a note: later reuse across properties allowed; no rework | 2 |
| RV-SIM | 12 | minor | **applied**: one result object per tree | 6.1 |
| W0 rev 5 | SR-L1..L4, R-97 | rulings | conformed; the EV-5 note is appended under EV-5 in `docs/specs/enterprise-evaluation.md` (R-97) | 2, 7.1, 16 |

## Gate record

| lens | reviewer | status | line |
| --- | --- | --- | --- |
| Patterns Expert | RV-PAT | PASS WITH CONDITIONS (round 1; conditions applied in rev 2) | `GATE W1-L · Patterns Expert · PASS WITH CONDITIONS · 7 findings (rv-pat-w1l-e1e4, 2026-10-03)` |
| Simplifier (soft veto) | RV-SIM | PASS WITH CONDITIONS (round 1; conditions applied in rev 2) | `GATE W1-L · Simplifier · PASS WITH CONDITIONS · 12 findings (rv-sim-w1l-e1e4, 2026-10-03)` |
| Test Architect (**hard veto**) | RV-TA | BLOCK (round 1); rev 2 pending RV-TA | `GATE W1-L · Test Architect · BLOCK · 13 findings (rv-ta-w1l-e1e4, 2026-10-03)` |

rev 2 pending RV-TA
