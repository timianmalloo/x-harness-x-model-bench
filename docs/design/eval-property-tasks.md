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
  with wrong-app fixtures, the check or strategy, reference and naive shapes, expected values with provenance (marked
  Inferred until the real host reproduces them), and the seeded-defect variants that flip each probe or metric. Three
  graders are new and specified: noguess (verified_before_use, hallucinated_symbol_errors), diffstats
  (size_vs_reference, new_abstractions, new_dependencies) and rework (rework_ratio, turn1_tests_pass). Grounding
  finding: the tool-call record carries no arguments, so verified_before_use cannot be computed today (seam SR-L1);
  and EV-5's "build-log errors" has no source (Owner request DR-L1). Gate pending RV-PAT, RV-SIM, RV-TA.
---

# Design W1-L: the remaining property tasks

**Status:** proposed, revision 1, gate pending ([Gate record](#gate-record)). **Author:** W1-L, session `w1l-tasks-e1e4` (Claude Sonnet 5.5, `claude-sonnet-5-5`). **Grounded at:** `main` `d47965b1` (W0 revision 3). **Authored later by:** X-RW (RW1 in E2, RW2 in E4), X-RS, X-NG, X-SM (E4). No task file is written in this slice. **Dispatch note:** one dispatch covered all eight tasks and reached its token budget; what remains is in [Status](#status-and-next-action).

## 1. Responsibility and boundaries

**One responsibility.** Specify eight property tasks so that their authors can write them without asking a question, and so that each task's hidden check decides its property mechanically. W1-I's S1/S2 design is the pattern; the lessons its reviews forced are applied here (§14).

| It owns | It borrows by identity |
| --- | --- |
| the eight bases, pins, overlays, prompts, latent requirements | W0 §2 `task.yaml` fields, §3 the check contract, §7 the metric ids |
| hidden tests, wrong-app fixtures, cases, variants, expected values | W1-F: `property.grade_cell`, `STRATEGIES`, `bench_check`, the classification order |
| the specification of three new strategy helpers (`rework.py`, `noguess.py`, `diffstats.py`) | W1-G / X-G1: the eleven metric ids (catalog 0.7) |
| the seam and decision requests of §16 | X-E: `readiness.py`, the discrimination record; X-LB: loopback, fault kind |

**Out of scope.** Writing `tasks/**`, the runner, the loopback fake (X-LB), any code. S1/S2 (W1-I).

## 2. Grounding

Labels: **Verified** = read or run by this slice. **Inferred** = reasoned; the confirming check is named.

| # | Fact | Source | Label |
| --- | --- | --- | --- |
| G1 | `ToolCall` is `{native_ordinal, name, tool_class (shell\|edit\|read\|other), start, end, ok, outcome_code}`; the `tool_call` row adds nothing. **No argument, path or output is extracted.** `process.py` says "command text is not extracted"; `drift.py` says "read targets not in the tool record (no arguments extracted)". | `telemetry/__init__.py:61-69`, `normalize.py:176-181`, `grade/process.py:7-9`, `grade/drift.py:43-46` | Verified |
| G2 | A discrimination cell is a synthetic cell built from the oracle solution trees (EV-7), so it has **no trajectory**: `verified_before_use` is NA there. | EV-7 (read); W0 §2 | Verified (text) |
| G3 | `scope_creep` counts lines added plus deleted in files **outside** `blast_radius` (`drift._in_radius`, `drift.py` `_measure`). Lines are counted with difflib over CRLF-normalised bytes (`drift._diff`). | `grade/drift.py` (read) | Verified |
| G4 | `_changes.change_set(before, after)` returns `path -> added\|changed\|deleted`, build output excluded, CRLF normalised. | `grade/_changes.py:167-182` | Verified |
| G5 | Rework needs two graded trees: the final tree and the snapshot named in `graded_snapshots: [turn-1]`; each reaches `correctness.grade` (R-90 c2). | ADR-0015 §8; W0 §3 | Verified (text) |
| G6 | Not built in E1: `loopback`, `kind: fault`, `kind: static`, the `resilience` strategy, `fault_suite_pass`, `idempotency_violations`, `rework`, `noguess`, `diffstats`. A task that declares one is NA `not built` for every metric. | W1-F §4 (read) | Verified (text) |
| G7 | W0 `measures` carries only non-derivable ids; resilience: `idempotency_violations`. `fault_suite_pass` = passed fault cases ÷ fault cases is the grader's. | W0 §3 (read) | Verified (text) |
| G8 | Eight candidate bases (below) have licence files, a full 40-hex HEAD at 2026-10-03, and import under `python -S` with no site-packages (CPython 3.12.10). `humanize` fails (`humanize._version` is generated by the build) and `python-slugify` fails (`text_unidecode` is third party): both rejected. | SP-L1 | Verified (3.12.10); **Inferred** for 3.14.6 |
| G9 | The authoring host has only CPython 3.12.10; the campaign pins 3.14.6. | `python --version` | Verified |

| task | base (repo @ commit) | licence (file) | `-S` import (SP-L1) |
| --- | --- | --- | --- |
| RS1 | `prometheus/client_python` @ `9cd073cb4dc6ee617eadf02dcdec94e0225eff0a` | Apache-2.0 (`LICENSE`, `NOTICE`) | ok |
| RS2 | `hynek/structlog` @ `91f44ae9031c80ad9c6045172f182803543ba6ba` (`src/`) | MIT OR Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`; GitHub reports NOASSERTION because it is dual) | ok |
| RW1 | `xolox/python-humanfriendly` @ `6758ac61f906cd8528682003070a57febe4ad3cf` | MIT (`LICENSE.txt`) | ok |
| RW2 | `dbader/schedule` @ `82a43db1b938d8fdf60103bd41f329e06c8d3651` | MIT (`LICENSE.txt`) | ok |
| NG1 | `tkem/cachetools` @ `3c082c654c2804b9354e4b62dbd2994f1aac464d` (`src/`) | MIT (`LICENSE`) | ok |
| NG2 | `hukkin/tomli` @ `5a77b12a7a9f052ce5a20c335d2825658f6aea52` (`src/`) | MIT (`LICENSE`) | ok |
| SM1 | `msiemens/tinydb` @ `18d73a15066a04c77f19ae9a8c03d582bd344c0d` | MIT (`LICENSE`) | ok |
| SM2 | `jmespath/jmespath.py` @ `2812594e69d43098ef60f81f4efc404c071b0418` | MIT (`LICENSE`) | ok |

Every property pair is two different codebases (DR-T1); the eight are also distinct from each other and from S1 (microdot) and S2 (bottle). The pins are `git rev-parse HEAD` of a fresh shallow clone on 2026-10-03; each task folder carries `NOTICE.md` and the upstream licence text, and `evidence.md` records the pin's `^{tree}` hash (the S1 rule).

Quoted rules this design rests on (DC-189):
- EV-3: "no call waits longer than the declared timeout plus the declared tolerance; retries per call are at most the declared maximum; no duplicate delivery produces a duplicate effect; the result is correct after the dependency recovers."
- EV-4: "`rework_ratio` = turn-1-added lines that turn 2 changed or deleted ÷ turn-1-added lines (non-test files inside the blast radius). Primary metric = 1 only when turn-2 tests pass, turn-1 tests still pass, and `rework_ratio` ≤ the task's declared ceiling."
- EV-5: "`verified_before_use` (1 when a read of the API's source or docs, or a probe run, comes before the first edit that uses the API, by tool-call order)".
- EV-6: "Primary metric = 1 only when the hidden tests pass and each value is within the task's declared ceiling." and "they are counted by the existing `scope_creep` (US-30), not by `size_vs_reference`, so one line is never counted twice."
- EV-7: "An expected value copied from a grader run is not provenance." and "A value derived by hand fails (HASH-A)" for a frozen value.

## 3. Data model (settled first)

**Bounded context.** Task authoring for property tasks, as W1-I §3. New vocabulary: *fault case* (one declared schedule against a check-owned fake, outcome `passed\|failed\|timeout`), *effect* (what the fake records as applied, once per idempotency identity), *logical call* (one caller invocation, however many requests it sends), *turn-1-added line* (a product line the base→turn-1 diff adds), *vendored API* (an authored library in the base tree, unpublished), *member* (a name reachable from it), *product line* (§5.1).

**Aggregate.** `PropertyTask`, root `tasks/<ID>/`, identified by its task version hash. **One invariant: the verdict on a solution depends only on that solution's behaviour or tree on fixed inputs, and every probe or metric branch is live, meaning some declared variant flips it and only it.** A branch no variant flips is a default result passing for evidence. Other aggregates are referenced by identity (discrimination record by `(task, task_version, identity_hash, platform)`).

**Durable representation. No new store.** Everything is a file in `tasks/<ID>/` (hashed into the task version; Type-2 by construction) or a row an existing writer writes (`scores`, `property.json`, the discrimination record). Grain table as W1-I §3, with these additions:

| Item | Grain ("one file/row is exactly one ...") | Writer | Compute reader |
| --- | --- | --- | --- |
| `oracle/check/cases.yaml` (resilience only) | one declared fault-case list at one version | X-RS | grader (`cases.json`), readiness |
| `oracle/fakes.py`-style schedule inside `check.py` | one fault schedule per case id | X-RS | the check |
| `turns/2.md`, `tests/turn1/`, `tests/turn2/` (rework) | one turn prompt / one turn's hidden tests | X-RW | runner (ADR-0015 §1), `correctness.grade` per tree |
| `oracle/solutions/{reference,naive}/turn-1/`, `turn-2/` (rework) | one solution tree after one turn | X-RW | synthetic cells (X-E) |
| `oracle/variants.py`, `oracle/wrong_apps.py` | `(file, old, new)` substitutions on the reference (as S1) | each author | variant tests |
| `vendor/<lib>/**` (no-guessing, in `workspace/`) | one authored library, its source and README | X-NG | the agent (readable), the resolver |
| `size_reference_lines` frozen value (simplicity) | the reference's added product lines at one version | X-SM, produced by `diffstats.product_lines` (HASH-A) | readiness (equality with the function) |

**Measures and additivity (DM9, DM7).**

| Metric | Class | Derivation (one definition) |
| --- | --- | --- |
| `fault_suite_pass` | non-additive ratio | grader: passed ÷ fault cases (W0 §3) |
| `idempotency_violations` | additive count | `measures` key from the check: logical calls whose effect count exceeds 1, summed over cases |
| `rework_ratio` | non-additive ratio | `rework.grade`: §6.1 |
| `turn1_tests_pass` | binary | `rework.grade`: `correctness.grade` on the `turn-1` snapshot, turn-1 hidden tests |
| `hallucinated_symbol_errors` | additive count | `noguess.grade`: §7.1 (provisional on DR-L1) |
| `verified_before_use` | binary | `noguess.grade`: §7.2 (provisional on SR-L1); NA without targets |
| `size_vs_reference` | non-additive ratio | `diffstats.grade`: added product lines in radius ÷ `size_reference_lines` |
| `new_abstractions`, `new_dependencies` | additive counts | `diffstats.grade`: §8.1 |

**Single definitions.** Product-line counting is one function, `diffstats.product_lines(old_lines, new_lines) -> (added: list[int], deleted: list[int])`, used by `rework` and `diffstats`. The radius test is `_changes.in_radius(path, radius)`, **moved** from `drift._in_radius` in X-LG's first E4 commit (`_changes.py` is X-LG's hub in E4, W0 §13); `drift` imports it from there. So a changed file is in exactly one of {`scope_creep`, `size_vs_reference`}, which is EV-6's "never counted twice" made structural (test `test_sm_radius_partition_counts_each_line_once`).

**Schema changes.** None. The one catalog dependency is W1-G's (the metric ids and `property:` tags). The one telemetry dependency is SR-L1 (§16).

## 4. Delivery phasing and mock-substitutable seams

| Task | Becomes ready | Needs built first |
| --- | --- | --- |
| RW1 | E2 (X-RW) | multi-turn (X-J1), `rework.py` (X-J2), `graded_snapshots` |
| RW2 | E4 | as RW1 |
| RS1, RS2 | E4 | loopback (SP-LB, X-LB), `kind: fault`, `resilience` strategy, SR-L2 |
| NG1, NG2 | E4 | `noguess.py` (X-LG), SR-L1 and DR-L1 for the full metric pair |
| SM1, SM2 | E4 | `diffstats.py` (X-LG), `_changes.in_radius` move |

**Mock-substitutable seams.** (1) `STRATEGIES[name]`: a missing helper is NA `not built` (W1-F). (2) Each helper takes its inputs as plain values (`noguess.verified_before_use(rows)`, `diffstats.measure(before, after, radius)`, `rework.measure(base, snap, final, radius)`), so X-LG and X-J2 test them on fixture trees without the runner. (3) The loopback fake is `bench_check.listen()`; X-RS develops `check.py` against a stand-in listener until X-LB lands, as X-I did with `bench_check`.

## 5. Shared contracts

### 5.1 Product lines (the one counting rule)

A *product line* of a file is a line that is not blank, not a comment-only line, and not part of a docstring (found by `ast`). Lines are CRLF-normalised and compared by difflib, as `drift._diff`. Rationale: a docstring or a blank line must not make an honest solution look larger than a three-line reference (SM2 below). *Residual:* a minimal solution can be padded with code on one line (`a; b`); the metric counts lines, not tokens, and the ceilings (§8) are set with that slack. **Inferred:** the exact counts of §8 until the stand-in run of the committed reference (assume A2).

### 5.2 `task.yaml` common fields

```yaml
schema: bench-task/1
scenario: 5
source: { kind: authored, upstream: "harness-bench property task on <repo>", repo: "<url>", commit: "<40-hex>", workspace_from: source, license: "<spdx>" }
language: python
graders: [correctness, property]          # R-90
property: { name: <one of 5>, latent_requirement: "<one sentence>", evidence_paths: [...], latent_terms: [...], primary_metric: property_check_pass, ceilings: {...}, fault_contract: {...} }
```

`workspace_from: source` and the overlay (`tasks/<ID>/workspace/`, authored files laid over the upstream tree) follow E5 and S1. Authoring rule: the overlay holds only docs and vendored libraries the task needs; it never edits an upstream file. Offline build: **none of the eight declares `deliverable.build`**; the probe host and the correctness runner run `-S` with no site-packages, so a third-party import fails (`did not start`, a measured 0). The S1 test `test_<id>_declares_no_build_and_no_network_names` is reused per task (§15).

## 6. Rework tasks (RW1, RW2)

### 6.1 The strategy `rework.grade` (X-J2, E2)

Inputs: base tree, the `turn-1` snapshot, the final tree, `blast_radius`. Steps: (1) `correctness.grade` on the snapshot with the **turn-1** hidden tests, giving `turn1_tests_pass`; (2) `correctness.grade` on the final tree with turn-1 **and** turn-2 hidden tests (one run, both files); (3) for each non-test file in the radius: `T1` = product lines added by base→snapshot (`product_lines`); `C` = the members of `T1` that snapshot→final deletes or replaces (difflib opcodes `delete`/`replace` over snapshot lines); `rework_ratio = Decimal(|C|) / Decimal(|T1|)` at scale 4; `|T1| = 0` is NA `turn 1 added no product lines`; a cell that ends in turn 1 has the turn-2 metrics NA `turn 2 not reached` and `property_check_pass` 0 (EV-4). `property_check_pass = 1` iff turn-2 tests pass ∧ turn-1 tests pass on the final tree ∧ `rework_ratio ≤ ceiling`.

**Known blind spot (finding RQ-1, not a defect of the formula).** The ratio sees only turn-1 lines that turn 2 *changes*. A solution that satisfies turn 2 by adding a sibling copy leaves turn-1 untouched and scores 0.0000. So each turn-2 prompt below is written so that **any correct solution must change the turn-1 entry point** (its behaviour is asserted through a call the turn-1 function must make), and each hidden turn-2 test asserts the delegation. The naive that duplicates is therefore a test failure, not a low ratio. *Control:* variant `v-duplicate` (§6.4) must fail a turn-2 test and not merely score 0. The duplication hole is reported as residual R-W1.

### 6.2 RW1: humanfriendly, a currency formatter

- **Base/pin/licence:** §2. `blast_radius: ["humanfriendly/*.py"]` minus `tests.py` (test file). `evidence_paths: ["humanfriendly/__init__.py"]` (`format_number`, `format_size`: the module's formatter style). Budget 60 (both turns).
- **Latent requirement:** "A formatter for one currency must keep the currency's symbol, decimals and separators in data, so a second currency adds data and not code paths."
- **Latent terms** (none in `prompt.md`): `currency`, `currencies`, `locale`, `euro`, `yen`, `EUR`, `JPY`, `per-currency`, `table`, `generalis`, `generaliz`.
- **Turn 1 (`prompt.md`, shape):** "Add `format_dollars(amount)` to `humanfriendly/__init__.py`. It returns US dollars with a thousands separator and two decimals, rounded half up: `format_dollars(1234.5)` is `'$1,234.50'` and `format_dollars(-5)` is `'-$5.00'`. It accepts an int, a float, a string number or a `Decimal`. Add tests to `humanfriendly/tests.py`."
- **Turn 2 (`turns/2.md`, shape):** "Add `format_money(amount, currency)` for `'USD'` (`'$1,234.50'`), `'EUR'` (`'1.234,50 €'`) and `'JPY'` (`'¥1,235'`, no decimals, half up). An unknown code raises `ValueError`. `format_dollars(amount)` must now return `format_money(amount, 'USD')` by calling `format_money`."
- **Hidden tests, turn 1** (`tests/turn1/test_money1.py`): T1-1 `1234.5` → `'$1,234.50'`; T1-2 negative; T1-3 half-up (`0.005` → `'$0.01'`, `2.675` as str → `'$2.68'`); T1-4 `Decimal`, `str`, `int` inputs; T1-5 zero. **Turn 2** (`tests/turn2/test_money2.py`): T2-1 EUR; T2-2 JPY; T2-3 unknown code raises; T2-4 negative EUR `'-1.234,50 €'`; T2-5 `format_dollars` calls `format_money` (the test replaces `humanfriendly.format_money` with a recorder and asserts one call with `(amount, 'USD')`: this is the delegation assertion of RQ-1).
- **Wrong-app fixtures** (reference with one substitution; each must turn exactly its own test red by `AssertionError`, not by import): `wa-halfeven` (T1-3), `wa-noneg` (T1-2), `wa-str` (T1-4), `wa-jpy-decimals` (T2-2), `wa-eur-prefix` (T2-1), `wa-noraise` (T2-3), `wa-nodelegate` (`format_dollars` formats itself: T2-5).
- **Reference** (shape): a private `_CURRENCIES` table (symbol, decimals, position, group separator, decimal separator; USD only), one private `_format_money(amount, code)`, `format_dollars` calling it. Turn 2 adds the EUR and JPY rows, a public `format_money` that calls `_format_money`, and changes the one line in `format_dollars` to call `format_money`. **Naive** (shape): turn 1 one function with the `$`, two decimals and rounding inline; turn 2 rewrites it into `format_money` plus a body for `format_dollars`.
- **Expected** (provenance: **Inferred**, a by-hand reading of the shapes; the committed sources and the stand-in count of §5.1 are X-RW's, blocking item B-RW1):

```yaml
expected:
  reference: { property_check_pass: 1, turn1_tests_pass: 1, rework_ratio: "<X-RW, design target <= 0.1000>" }
  naive:     { property_check_pass: 0, turn1_tests_pass: 1, rework_ratio: "<X-RW, design target >= 0.6000>" }
ceilings: { rework_ratio: "0.3000" }
```

  The naive scores `property_check_pass` 0 because its ratio exceeds the ceiling, not because a test fails: it passes both test files (it is a correct but short-sighted design). *Blocking:* the numeric `rework_ratio` strings cannot be fixed before the two solutions exist; the design fixes the targets and the rule that X-RW writes the number from a **hand count of the committed diff**, then readiness compares it with the grader.
- **Variants flipping each branch:** `v-ratio-high` (reference with the table inlined into `format_dollars`, so turn 2 rewrites the body): flips the ratio clause and nothing else (all tests pass, `rework_ratio` above the ceiling). `v-t1-regress` (reference whose turn 2 breaks T1-3): flips the turn-1-still-passes clause. `v-t2-short` (turn 2 not implemented, final = snapshot): flips the turn-2 clause. `v-duplicate` (§6.1): fails T2-5.

### 6.3 RW2: schedule, job failure handling

- **Base/pin/licence:** §2 (`schedule/__init__.py`, ~one module; tests `test_schedule.py`). `blast_radius: ["schedule/__init__.py"]`. `evidence_paths: ["schedule/__init__.py"]` (`Scheduler.run_pending`, `Job.run`). Budget 60.
- **Latent requirement:** "A failure policy added to a scheduler must sit behind one hook, so a second policy changes the hook's listeners and not the run loop."
- **Latent terms:** `hook`, `callback`, `observer`, `listener`, `policy`, `strategy`, `extensib`, `pluggable`, `subscribe`.
- **Turn 1 (shape):** "When a job raises, `Scheduler.run_pending()` must not stop. It keeps running the other due jobs and counts the failure: after the run `job.failures` is the number of consecutive failures of that job, reset to 0 by a success."
- **Turn 2 (shape):** "Add `Scheduler.on_failure(callback)`. Every failure calls each registered callback with `(job, exception)` in registration order. A job that fails 3 times in a row is paused: it is not run again until `job.resume()`. The `failures` counter keeps working." 
- **Hidden tests** T1: other jobs run after a raising job; `failures` counts consecutive; success resets. T2: callbacks in order with `(job, exc)`; pause after 3; `resume()` re-enables; counter still correct; T2-delegation: the pause is decided by a registered callback or a hook (asserted by registering a second callback and seeing it called before the pause: the test fixes call order, which forces the loop to call a hook list). 
- **Wrong-app fixtures:** `wa-continue` (T1-1), `wa-noreset` (T1-3), `wa-order` (T2-1), `wa-pause2` (T2-3), `wa-noresume` (T2-4).
- **Reference/naive shapes:** reference turn 1 keeps the failure count in `_record_failure(job, exc)` called from the run loop; turn 2 adds the hook list and has `_record_failure` iterate it. Naive turn 1 inlines `try/except` and the counter in the run loop; turn 2 edits the same block for callbacks and pausing.
- **Expected and ceiling:** as RW1 (`ceilings.rework_ratio` `"0.3000"`; numbers are X-RW's, blocking item B-RW2).
- **Variants:** `v-ratio-high` (loop edited in place), `v-t1-regress`, `v-t2-short`, `v-nohook-order`.

## 7. No-guessing tasks (NG1, NG2) and the `noguess` strategy

### 7.1 `hallucinated_symbol_errors` (provisional on DR-L1, recommended option A)

**Option A (built in E4).** The strategy parses every `.py` file of the final tree inside `blast_radius` with `ast`, collects the *vendored-API references* it can resolve statically: names in `from <lib> import a, b`, and attribute chains `alias.x.y` rooted at an `import <lib> [as alias]`, and keyword names at call sites whose callee resolved. A resolver subprocess (`python -S`, `sys.path` = the vendored path only, **never the agent's code**) imports the real library and answers `hasattr` / `inspect.signature` for each reference. The metric is the number of distinct unresolved dotted names (a keyword is `lib.Cls.__init__:kw`). A name the agent defines itself is not a reference. *Meaning:* members that survive in the final tree. It is not the trajectory's build-log count; EV-5 says "build-log errors", and the extraction has no tool output (G1), hence DR-L1. *Residual:* dynamic access (`getattr(lib, name)`) is not seen.

### 7.2 `verified_before_use` (provisional on SR-L1)

Per EV-5: 1 when a read of the API's source or docs, or a probe run, precedes the first edit that uses the API, by `native_ordinal`. With SR-L1 each `tool_call` row has `target`. The predicate: let `E` be the first row with `tool_class == "edit"` whose `target` is in the blast radius. The read clause: a `read` row whose `target` starts with the vendored path. EV-5's probe-run clause needs command text, which SR-L1's first command word cannot carry, so it is **Not built** (a probe run alone scores as not verified). `verified_before_use = 1` iff some read of the vendored path has a smaller `native_ordinal` than `E`; no edit in the radius → NA `no edit in the blast radius`; no `target` on any row → NA `tool targets not extracted`. **It never degrades to 1:** a class-order rule (any read before any edit) is refused because it is 1 for nearly every run and would be a plausible wrong number (IO rule). Synthetic cells have no trajectory (G2), so both expected values are `{na: "synthetic cell has no trajectory"}` and the metric is exercised by fixture rows only (test `test_vbu_*`, §15).

### 7.3 NG1: cachetools plus the vendored `quotakit`

- **Base/pin/licence:** §2. Overlay `vendor/quotakit/` (authored by the task, MIT, with `README.md` that states the true contract). `blast_radius: ["src/cachetools/limiter.py", "src/cachetools/__init__.py"]`. Budget 45.
- **Vendored API (authored, unpublished).** Package `quotakit`: class **`Gate(max_per_window, window_seconds, *, clock=time.monotonic, mode="sliding")`**; method **`admit(cost=1) -> bool`**; exception **`QuotaExceeded`**. Conventional guesses, absent here: `RateLimiter(calls, period)`, `.acquire()` / `.allow()` / `.try_acquire()`, `RateLimitExceeded`, a fixed window by default. *Renamed members:* `RateLimiter`→`Gate`, `acquire`→`admit`, `RateLimitExceeded`→`QuotaExceeded`. *Changed default:* `mode="sliding"`, not a fixed window. The contract is readable in `vendor/quotakit/README.md` and `vendor/quotakit/quotakit/gate.py`.
- **Latent requirement:** "Code that uses a vendored library must read its source or documentation and use only the members and defaults that exist." **Latent terms:** `read`, `documentation`, `docs`, `README`, `source`, `signature`, `docstring`, `verify`, `check the`, `look at`.
- **Prompt (shape):** "Add `src/cachetools/limiter.py` with `limit_calls(max_calls, per_seconds, clock=None)`, a decorator that lets the function run at most `max_calls` times in any window of `per_seconds`, using the `quotakit` package in `vendor/quotakit`. When the limit is reached the call raises `cachetools.limiter.LimitExceeded`. Add tests in `tests/test_limiter.py`."
- **Hidden tests** (`tests/test_limiter_hidden.py`, with `vendor/quotakit` on `sys.path`, fake clock): N-1 allows `max_calls` calls; N-2 the next raises `LimitExceeded`; N-3 **sliding semantics** (calls at 0.0 and 0.9 of a 1.0 s window; a third at 1.05 is allowed and a fourth at 1.2 is refused: a fixed-window guess differs at 1.05); N-4 `clock=None` uses the default clock; N-5 the decorated function's result and name are preserved; N-6 `LimitExceeded` is not `quotakit.QuotaExceeded` (it is the module's own).
- **Wrong-app fixtures:** `wa-fixed-window` (N-3), `wa-no-raise` (N-2), `wa-wraps` (N-5), `wa-extra-allowed` (N-1).
- **Reference:** builds `quotakit.Gate(max_calls, per_seconds, clock=clock or time.monotonic)` and calls `gate.admit()`. **Naive** (written against the conventional contract): `from quotakit import RateLimiter, RateLimitExceeded`, `.acquire()`. The import fails, so every hidden test fails (primary 0) and the resolver finds **two** unresolved names.
- **Expected (Inferred; hand-read; the committed sources are X-NG's, the resolver counts are confirmed by the first strategy run):**

```yaml
expected:
  reference: { property_check_pass: 1, hallucinated_symbol_errors: 0, verified_before_use: { na: "synthetic cell has no trajectory" } }
  naive:     { property_check_pass: 0, hallucinated_symbol_errors: 2, verified_before_use: { na: "synthetic cell has no trajectory" } }
# naive 2: quotakit.RateLimiter and quotakit.RateLimitExceeded on one import line; each is one distinct unresolved name (§7.1).
```
- **Variants:** `v-hallucinated` (reference plus one call to `gate.try_acquire`): flips `hallucinated_symbol_errors` 0→1 and keeps the hidden tests green (the call sits on an unreached branch); `v-default` (reference that passes `mode="fixed"`; real symbols, wrong default assumption): flips N-3 and leaves the symbol count 0; `v-kw` (reference with an unknown keyword `Gate(..., period=...)`): flips the keyword rule (count 1).

### 7.4 NG2: tomli plus the vendored `envkit`

- **Base/pin/licence:** §2. Overlay `vendor/envkit/` (authored, MIT, README). `blast_radius: ["src/tomli/_interp.py", "src/tomli/__init__.py"]`. Budget 45.
- **Vendored API.** `envkit.MappingSource(mapping)`; method **`fetch(name, *, fallback=MISSING)`**; exception **`UnknownName`**. Conventional guesses: `EnvSource`, `.get(name, default=None)`, returning `None` or `""` for an unknown name. *Renamed:* `get`→`fetch`, `EnvSource`→`MappingSource`. *Changed default:* an unknown name **raises** `UnknownName` unless `fallback` is given.
- **Latent requirement / terms:** as NG1 (the same property sentence; terms identical).
- **Prompt (shape):** "Add `tomli.loads_env(text, source)` in `src/tomli/_interp.py`, exported from `tomli`. It parses TOML as `tomli.loads` does and replaces `${NAME}` in every string value (including inside arrays and tables) with the value `source` gives for `NAME`, using the `envkit` package in `vendor/envkit`. `source` is an `envkit.MappingSource`. A name `source` does not know is an error. Add tests in `tests/test_interp.py`."
- **Hidden tests:** G-1 simple substitution; G-2 nested table and array strings; G-3 an unknown name raises `envkit.UnknownName` (the changed default: the guess returns `""`); G-4 `${A}${B}` adjacency; G-5 a string with no `${}` is untouched; G-6 non-string values untouched.
- **Wrong-app fixtures:** `wa-unknown-empty` (G-3), `wa-no-nested` (G-2), `wa-int-str` (G-6).
- **Reference:** `source.fetch(name)` with the `UnknownName` propagating. **Naive:** `from envkit import EnvSource`; `source.get(name, "")`. Hallucinated names: `envkit.EnvSource`, `envkit.MappingSource.get` is not a static reference (the instance is an argument, not resolvable), so the count is **1**.
- **Expected (Inferred):** reference `{property_check_pass: 1, hallucinated_symbol_errors: 0, verified_before_use: {na: …}}`; naive `{0, 1, {na: …}}`.
- **Variants:** `v-hallucinated` (reference plus `envkit.EnvSource` reference on a dead branch → 1), `v-default-guess` (catches `UnknownName` and returns `""`: flips G-3, count 0), `v-kw` (unknown keyword).

## 8. Simplicity tasks (SM1, SM2) and the `diffstats` strategy

### 8.1 `diffstats.grade` (X-LG, E4)

For the non-test files in `blast_radius` (G3, G4): `size_vs_reference = added product lines ÷ size_reference_lines` at scale 4, where `size_reference_lines` is the reference's own added product lines, **frozen in `task.yaml` and equal to `diffstats.product_lines` applied to the committed reference diff** (HASH-A: readiness recomputes it and compares; a hand count fails). `new_abstractions` = count of new `class` definitions (any base, including `Protocol`, `ABC`, `dataclass`, `NamedTuple`, `TypedDict`) plus new `typing.Protocol`/`abc.ABC` subclasses found by `ast` on the changed files, minus those present before. `new_dependencies` = new top-level imports of a module that is neither stdlib (`sys.stdlib_module_names`), nor the package itself, nor already imported somewhere in the base tree, plus new entries in `pyproject.toml`/`setup.py` requirements. Files **outside** the radius are `scope_creep`'s and never counted here (§3, partition test). `property_check_pass = 1` iff hidden tests pass ∧ each value ≤ its ceiling. There is no `oracle/check/` for these tasks (seam SR-L3, §16: readiness accepts a strategy with no check process).

### 8.2 SM1: tinydb, `Table.first`

- **Base/pin/licence:** §2. `blast_radius: ["tinydb/table.py"]`. `evidence_paths: ["tinydb/table.py"]` (`search`, `get`, `count`, `contains` show the style). Budget 45.
- **Latent requirement:** "A small addition to a library must be the smallest code that meets the ask, with no new type, option or layer the ask never named." **Latent terms:** `minimal`, `simple`, `smallest`, `no extra`, `without adding`, `YAGNI`, `abstraction`, `configur`, `option`, `strategy`, `factory`.
- **Prompt (shape):** "Add a method `first(cond)` to `Table` in `tinydb/table.py`. It returns the first document that matches `cond`, or `None` when none matches. Add tests to `tests/test_tables.py`."
- **Hidden tests** (`tests/test_first_hidden.py`): F-1 first match in insertion order; F-2 `None` when no match; F-3 on an empty table; F-4 a query that matches several returns only the first; F-5 the returned object is a `Document` with its `doc_id`.
- **Wrong-app fixtures:** `wa-last` (F-1/F-4 pair: returns the last, so F-1 red, F-4 red), `wa-raises` (F-2), `wa-dict` (F-5).
- **Reference (exact):** `def first(self, cond): return next(iter(self.search(cond)), None)`: 2 product lines. `size_reference_lines: 2`. **Naive:** the same method plus an unrequested `FirstOptions` dataclass and a `FirstStrategy` ABC with a `ScanStrategy`: 3 new abstractions, about 25 product lines, all tests pass.
- **Ceilings:** `{size_vs_reference: "3.0000", new_abstractions: 0, new_dependencies: 0}`. (3.0000 admits a 6-line honest solution with a loop and a guard; the naive's ratio is expected near 12.)
- **Expected:** reference `{property_check_pass: 1, size_vs_reference: "1.0000", new_abstractions: 0, new_dependencies: 0}`: **derivation** `2 ÷ 2` (definitional: the reference measured against itself under one function), 0 classes in the reference source, 0 imports. Naive `{0, "<naive lines ÷ 2>", 3, 0}`: `new_abstractions` 3 by construction (three `class` statements in the committed naive); the size ratio is X-SM's hand count of the committed naive (blocking item B-SM1; design requirement: at least `6.0000`). Provenance: **Inferred** until the grader runs.
- **Variants (every metric flips):** `v-bloat` (reference plus a 5-line docstring-less helper `_first_or_none`: size 2→7, ratio `3.5000`, flips `size_vs_reference` only; shows the ceiling bites without a class); `v-class` (reference plus one empty `class _Sentinel`: flips `new_abstractions` 0→1 only); `v-dep` (reference using `import attr` in a dead branch: flips `new_dependencies` 0→1 only); `v-docstring` (reference plus a 6-line docstring: must **not** flip anything, proving §5.1's docstring rule).

### 8.3 SM2: jmespath, `search_many`

- **Base/pin/licence:** §2. `blast_radius: ["jmespath/__init__.py"]`. `evidence_paths: ["jmespath/__init__.py"]` (`compile`, `search`). Budget 45.
- **Latent requirement and terms:** as SM1.
- **Prompt (shape):** "Add `search_many(expression, documents, options=None)` to `jmespath/__init__.py`. It returns a list with the result of `jmespath.search` for each document, in order, parsing the expression once. Add tests in `tests/test_search_many.py`."
- **Hidden tests:** M-1 order and values; M-2 empty list → `[]`; M-3 `options` is passed through (a custom function table changes the result); M-4 the expression is parsed once (the test counts `Parser.parse` calls with a recorder: a naive per-document `search` fails); M-5 an invalid expression raises `ParseError` even when `documents` is empty.
- **Wrong-app fixtures:** `wa-reparse` (M-4), `wa-noopts` (M-3), `wa-lazy` (M-5; parse deferred until the first document).
- **Reference (exact, 3 product lines):** `def search_many(expression, documents, options=None): parsed = compile(expression); return [parsed.search(d, options=options) for d in documents]`. `size_reference_lines: 3`. **Naive:** the same function wrapped by `BatchConfig` (dataclass), `BatchSearcher` and a `ResultCollector` Protocol: 3 abstractions, ratio expected ≥ 8.
- **Ceilings/expected/variants:** as SM1 with `size_reference_lines: 3` (`v-bloat` here adds a helper so the total is 13 product lines: ratio `13 ÷ 3 = 4.3333`, above the 3.0000 ceiling, flips the size clause only).

## 9. Resilience tasks (RS1, RS2) and the `resilience` strategy

### 9.1 Check shape (shared)

`interface: loopback`; the **dependency is a check-owned fake** on `bench_check.listen()` (`("127.0.0.1", 0)`, asserted; ADR-0018 §3). The deliverable is a **client function**, called through the probe host (`app.kind: callable`, request `args` carry the fake's `base_url`); this combination is SR-L2. The check measures the wall time of each probe-host call and reads the fake's counters. Case `kind: fault`, outcomes `passed|failed|timeout`. `fault_suite_pass` = passed ÷ cases (grader). `idempotency_violations` = Σ over logical calls of `max(0, effects − 1)` (a `measures` key). `property_check_pass` = hidden tests ∧ `ran` ∧ every case `passed` (W0). Each fault case passes iff **all four** hold (EV-3): `duration ≤ timeout_ms + tolerance_ms`; `requests ≤ max_retries + 1`; `effects == 1` for a logical call that should succeed and `0` for one that should fail; the result after recovery is correct. The case record keeps which clause decided (`clause: time|requests|effect|result`), the variant test asserts it (S1 lesson).

`fault_contract` (both tasks): `{timeout_ms: 3000, tolerance_ms: 500, max_retries: 2}`. **Numbers are in the prompt; the mechanisms are latent** (finding RQ-2: a check cannot hold a solution to a bound it never told the author): the prompt says a call returns or raises within 3 seconds and sends at most 3 requests, and never says how.

**Case bound (RV-DS 4 lesson).** Declared per case from the designed fault, not from a reference run that does not exist yet: cases that wait for the full budget have `bound_ms: 4500` (3000 + 500 tolerance + 1000 for host start and fake setup; the host start measured 67 ms in SP-I3, Inferred for 3.14.6); quick cases omit it (interface bound). *Upgrade trigger:* X-RS measures the reference's `duration_ms` per case in the E4 spike and replaces any bound that is not at least 25 percent above the reference's slowest honest run. **Inferred.**

**Determinism.** Every schedule is a fixed list (which request number is delayed, dropped or answered 503); the seed is recorded and unused (`simplify:` no jitter; upgrade trigger: a case whose outcome depends on the order of two concurrent faults). Two ports never collide (port 0 per case).

### 9.2 RS1: prometheus_client, a ledger-event client

- **Base/pin/licence:** §2 (`prometheus_client/exposition.py` shows the base's `urllib` style). Overlay `docs/ledger-service.md`: `POST /v1/events` with JSON `{"name": str, "value": number}`; 201 `{"id": int}`; an optional header `Idempotency-Key`: a second request with the same key returns 200 and the original `id` and creates no event; 5xx may be transient; 4xx are final. `evidence_paths: ["docs/ledger-service.md", "prometheus_client/exposition.py"]`. Budget 45.
- **Latent requirement:** "A call to a remote service must bound every attempt, retry only transient failures within the stated budget, and send a stable idempotency key so a replayed request takes effect once." **Latent terms:** `timeout`, `retry`, `retries`, `backoff`, `idempot`, `dedup`, `deduplic`, `transient`, `circuit`, `jitter`, `give up`, `exactly once`.
- **Prompt (shape):** "Add `prometheus_client/ledger.py` with `post_event(base_url, name, value)`. It sends the event to `<base_url>/v1/events` as described in `docs/ledger-service.md` and returns the new event's `id` as an int. It raises `LedgerError` when the service refuses or cannot be reached. A call must return or raise within 3 seconds and must send at most 3 requests to the service. Add tests in `tests/test_ledger.py`."
- **Hidden tests** (against a stdlib `http.server` in the test, loopback): H-1 returns the `id` as int; H-2 sends a JSON body with `name` and `value`; H-3 a 400 raises `LedgerError`; H-4 connection refused raises `LedgerError`; H-5 a trailing slash on `base_url` is accepted; H-6 module import has no side effect. **Wrong-app fixtures:** `wa-id-str` (H-1), `wa-path` (H-2), `wa-swallow` (H-3), `wa-slash` (H-5), `wa-import` (H-6).
- **Cases (8):** `f-ok`; `f-5xx-burst` (503, 503, 201); `f-5xx-persistent` (all 503); `f-slow-first` (first response delayed 6 s, the effect applied); `f-hang` (never answers); `f-lost-response` (effect applied, connection closed, second request with the same key returns the stored result); `f-4xx` (400); `f-recover` (call 1 against a hung service, then the fault clears, call 2 must return the correct `id`).
- **Reference:** per-attempt timeout from the remaining budget; up to 3 requests; retry on 5xx, connection reset and timeout; never on 4xx; one `Idempotency-Key` created per call and reused across its attempts. **Naive:** plain `urlopen` with no timeout, no retry, no key (passes all six hidden tests).
- **Expected (Inferred; hand-traced by case; the fake is X-LB's, so no run exists):**

```yaml
expected:
  reference: { property_check_pass: 1, fault_suite_pass: "1.0000", idempotency_violations: 0 }
  naive:     { property_check_pass: 0, fault_suite_pass: "0.3750", idempotency_violations: 0 }
# naive passes f-ok, f-5xx-persistent (one 503, one request, raises quickly) and f-4xx = 3 of 8; it fails f-5xx-burst (raises), f-slow-first and f-hang
# (no timeout: bound -> timeout), f-lost-response (raises), f-recover (hangs). It never retries, so no call has two effects: violations 0.
```
- **Variants (each flips its named cases and clause; all hidden tests green, `deliverable == ran`):**

| variant (one substitution) | flips | clause |
| --- | --- | --- |
| `v-no-timeout` | `f-slow-first`, `f-hang`, `f-recover` | time |
| `v-attempt-3s` (3 s per attempt, no budget) | `f-slow-first`, `f-hang`, `f-recover` | time |
| `v-retry-forever` (loop until success) | `f-5xx-persistent`, `f-hang` | requests (and time) |
| `v-no-key` | `f-slow-first`, `f-lost-response` | effect (violations 2) |
| `v-key-per-attempt` | `f-slow-first`, `f-lost-response` | effect |
| `v-retry-4xx` | `f-4xx` | requests |

  `v-no-timeout` and `v-attempt-3s` flip the same set but differ on `f-ok`-adjacent timing evidence only (their `duration_ms`), so the variant test also asserts the clause **and** the maximum observed `duration_ms` band (above 3500 ms for both, equal to the bound for the first). A `crash-variant` (every call raises) flips all but `f-4xx` and `f-5xx-persistent` and is rejected by the "hidden tests pass" clause (S1 lesson).

### 9.3 RS2: structlog, a batching log shipper

- **Base/pin/licence:** §2. Overlay `docs/collector.md`: `POST /v1/logs` with `{"batch_id": str, "records": [..]}`; 200 `{"accepted": n}`; a repeated `batch_id` is accepted without applying it again; 5xx transient; 4xx final. `blast_radius: ["src/structlog/shipper.py"]`. `evidence_paths: ["docs/collector.md", "src/structlog/processors.py"]`. Budget 45.
- **Latent requirement:** "A shipper must bound every flush, keep a batch's identity stable across its retries, and keep unsent records after a failure so recovery delivers each record once." **Latent terms:** as RS1 plus `batch id`, `stable`.
- **Prompt (shape):** "Add `src/structlog/shipper.py` with `HttpShipper(base_url)`. Its `processor(logger, name, event_dict)` appends a copy of the event to an in-memory buffer and returns `event_dict` unchanged. `flush()` sends the buffered records in one batch to `<base_url>/v1/logs` as in `docs/collector.md`, empties the buffer on success and returns the number accepted. On failure `flush()` raises `ShipError` and keeps the records for the next flush. A flush must return or raise within 3 seconds and send at most 3 requests. Add tests in `tests/test_shipper.py`."
- **Hidden tests:** S-1 the processor returns `event_dict` unchanged and buffers a copy; S-2 `flush()` returns the accepted count and empties the buffer; S-3 a refused batch (400) raises `ShipError`; S-4 an empty buffer sends nothing; S-5 order is preserved. **Wrong-app fixtures:** `wa-nocopy` (S-1), `wa-keep` (S-2), `wa-ok4xx` (S-3), `wa-sendempty` (S-4), `wa-reverse` (S-5).
- **Cases (8):** `g-ok`; `g-5xx-burst`; `g-5xx-persistent` (flush raises, buffer kept; after recovery a second flush delivers all records, **applied once**); `g-slow-first`; `g-hang`; `g-lost-response` (batch applied, connection closed; the retry must reuse `batch_id`); `g-4xx`; `g-ordering` (after a failed flush and a recovery flush, the collector sees records in order).
- **Reference:** `batch_id` created when the batch is formed and kept until success; per-flush budget; retry 5xx/reset/timeout; buffer cleared only after acceptance. **Naive:** one `urlopen`, a new `batch_id` per flush, buffer kept on exception (passes the hidden tests).
- **Expected (Inferred):** reference `{1, "1.0000", 0}`; naive `{0, "0.5000", 0}` (passes `g-ok`, `g-5xx-persistent`, `g-4xx`, `g-ordering` = 4 of 8; fails burst, slow, hang, lost). Naive violations 0: it never re-sends inside one flush, and the check does not re-flush after `g-lost-response` raises.
- **Variants:** `v-no-timeout`, `v-retry-forever`, `v-batch-id-per-attempt` (flips `g-slow-first`, `g-lost-response`; effect), `v-clear-early` (buffer cleared before acceptance: flips `g-5xx-persistent`; result), `v-retry-4xx` (`g-4xx`).

## 10. Telemetry (O1-O13)

Questions an operator asks, each with a named source (no new emitter beyond the strategies' own evidence): how long does a fault case take (`check.cases[].duration_ms`, `start_ms`); which clause failed (`clause` in the case record); how many requests and effects (the fake's counters, in the evidence file, no bodies); did the ratio or count move (`property.json` metrics, `rework.json`, `diffstats.json`, `noguess.json` under the cell's `out_dir`, each with its inputs so the rebuild test recomputes the rows); NA reason (`Score.reason`: `turn 2 not reached`, `tool targets not extracted`, `no edit in the blast radius`, `turn 1 added no product lines`). Cost axes: wall per fault case; strategy wall time (`*_ms` in the evidence file); tokens none. Every path degrades to NA, never to a plausible number.

## 11. Failure-mode analysis

| # | Mode (choice that causes it) | Disp. | Control · test |
| --- | --- | --- | --- |
| F1 | A fault case, or a clause of it, is dead (no solution can flip it) | P+D | per-variant flip test with clause (§9.2 table); a case no variant flips fails the branch rule |
| F2 | A hidden test is red on the base only because a module is missing | P+D | wrong-app fixtures per task; `test_<id>_each_wrong_app_turns_exactly_its_test_red` |
| F3 | A broken exchange or crash reads as a flipped case (fail-closed) | P+D | variant test asserts hidden tests pass, `deliverable == ran`, flipped set, deciding clause; `crash-variant` |
| F4 | The prompt states a mechanism (a latent term) | P | latent-term scan; `test_<id>_prompt_has_no_latent_term` |
| F5 | The solution must meet a bound the prompt never gave | P | numbers in the prompt, mechanisms latent (RQ-2) |
| F6 | `rework_ratio` is gamed by duplication (RQ-1) | P+A | turn-2 delegation test; `v-duplicate`; residual R-W1 |
| F7 | Synthetic cell has no trajectory, so `verified_before_use` expected is unprovable | P | `{na: "synthetic cell has no trajectory"}`; metric tested on fixture rows |
| F8 | `verified_before_use` is 1 by class order | P | refused; NA without targets (§7.2); `test_vbu_class_order_is_not_one` |
| F9 | A hallucinated member sits on a dead branch of the final tree and the hidden tests stay green | D | the count is the metric; `v-hallucinated` keeps tests green and flips the count |
| F10 | A docstring or blank line inflates `size_vs_reference` | P | §5.1; `v-docstring` must flip nothing |
| F11 | A changed file is counted by both `scope_creep` and `size_vs_reference` | P | one `in_radius`; partition test (§3) |
| F12 | Fake listeners of parallel cells collide | P | `listen()` binds port 0 and asserts `127.0.0.1` (ADR-0018 §3); X-LB's test |
| F13 | A host suspend turns a 3 s case into a `timeout` | M | HB-CHK-004 (W0 row 1); `PROPERTY_SUSPEND_GAP_S` |
| F14 | The campaign interpreter (3.14.6) differs from 3.12.10 | D | assume A1; the first discrimination run is the confirmation |
| F15 | The agent special-cases the fake's address or the canary | A | the in-process residual of ADR-0018 Amendment 1, as S1 F13 |
| F16 | Control arm saturates or floors | D | EV-8 admission, not a design defect; RS and SM may saturate on strong models (R-L1) |
| F17 | A base's upstream licence or contents change under a moving ref | P | 40-hex pin, `^{tree}` hash in `evidence.md`, `NOTICE.md` |
| F18 | An authored vendored library's README disagrees with its code | P | `test_ng_vendored_readme_matches_code` (parses the documented signatures and checks them with `inspect`) |

## 12. Adversarial analysis (STRIDE-lite)

Trust boundaries: B7 (agent deliverable → check host; W1-F/ADR-0018), plus T1 (oracle material → agent workspace), T2 (upstream base → engine, supply chain), T3 (canary/fake data → reports).

| Threat | Boundary | Disp. | Control · negative test |
| --- | --- | --- | --- |
| S: the agent detects the check and returns canned safe replies (fault cases) | B7 | accept | residual as S1 F13; the fake's schedule is fixed but the agent cannot see it before grading |
| T: the oracle (fault schedules, hidden tests, vendored README answers) enters the prompt or workspace | T1 | mitigate | `oracle/` is outside the base; the NG README is the **task's public contract** and is meant to be read; `test_<id>_no_oracle_string_in_prompt_or_task_workspace` greps the prompt and base for schedule constants and wrong-app markers |
| T: the pin moves | T2 | mitigate | 40-hex, tree hash, `test_<id>_pin_is_a_full_commit` |
| I: a canary or record body reaches a report | T3 | transfer | `egress.task_canary`; resilience records are counts, never bodies |
| D: a handler that blocks forever, a huge response | B7 | mitigate | per-case bound → `timeout`; frame limits (W1-F) |
| D: the fake is flooded by a retry storm | B7 | mitigate | the fake counts requests and caps at 50 per case, then answers 503 and records `requests` over the bound |
| E: the resolver (NG) imports the real vendored library, which is task-authored code | B7 | prevent | the resolver imports only `vendor/<lib>` under `-S`, never agent code; it is the task's own library |
| Supply chain: base licences | T2 | mitigate | §2 table; `NOTICE.md` and upstream licence copy per task; `test_<id>_notice_and_license_exist` |

Misuse cases as negative tests: the retry-forever, no-key and no-timeout variants (RS), the duplicate (RW), the class-order read (NG), the padded one-liner (SM, residual R-S1).

## 13. Patterns

Rungs climbed (Solution-Selection Ladder): YAGNI → reuse (`correctness.grade`, `_changes.change_set`, `drift._diff`, `bench_check`, S1's variant/wrong-app tables) → stdlib (`ast`, `difflib`, `inspect`, `http.server`) → one line → minimum.

| Pattern | Where | Justification | Rejected |
| --- | --- | --- | --- |
| Strategy (W1-F `STRATEGIES`) | `rework`, `noguess`, `diffstats` | one property, one function; no registration in `GRADERS` (R-90 c4) | three graders in `GRADERS` (refused, DR-4) |
| Fake / Test Double on loopback | resilience dependency | the fault is the stimulus; fixed schedule | a mock in the deliverable's process (cannot time a socket) |
| Mutation-based test adequacy | variants and wrong-app fixtures per task | the only evidence a branch or a hidden assertion is live | trusting the naive (it flips only some branches) |
| Fail-closed oracle | broken exchange = failed case | a resilience check that errs open scores a hang as safe | NA on a broken exchange |
| Canary / Characterisation Golden | expected values | provenance by derivation, `Inferred` until a real-host run | copying a grader run |
| Ordered Decision Table | unchanged (W1-F `_classify`) | not reimplemented | handler chains |

**Simplifier's cuts accepted (pre-empting RV-SIM).** (1) No shared probe library across the resilience tasks (two tasks; `simplify:` ceiling two, trigger a third). (2) No jitter or random schedules. (3) `verified_before_use` takes the read clause only; the probe-run clause is `Not built` until SR-L1's target can carry a command word. (4) No `static` case for simplicity: the strategy computes metrics from the tree, not a check process. (5) Rework and simplicity numeric expectations are targets until sources exist, not invented numbers. **Patterns Expert's push accepted:** predicates accept sets of correct behaviours (any retry schedule within the bounds), and a second correct reference is required per resilience task (`test_<id>_an_alternative_correct_solution_passes`: different timing, same bounds).

## 14. W1-I lessons, applied

| Lesson | Where |
| --- | --- |
| every hidden test has wrong-app fixtures | §6.2, 6.3, 7.3, 7.4, 8.2, 8.3, 9.2, 9.3 |
| the variant-flip test asserts tests pass, `deliverable == ran`, flipped set, deciding clause | §9.2 table; §15 |
| every probe, case and metric has a flipping variant | §6.2, 7.3, 8.2 (each metric), 9.2, 9.3 |
| expected values are Inferred until the real host reproduces them; `ready` needs a real-host discrimination record | every `expected` block; §15 `test_<id>_real_host_reproduces_expected` |
| builds are declared offline | §5.2 |
| MIT/Apache bases at a 40-hex pin | §2 |

## 15. Test plan (by node id; red first)

Files: `tests/test_property_tasks_rs.py`, `_rw.py`, `_ng.py`, `_sm.py` (one per property; written by the owning track), and strategy tests in `tests/test_grade_rework.py`, `test_grade_noguess.py`, `test_grade_diffstats.py` (X-J2, X-LG). Directives: D0 hygiene; the Testing-Strategy union is the golden set (expected values), a negative set (variants), a determinism test.

**Floor items (README §2a).** (1) *Skeleton commit first:* each track's first commit lands the folder with `variants.py`/`wrong_apps.py` tables and a stub solution that returns a wrong value (501 for services, an identity function for libs), so every red below is an assertion on a real result, never an `ImportError`. (2) *Red fixtures:* named per row. (3) *Real-wiring tests beside fakes:* `test_<id>_real_host_reproduces_expected` per task drives the real grading pass and fails if the strategy's registration line in `property.STRATEGIES` is removed. (4) *Adjacent-pair mutants:* `rework` (delete vs replace opcodes, a swap changes `|C|` on the fixture `replace_only`), `diffstats` (radius partition: a swap of in/out counts the same line twice), `noguess` (read-before-edit vs edit-before-read ordinals, equal ordinals read as not-before). (5) *Sweeps checked against the tree:* the latent-term scan was run on every prompt shape above and found 0 hits (list in §6-9; the scan itself is the test); the only allowlist, the stdlib module set, is `sys.stdlib_module_names` (not a copy).

| Node id | Red today because | Red fixture / mutant | Ring |
| --- | --- | --- | --- |
| `test_<id>_prompt_has_no_latent_term` (8) | the scan names term and line | fixture prompt containing a latent term; delete the scan | push |
| `test_<id>_each_wrong_app_turns_exactly_its_test_red` (8) | the stub already fails all tests by assertion | a fixture that fails two tests or by `ImportError` | readiness |
| `test_<id>_hidden_tests_fail_on_stub_pass_on_both_solutions` (8) | stub fails | the stub is the red case (does not prove strength: previous row does) | readiness |
| `test_<id>_pin_is_a_full_commit`, `_notice_and_license_exist` (8) | a branch name or missing `NOTICE.md` | fixtures | readiness |
| `test_<id>_declares_no_build_and_no_network_names` (8) | five S1 fixtures | `pip`, `uv`, `npm`, `http*` words; `uv` inside `uvicorn` must not hit | push |
| `test_<id>_no_oracle_string_in_prompt_or_task_workspace` (8) | oracle constant found | fixture prompt with a schedule constant | readiness |
| `test_<id>_each_variant_flips_exactly_its_set` (8) | per variant: hidden tests pass, `deliverable == ran`, flipped set, clause, duration band (RS) | `crash-variant`; a `dead-case` fixture no variant flips | readiness |
| `test_<id>_an_alternative_correct_solution_passes` (RS1, RS2) | second reference with different timing passes | reference with the key removed must fail | readiness |
| `test_<id>_real_host_reproduces_expected` (8) | expected block unreproduced (the task cannot be `ready`) | strategy registration removed → reads `not built` | readiness (strategy landed) |
| `test_rs_fault_clause_is_recorded` | the case record names `time|requests|effect|result` | variant whose clause is `result` | readiness |
| `test_rework_ratio_counts_replaced_and_deleted_not_added` | `\|C\|` on a 6-line fixture with 2 replaced, 1 deleted, 3 added = `3/6` | `replace_only` fixture swapping `replace` for `delete` | push |
| `test_rework_turn2_not_reached_is_na_and_primary_zero` | final tree absent turn-2 | fixture cell ended in turn 1 | push |
| `test_rework_duplicate_fails_delegation` (RW1, RW2) | `v-duplicate` fails T2-5 and not by ratio | reference with ratio 0 but no delegation | readiness |
| `test_noguess_resolver_counts_distinct_unresolved_names` | `from quotakit import A, B` → 2; `getattr` form → 0 | fixture trees; agent code never imported (a module that writes a marker on import must leave none) | push |
| `test_vbu_read_before_edit_is_one`, `_edit_before_read_is_zero`, `_no_targets_is_na`, `_class_order_is_not_one` | NA/0/1 by ordinal; class order refused | fixture rows with and without `target`; equal ordinals = not before | push |
| `test_sm_product_lines_ignore_blank_comment_docstring` | `v-docstring` flips nothing | fixture file with 6-line docstring | push |
| `test_sm_each_metric_has_a_flipping_variant` | `v-bloat`, `v-class`, `v-dep` flip exactly one metric each | variants | readiness |
| `test_sm_radius_partition_counts_each_line_once` | a file in radius counted by `size_vs_reference` only, a file outside by `scope_creep` only | change set with one file each; `in_radius` swapped → a line counted twice | push |
| `test_sm_frozen_reference_size_equals_function_output` | `size_reference_lines` equals `product_lines(reference diff)` | a hand-edited value | readiness |
| `test_ng_vendored_readme_matches_code` | documented signatures equal `inspect` | README with a renamed member | push |

**Sweep run on this design's base (floor item 5):** the eight pins were checked by `git rev-parse` and the `-S` import (SP-L1, count 8 ok, 2 rejected). The `ToolCall` sweep: `grep tool_class` found the extraction sites in `telemetry/codex.py` and `copilot.py` and `normalize.py:176-181` (all carry no argument), the basis of SR-L1.

**W0 trace.** §1 ids/budget: BOM check (X-A1). §2 fields and `expected` set per property: the `expected` blocks and `test_<id>_real_host_reproduces_expected`. §3 cases/`measures`/truth table/outcomes: W1-F's tests plus §9.1. §7 metric ids: W1-G. ADR-0015 §8 `graded_snapshots`: `rework` tests. EV-1..EV-7 mapped in §17.

## 16. Seam requests and decisions

| id | to | ask | fallback / what this design does |
| --- | --- | --- | --- |
| `req-01M41GWMCQDK3724G8CZ2VR40M` (SR-L1) | `coord-opus-e1e4` | `ToolCall` and the `tool_call` row gain a bounded `target` (workspace-relative path for read/edit, else first command word, at most 200 chars) before X-LG builds `noguess.py`; `telemetry/*` is run class (R-94), so it is an identity change | `verified_before_use` is NA `tool targets not extracted`, never a class-order 1 |
| `req-01M41GWMT35CEXNPNZXMYD9KP0` (SR-L2) | `coord-opus-e1e4` | confirm `interface: loopback` may declare `app` (callable) so the probe host calls the client with `args` carrying the fake's URL; confirm `kind: fault` outcomes and the `idempotency_violations` measure | RS1/RS2 stay provisional on it |
| `req-01M41GWNS06F362RJ78XB7AXY5` (DR-L1) | `owner-fable` | meaning of `hallucinated_symbol_errors`: A final-tree static count, or B trajectory build log (needs tool-result extraction) | A, provisional |
| `req-01M41H679VVB248H3XANMY1PKN` (SR-L3) | `coord-opus-e1e4` | readiness (HB-RDY) must accept a rework/no-guessing/simplicity task with no `oracle/check/` and no `cases.yaml`, since the strategy helper is the check; `tasks/README.md` currently says `oracle/check/` holds the entry point | design assumes the exemption; blocks only X-E's rule |

**Decisions made here (reversible by editing a task):** D1 eight distinct bases, humanize and python-slugify rejected (G8). D2 numbers in prompts, mechanisms latent (RQ-2). D3 product-line rule (§5.1). D4 rework turn-2 prompts force a change to the turn-1 entry point (RQ-1). D5 simplicity has no check process. D6 NG hallucination count is the final-tree static one, provisional on DR-L1.

## 17. Conformance, residuals and "Done when" met

- **Assume A1.** The behaviours of §6-9 hold on CPython 3.14.6. *Confirm:* the first discrimination run on the pinned interpreter. *Breaks if false:* readiness fails (HB-RDY-003).
- **Assume A2.** The §8 line counts follow `product_lines`. *Confirm:* the stand-in run of the committed reference and naive before the task is `ready`. *Breaks if false:* the frozen value or a ceiling is re-derived.
- **Assume A3.** Hidden tests may use loopback sockets in the grading copy (RS1/RS2 tests use `http.server` on `127.0.0.1`). *Confirm:* `test_<id>_hidden_tests_fail_on_stub_pass_on_both_solutions` under the real `correctness.grade`. *Breaks if false:* the RS hidden tests move to a stdlib `unittest.mock` of `urlopen`.
- **Residuals.** R-W1 duplication (RQ-1). R-S1 line padding. R-L1 saturation (EV-8). R-N1 `getattr`/dynamic access is invisible to the resolver. R-X1 two bases per property are two samples of the property (spec R-E1).
- **Not verified here:** every reference and naive solution, every variant, every expected value (no run exists; all `Inferred`), the loopback fake, CPython 3.14.6, `readiness.py`, the strategy helpers.

| "Done when" item | Where |
| --- | --- |
| Gate PASS | [Gate record](#gate-record) (pending) |
| base codebase, eight tasks | §2 table, §6-9 per task |
| latent requirement, eight tasks | §6.2, 6.3, 7.3, 7.4, 8.2, 8.3, 9.2, 9.3 |
| hidden check, eight tasks | tests + cases/strategy per task; §6.1, 7.1-7.2, 8.1, 9.1 |
| reference and naive | per task; shapes, with exact source for SM1/SM2 reference |
| expected values | per task `expected` blocks; blocked numbers named B-RW1, B-RW2, B-SM1 |
| which graders are new | `rework.py`, `noguess.py` (`verified_before_use`, `hallucinated_symbol_errors`), `diffstats.py` (`size_vs_reference`, `new_abstractions`, `new_dependencies`), the `resilience` strategy: §6.1, 7.1, 7.2, 8.1, 9.1 |

## 18. Change-surface list (E7)

| Layer | Item | Owner |
| --- | --- | --- |
| store | `bench/bom.yaml`: the eight entries (status, base) | X-RW, X-RS, X-NG, X-SM (own entry each) |
| model | `tasks/<ID>/task.yaml`, `prompt.md`, `turns/2.md`, `tests/**`, `workspace/**` (overlay, `vendor/**`), `NOTICE.md`, licence copy | the owning track |
| service | `oracle/check/{check.py,cases.yaml}` (RS only), `oracle/solutions/**`, `oracle/variants.py`, `oracle/wrong_apps.py`, `oracle/evidence.md` | the owning track |
| service | `grade/rework.py` (E2), `grade/noguess.py`, `grade/diffstats.py` (E4), `STRATEGIES` lines in `grade/property.py`, `_changes.in_radius` move and `drift` import | X-J2, X-LG, X-LB (resilience line) |
| projection / wire | none new; `cases.json` is the grader's (W1-F) | — |
| client type / UI | none | — |
| compute reader | `readiness.py` (HB-RDY-003/005/006/007/008; SR-L3), the discrimination record | X-E |
| telemetry | `ToolCall.target` (SR-L1, provisional) | per ruling on SR-L1 |
| evidence | `oracle/evidence.md`: pin trees, per-case and per-variant outcomes and clauses, stand-in counts | the owning track |

## Status and next action

| Item | State |
| --- | --- |
| Eight tasks: base, pin, licence, latent requirement, prompt shape, hidden tests, fixtures, variants | done in this revision |
| Expected values | fixed for primary metrics and integer metrics where derivable; `rework_ratio` (RW1, RW2) and the naive `size_vs_reference` (SM1, SM2) are named blocking items B-RW1, B-RW2, B-SM1, B-SM2 (need committed sources) |
| SR-L3 | filed: `req-01M41H679VVB248H3XANMY1PKN` |
| Spikes not run | stand-in count of rework and size (A2), the fault timings, the loopback fake |
| Reviews | RV-PAT, RV-SIM, RV-TA pending |

## Gate record

| lens | reviewer | status | line |
| --- | --- | --- | --- |
| Patterns Expert | RV-PAT | pending | |
| Simplifier (soft veto) | RV-SIM | pending | |
| Test Architect (**hard veto**) | RV-TA | pending | |
