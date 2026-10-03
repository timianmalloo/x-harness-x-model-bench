---
id: "design-eval-discriminate"
title: "W1-E design: discriminate, the synthetic profile and the readiness check (EV-7; X-E)"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 design slice W1-E; builds in E1 (X-E: discriminate.py, readiness.py, synthetic_agent.py, profiles.py)"
tags: [benchmark, discrimination, readiness, synthetic-agent, evaluation-campaign, w1-e]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: adr-0016-campaign-record, rel: depends-on }
  - { to: adr-0018-hidden-check-harness, rel: depends-on }
  - { to: adr-0019-catalog-0-7-property-metrics, rel: depends-on }
  - { to: design-eval-property-grader, rel: depends-on }
  - { to: design-eval-atomic-publish, rel: depends-on }
  - { to: design-eval-security-tasks, rel: relates-to }
  - { to: defect-classes, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Designs the one path by which a property task becomes ready: bench discriminate runs the task's reference, its
  naive solution and its defect variants as synthetic cells through the real engine, working-copy builder, archiver
  and grading pass (and so the real probe host), and writes a create-once, idempotent discrimination record;
  readiness.py then refuses `ready` unless that record exists, was made by the real host, matches the current task
  version and engine, and every expected value is observed. Settles the record's data model (no run id in its body,
  so a legitimate retry is a no-op), the synthetic agent (a stdlib ACP process behind Launcher; engine.py unchanged,
  Verified by spike S-E1), the solutions-overlay rule, the disagreement and clock-failure readers, the discrimination
  sweeper, and names every red-first test with its fixture, real-wiring partner and mutant.
---

# W1-E design: discriminate, the synthetic profile and the readiness check (EV-7)

**Author:** Claude Sonnet 5.5 (`claude-sonnet-5-5`, session `w1e-discrim-e1e4`), 2026-10-03, base `b88746d9` (main; W0 rev 3 and R-87..R-96). Branch `design/eval-discriminate`. T2, fan-out 0. Gate record: pending (the Gate section).

Confidence labels: **Verified** (I opened the file or ran it on this base), **Inferred** (reasoned, not observed), **Flagged** (a contradiction or gap the reader must resolve). A sibling design on a branch is cited by its section; it is Verified as *text*, not as code.

## Status

| | |
|---|---|
| **Completed** | Data model; discrimination record; synthetic agent and launcher (spike S-E1 run); overlay rule; variant trial (D1); real-host control (D4); readiness items EV-1/EV-7 to HB-RDY to test; the three readers (`hidden_test_disagreements`, `unbiased_failures`, trial-untrustworthy); sweeper; E7 surface list; failure modes; STRIDE-lite; telemetry; test plan with the testability floor; two seam requests |
| **Remaining** | Gate (RV-PAT, RV-SIM, RV-TA, RV-SEC); seam answers (section 15); X-E's build, which waits on X-A1 (`kind`, `profile_record` for `synthetic`), X-B1 (`create_once`), X-D (`identity`, HB-RDY-011 row) and, for the property end-to-end test, X-F |
| **Best next action** | Gate review; then `/implement` X-E starting with the skeleton commit of section 14.1 |

## 1. What this slice owns, and the obligations routed to it

One responsibility: **a property task is `ready` only because the engine itself showed that its hidden check discriminates, and the proof is a record nobody can fake by hand or lose by retrying.** It owns `src/harness_bench/discriminate.py`, `readiness.py`, `synthetic_agent.py` (all three grade class, W0 §9) and the `profiles.py` hunk of section 5.3 (W0 §13: X-E's hub in E1). It owns `bench discriminate`'s composition (the subcommand's `cli.py` line is X-C's, section 12).

| # | Obligation (source) | Design element | Section | Test |
| --- | --- | --- | --- | --- |
| O1 | RV-TA W1-I D4: readiness refuses `ready` without a real-host record; "X-I advances" is a convention, not a control | Rule R-HOST: `ready` needs a record whose `probe` digest shows the real probe host ran every declared case; `bench validate` fails otherwise (HB-RDY-001) | 8.2 | T-E8, T-E9 |
| O2 | RV-TA W1-I D1: the variant test (m9-m13, deciding clauses) runs on the real host before `ready` | Variants are synthetic cells of the same discrimination run; the record holds each variant's flipped set and clauses; readiness compares them with the declared ones | 7 | T-E11, T-E12 |
| O3 | Seam `req-01M41DM7XQG9GYVR32TJ762V67`: never drop an HB-CHK-002 count or a failed clock reading silently | Rule R-NA: any trial cell with an HB-CHK-001..004 NA row, or a span with `unbiased_ok` false, is a `readiness_failures` item (HB-RDY-011) and a telemetry count; `readiness.unbiased_failures` is the pilot's reader | 8.4 | T-E13, T-E14 |
| O4 | R-93 / R-96: `readiness.hidden_test_disagreements` is `None` when the reader did not run; R-90 condition 3 sits in X-E's path | One function, three states; the discriminate path calls it and fails the trial on a non-empty list or `None` | 8.3 | T-E15, T-E16 |
| O5 | RV-DS W0 F2: the record is idempotent; its body carries no `run_id` or `grading_id` | The body is a pure function of (task version, engine, platform, scores); the run link is a local sidecar | 4.2, 4.3 | T-E5, T-E6 |
| O6 | RV-DS W1-B F3: X-E owns the sweeper for discrimination temps | Per-task lock, `sweep_temps` before a write, `is_temp_name` skip-and-name in readers | 9 | T-E17, T-E18 |
| O7 | RV-PAT W1-I 7: state the solutions-overlay rule | Section 6 states it; one paragraph goes to `tasks/README.md` by seam | 6 | T-E2, T-E3, T-E4 |

**Done when (the plan row):** Gate PASS incl. Security (the Gate record, pending); the SCAN-A red fixture named (section 8.2, fixture `scan_a`, test T-E10); the synthetic agent mechanism (section 5; a stdlib ACP fake behind `Launcher`, no `engine.py` edit, **Verified** by spike S-E1, section 16).

## 2. Inputs read (quoted where a control rests on them)

- ADR-0016 §4: "**Grain:** one file is exactly one discrimination trial of one task version under one engine identity on one platform. It holds the full task version hash, identity hash and platform, the synthetic run id and grading id, both score sets ... and the readiness items that failed". **Flagged:** this and W0 §6's JSON put `run_id` and `grading_id` in the body; obligation O5 says the body carries none. Section 4.3 resolves it by seam request SR-E1 with a stated fallback.
- ADR-0016 §5: "its 'driver' copies `tasks/<ID>/oracle/solutions/<reference|naive>/` ... into the working copy and ends the turn. Everything else is the engine's own path".
- W0 §6 "A second production at the same key": "Different is the real determinism defect: HB-RDY-010".
- W0 §2: the `expected` set is `runner.applicable(catalog, graders, property)["property"]`; comparison "by exact equality after both sides pass through one function, `grade/property.py: at_scale`".
- W0 §7 condition 3 and R-93, R-96 (quoted in 8.3).
- Code read on this base: `engine.py:69-85` (`Launcher`), `:602-682` (`_run_cell`), `:852-854` (`_read_records`); `profiles.py:26,176,220-262`; `plan.py:240-246,272-356,113-115`; `cli.py:76-82,142-155,202-226`; `preflight.py:41-60`; `tests/test_engine.py:41-77`; `tests/fake_acp_agent.py`; `config.py:29,34,356-366`; `oslock.py:46-60`.

## 3. Bounded context, ubiquitous language, aggregates

**Context:** *Task readiness*, inside the Evaluation Campaign context (spec domain model). Language: **trial** (one discrimination run of a task version), **role** (`reference`, `naive`, or a variant name), **overlay** (the solution files copied over the engine-built base), **key** (task version, engine identity, platform), **expected set** (W0 §2), **probe digest** (the per-role summary of what the real host did).

| Aggregate | Root | One invariant it protects | Referenced by identity only |
| --- | --- | --- | --- |
| `DiscriminationTrial` (the record) | file at `bench/discrimination/<task>/<tv16>-<id16>-<platform>.json` | **A key holds at most one record, and its scores are what the engine measured for that key; a second production either equals it or is a reported determinism defect.** | task version hash, engine identity hash (both by value in the key); the run by a local link (4.3) |
| `ReadinessVerdict` | none, never stored | n/a: a derivation (DM7) of {task files, catalog, record, current identity} | |

`readiness_failures` is stored in the record (W0 §6) but **readiness never trusts it**: it recomputes the list from `scores`, `expected` and the probe digest and compares (test T-E19 tampers the stored list). The stored list is the audit copy of what the author saw when the record was made.

## 4. Durable representation

### 4.1 Grain, measures, history

- **Grain:** one row is exactly one trial of one task version, under one engine identity, on one platform. Key as ADR-0016 §4. **Measures:** each score is a non-additive per-cell value (a 0/1 or a 4-decimal share); nothing in the record is summed. **History rule:** the record is an immutable fact. A new task version or a new identity is a new key, so a past record keeps meaning what it meant (Type-2 by key). Nothing is updated.
- **Engine identity, for the key.** `identity_hash` of the manifest **without** `builds/*`: `identity.manifest(root, [task], builds=None)` hashed with `ledger.canonical` (W1-D §3.2: `builds` is optional and `builds/<h>` is "a plan-consistency key only"). A discrimination run plans only the synthetic harness; the real harness builds are irrelevant to it, and a baseline manifest that includes them would never equal the record's hash. For a campaign, HB-RDY-002 compares the record's hash with the baseline manifest (read from `bench/campaigns/<id>/identity/<hash>.json`) after dropping its `builds/*` keys. **Flagged, seam SR-E1:** this needs X-D to state that `builds=None` omits the `builds/*` keys and that `profiles/<h>` covers the plan's harnesses only; I read W1-D's text, not its code.
- **Status is inside the version hash (Verified, `plan.py:113-115`: `task_version_hash` is `tree_hash` over every file in the task folder, `task.yaml` included).** Flipping `status: draft` to `ready` after the record is made changes the hash and orphans the record. So the order is fixed: **flip to `ready` first, then discriminate, then commit task and record together.** The discrimination plan admits `draft` and `ready` (W0 §1, W1-A). A failed trial writes no record (4.4), so a task that fails stays `ready` on disk until the author reverts or fixes it, and `bench validate` names HB-RDY-001. W1-I's note "X-I advances to ready only when ... the discrimination record exists" is circular as written; SR-E2 corrects its wording.

### 4.2 The record (W0 §6, detailed; changes are SR-E1)

```json
{"schema": "bench-discrimination/1", "task": "S1", "task_version": "<64 hex>", "identity_hash": "<64 hex>",
 "platform": "win32",
 "scores":   {"reference": {"<metric>": 1}, "naive": {"<metric>": {"na": "<reason>"}}},
 "expected": {"reference": {"<metric>": 1}, "naive": {"<metric>": 0}},
 "probe":    {"reference": {"deliverable": "ran", "cases": {"inj-1": "blocked"}, "hosts_ready": 8}, "naive": {...}},
 "variants": {"m9": {"scores": {...}, "flips": ["leak-3"], "clauses": {"leak-3": "file, deliverable copy"},
                     "hidden_tests_pass": true, "deliverable": "ran"}},
 "readiness_failures": []}
```

- **Removed from W0 §6's JSON:** `run_id`, `grading_id` (O5). **Added:** `probe` (the real-host digest, O1) and `variants` (O2, present only when the task declares variants). `scores` and `expected` hold the roles `reference` and `naive` exactly as W0 §6. Values are `at_scale` normalised (a JSON int, or a string with exactly the catalog scale of decimals, or `{"na": "<reason>"}`), the one normaliser (W0 §2).
- **Bytes** are `ledger.canonical(obj)` (sorted keys, no floats) and are written once with `atomic.create_once` (W0 §4).
- **Why `probe` copies a digest:** `runs/` is gitignored, so on a fresh clone the run does not exist and `bench validate` must still decide (ADR-0016 §4, "Why the record copies score sets"). The digest is a copy of fields the grader wrote in `property.json` (`check.deliverable`, `check.cases[].outcome`, the count of `check.hosts` lines with `end: ready`), identified by the run link when that run exists.

### 4.3 Idempotence: the body is a function of the key and the scores (O5)

RV-DS W0 F2: with `run_id` and `grading_id` in the body, two productions never have equal bytes, so `create_once` raises HB-LED-007 (a false determinism defect) on every legitimate retry. W0 rev 2 chose the reviewer's option (a): read the key first, compare only `scores`, `expected`, `readiness_failures`. O5 asks for the stronger form, and this design takes it:

- The body holds no run or grading id, so **a retry at an unchanged key produces equal bytes and `create_once` returns "equal, no-op"** (W0 §4: "True = created; False = path existed with equal bytes"). There is no special read-first branch to maintain. HB-LED-007 keeps its one meaning: bytes differ.
- `discriminate.run` still reads the key first, for one reason: to tell **why bytes differ**. A difference at an existing key is HB-RDY-010 naming the first differing metric, the stored value and the new value (W0 §6), raised **instead of** HB-LED-007 (the file is never touched, so the two codes cannot both be right; test T-E6 asserts HB-RDY-010 and that the stored bytes are unchanged).
- **The run link** (so HB-RDY-004's read-time reconciliation still works). After a trial, `discriminate` writes `runs/<run_id>/discrimination-link.json` (`bench-discrimination-link/1`: record path relative to the repo, `grading_id`, the timings and counts of section 11). It is local and gitignored with `runs/`. Reconciliation (HB-RDY-004) finds the newest link whose `record` equals the record's path, and recomputes the scores from that run's grading pass (ADR-0006 latest-pass rule). **No link, or the run folder absent, means "not reconciled"**: `readiness` prints `reconciled: no (no local run)` and does not fail. It never reads as a pass of the reconciliation (IO: degrades to "not recorded"). Loss of the link costs the reconciliation, not the record.
- **Fallback if SR-E1 is refused** (keeps O5's purpose): W0 rev 2's option (a). The body keeps `run_id` and `grading_id` of the *first* production; a retry compares `scores`, `expected`, `readiness_failures`, `probe`, `variants`, writes nothing when equal and raises HB-RDY-010 when different. T-E5 and T-E6 hold under either form; only T-E5's mutant differs (section 14.3).
- **Flagged:** the brief's wording and ADR-0016 §4/W0 §6 disagree (the ADR says the record holds the ids). I follow the brief and ask the Coordinator for the ADR amendment note (SR-E1). The ADR wins over a W1 design, so this section is **provisional (seam SR-E1)**.

### 4.4 When no record is written

`discriminate` writes a record only when the trial **ran to the end**: every role's cell reached a grading row for every metric of its expected set (a value or an NA with a reason). A trial whose engine run was incomplete (a cell `failed`, `timed_out`, the run stopped) or whose grading pass raised writes **nothing** and exits non-zero naming the cell and cause; there is nothing to reconcile and nothing to confirm. A trial that ran but **disagrees with `expected`** (a defect in the task) is still written, with `readiness_failures` non-empty: the record is the evidence of the failure (it is what makes the SCAN-A fixture's failure reproducible and diffable), and readiness reports it as HB-RDY-003. A trial that is untrustworthy (R-NA, R-93) is written the same way, with the HB-RDY-011 item.

### 4.5 Writer and compute reader of every persisted field (DM15)

| Field | Writer | Compute reader |
| --- | --- | --- |
| record: `task`, `task_version`, `identity_hash`, `platform` | `discriminate.run` | `readiness` (HB-RDY-001/002), `bench campaign verify` (name = key; X-C) |
| `scores`, `probe`, `variants` | `discriminate.run`, copied from the grading pass and `property.json` | `readiness` (HB-RDY-003, R-HOST, variant compare), reconciliation (HB-RDY-004) |
| `expected` | `discriminate.run`, copied from `task.yaml` at the trial | `readiness` (recomputed from the current `task.yaml`; a difference is HB-RDY-001 "task changed", impossible while the key holds, so it is a tamper tell) |
| `readiness_failures` | `discriminate.run` | humans; `readiness` recomputes and compares (T-E19) |
| `discrimination-link.json` | `discriminate.run` | `readiness` (reconciliation), the operator (timings) |
| `solutions` overlay tree | task authors (X-I, X-L) | the synthetic agent, at the trial only |

## 5. The synthetic profile and agent (Strategy behind `Launcher`; no `engine.py` edit)

### 5.1 Mechanism

`synthetic_agent.py` is a stdlib-only script run as `<sys.executable> <path of synthetic_agent.py>`. It speaks the minimum ACP the driver needs (`initialize`, `session/new`, `session/prompt`; `set_mode` and `set_model` are never sent because `mode=None`, `set_model=False`). On `session/prompt` it applies the overlay (section 6) to its **cwd**, which the engine sets to the cell's working copy (`engine.py:696`, `procs.spawn(argv, cwd=str(ws), ...)`, Verified), then replies `stopReason: end_turn`. `SyntheticLauncher` (in `discriminate.py`) satisfies the `Launcher` protocol (`engine.py:69-85`):

| member | value | why |
| --- | --- | --- |
| `harness` | `"synthetic"` | the cell's harness; `config.HARNESSES` already lists it by W0 §6 (SR-E1 carries the `config.py` hunk to X-A1) |
| `credential_names`, `credential_kind` | `frozenset()`, `"none (synthetic)"` | no login is read or copied; `profile.credential_source` does not exist |
| `usage_source` | `"acp_turn"` | with no usage in the reply, `_spend` returns None ("not recorded", never 0; `engine.py:857-863`) |
| `mode`, `set_model`, `shutdown_grace` | `None`, `False`, `1.0` | |
| `check_build()` | re-hashes `synthetic_agent.py` against the plan's `builds["synthetic"]` (`{"version": SYNTHETIC_VERSION, "sha256": <file sha256>, ...}`) and raises `tools.BuildChanged` on a difference | the US-12 analogue: the agent that made the trial is the one the plan froze |
| `seed`, `clean` | create the home folder; nothing | |
| `argv_env(cell, home, traceparent)` | `[sys.executable, <agent path>]`, `os.environ` plus `HB_SYNTH_OVERLAY=<abs path of the overlay tree for cell["combo"]>` and `TRACEPARENT` | the overlay is chosen by combo (section 5.2) |
| `records`, `read` | `[]`, never called | no native record exists; `_read_records` gets an empty list (`engine.py:852-854`) |

**Spike S-E1 (run, section 16):** the real `engine.Engine`, with this launcher shape and a prototype agent, ran two cells to `outcome completed, cause None, stop_reason end_turn`; the overlay file was present in each cell's archive (`attempt-1/ws/pkg/app.py`); no spend row was written; `engine.py` was not edited. So the Inferred line in W0 §14 is now **Verified** for the engine half. Not covered by S-E1: grading the archived tree (the grader's own path, X-F) and Python 3.14.6 (the spike ran 3.12; the agent uses only the stdlib calls the 3.12 and 3.14 docs share, **Inferred**).

### 5.2 Cells, combos, matrix

A trial is one run of `kind: "discrimination"` (W0 §5; X-A1 writes the field, X-E passes it). Combos: `synthetic-reference`, `synthetic-naive`, and `synthetic-v-<name>` per declared variant (names match `^[a-z0-9]{1,16}$`); each `{harness: synthetic, model: "synthetic-1"}` (`validate_matrix` refuses an empty or `auto` model, `config.py:119-120`). The matrix is `bench-matrix/1` with `packs: ["off"]` (one arm, rep 1; W1-A: a `/1` matrix with `packs: ["off"]` needs no pack clone, so `build_plan`'s `pack` argument is a placeholder the plan never reads for an `off` arm, **Inferred** from W1-A's text, confirmed by the real-wiring test T-E1a).
Run id: `disc-<task lowercased>-<tv[:8]>-<UTC yyyymmddThhmmss>`; every cell label matches `config.LABEL` (W0 §5 label `<task>.<combo>.arm-off.r1`, at most 80 characters: the longest case is 6 + 1 + 17 + 8 + 3 = 35).

### 5.3 What is, and is not, a profile

W0 §6 names `bench/profiles/synthetic.yaml`. **That file is not created** (Flagged, SR-E1), for two measured reasons: `tests/test_profiles.py:125` asserts `set(profiles.HARNESSES) == set(profiles.READERS) == set(tools.LAYOUT) == yaml_stems`, and `tests/test_acp_record.py:249` asserts `profiles.HARNESSES == ("claude-code", "codex", "copilot")`. A fourth stem or HARNESSES entry turns both red, and `READERS` and `tools.LAYOUT` have no synthetic entry to add. `config.HARNESSES` already differs from `profiles.HARNESSES` (it lists `grok` and `agy`, `config.py:34`), so a harness without a profile file has precedent. The one thing a profile file gave the plan is `plan.profile_record(root, "synthetic")` (`plan.py:240`, called for every harness in the plan, `plan.py:341`), which raises `ValueError` today (`profiles.py:176`). SR-E1 asks X-A1 for one hunk: `profile_record` returns the constant `SYNTHETIC_PROFILE_RECORD` for `"synthetic"` (defined in `plan.py`, because a run-class module may not import a grade-class one; W0 §9). X-E's `profiles.py` hunk is therefore **empty**: X-E edits `profiles.py` only if a gate review asks for the exclusion rule in code (5.4).

### 5.4 Exclusion from leaderboards and the qualification suite (ADR-0016 follow-up)

Exclusion is structural, not a filter someone must remember: the synthetic harness is in neither `profiles.HARNESSES` nor `tools.LAYOUT`, so the qualification suite (which iterates `profiles.HARNESSES`) never sees it; and a discrimination run is a run folder of `plan.kind == "discrimination"`, planned and run only by `bench discriminate`. **Residual (Inferred):** readers that enumerate run folders (`status.require_known` by `plan.json`, `gateway/backend.py:286`, `report` code reading `load_confirmed`) would include a discrimination run if handed its id. Test T-E20 plans a real discrimination run and asserts `bench status`, `bench report` and the board's run listing either refuse or label it; the scan behind the sweep is in section 13.

## 6. The solutions overlay rule (O7; RV-PAT W1-I 7)

**The rule.** A synthetic cell's final tree is the **engine-built working copy** (`workspace.task_source` then `cell_working_copy`) with the role's overlay applied by the synthetic agent, inside the cell, to the working copy's root:

1. The overlay is `tasks/<ID>/oracle/solutions/<role>/` (`reference`, `naive`). A variant's overlay is a materialised copy of `reference` with the variant's edits applied (section 7), held under the trial's run folder, never in the task folder.
2. Every regular file under the overlay is copied to the **same relative path** in the working copy, creating folders and replacing a file already there. A solution therefore ships **only the files it changes or adds** (S1 ships `examples/notes/app.py` alone).
3. **No file is deleted or renamed.** A solution that must remove a file replaces it. (`assume:` no E1 task needs a deletion; confirm: S1's and S2's overlays hold only replacements; breaks if false: the overlay would leave a stale file that the check sees. Upgrade trigger: a task whose naive needs a deleted file; then a `delete:` list file in the overlay, a design change.)
4. **Refused, with a named error, before any copy** (HB-RDY-005 from readiness; the agent also re-checks and exits non-zero, which the engine records as a failed cell): an absolute path or drive/UNC prefix; any `..` segment; a path under `.git/`; a symlink, junction or other reparse point (the agent uses `os.scandir` and never follows one, as W1-F's `_copy_tree`); two paths equal after case-folding (a Windows collision); more than 2000 files or 8 MiB (a runaway overlay; `simplify:` constants, upgrade trigger: a legitimate solution above them).
5. The task layout under `oracle/solutions/` is the only one a property task may use (`tasks/README.md:47`). `oracle/reference/` (D2, E5) is not a property-task layout; a property task that has it and no `solutions/` fails HB-RDY-005. Multi-turn (`turn-1/`, `turn-2/`) is **not built in E1**: a task with `turns` fails discriminate with HB-RDY-005 `not built in E1` (the rework design, X-J1/X-J2, E2, adds one prompt and one overlay per turn).
6. The rule is stated in `tasks/README.md` by one paragraph through the Coordinator (SR-E2: the file is W0's). W1-I cites this section.

**Why the agent copies inside the cell, not the launcher beforehand:** the point of EV-7 is that the tree was built and handed over by the engine's own path (ORCL-A: an oracle proven against a working copy the engine never builds). An overlay applied by the launcher before the engine builds the copy, or applied to a script-local clone, would reintroduce exactly that. T-E2 holds it.

## 7. Variants on the real host (O2; RV-TA W1-I D1)

**Contract with the task (SR-E2 to W1-I/X-I).** A task that declares defect variants holds `oracle/variants.py` whose module body assigns one literal:

```python
VARIANTS = {"m9": {"flips": ["leak-3"], "clauses": {"leak-3": "file, deliverable copy"},
                   "edits": [{"file": "examples/notes/app.py", "old": "<exact text>", "new": "<replacement>"}]}}
```

X-E reads it with `ast.literal_eval` of that one assignment: **the file is never imported or executed** (no operator-process code execution from a task file; test T-E21 puts a side effect in the file and asserts it does not run). W1-I's `apply(reference_source, name)` function may live in the same file for X-I's own tests; X-E does not call it. `edits[].file` is a path relative to the reference overlay; `old` must occur **exactly once** in that file (else the variant is an authoring defect: HB-RDY-005 `variant <name> edit does not apply (0 or n matches)`).

**Trial.** For each variant, `discriminate` copies the `reference` overlay to `<run>/variants/<name>/`, applies the edits, and adds a combo `synthetic-v-<name>`. The variant is a cell of the **same** run, so it is built by the engine path and graded by the real grading pass and the real probe host. Cost: S1 declares 13 variants, so the trial is 15 cells; each cell's property step is one probe-host session of 8 cases. **Inferred** wall time: minutes, not measured; section 11 emits it, section 15 names the measurement as the first X-E join check (the parallel-cell load coupling RV-DS W0 4 names applies: a variant flipped by a load-driven `timeout` reads as a wrong `flips`, so `discriminate` runs the synthetic cells with `parallelism: 1` to keep host load independent of cell order; `simplify:` ceiling: serial runs; upgrade trigger: a 15-cell trial longer than the operator accepts).

**Compare, per variant** (all four of X-I's assertions, on the host, from the grading pass):
1. `hidden_tests_pass` true (from `property.json`), 2. `deliverable == "ran"`, 3. the flipped set equals `flips`, where *flipped* means a case whose outcome is not `blocked` or `passed`, 4. the deciding clauses equal `clauses`. The clauses come from the task's check: if a variant declares `clauses`, the check writes `clauses.json` (`{"<case id>": "<clause>"}`) beside its other evidence; `discriminate` reads it from the directory that holds the cell's `property.json` (**assume:** the `Score.evidence` pointer of the `property_check_pass` row names that directory; confirm: W1-F §5.x and the pointer format `<evidence file>:<line>`; breaks if false: clauses cannot be read and every clause variant fails closed as HB-RDY-011, never passes). A missing `clauses.json` when `clauses` is declared is a failure, not a skip.
The results go into the record's `variants` (4.2). Readiness (8.2) recomputes the comparison from the record and the current `variants.py`.
The crash variant (every handler raises) must fail (1) or (2), not (3): a broken exchange reads `exploited` (W0 §3 fail-closed), so (3) alone would call a crash a flip (RV-TA W1-I 2). T-E12 holds it with a fixture variant.

## 8. Readiness: `readiness.py`

### 8.1 API

```python
@dataclass(frozen=True)
class Failure: code: str; item: str; detail: str            # "HB-RDY-003", "exploit_probes_blocked", "reference expected 1.0000, observed 0.0000"

def contract_failures(root: Path, task_id: str) -> list[Failure]        # 005, 006, 007(task-local part), 008, 009: no run needed
def record_failures(root: Path, task_id: str, *, baseline: Mapping | None = None) -> list[Failure]   # 001-004, 010-011, R-HOST, variants
def problems(root: Path, *, baseline: Mapping | None = None) -> list[str]   # what cmd_validate prints: "x <code> <task>: <item>: <detail>"
def hidden_test_disagreements(run_dir: Path, grading_id: str) -> list[str] | None   # 8.3
def unbiased_failures(run_dir: Path, grading_id: str) -> list[str] | None           # 8.4
```

`problems` covers every property task (a `task.yaml` with a `property:` block; 10 on this base, **Verified** by `grep -l "^property:" tasks/*/task.yaml` = 10, all stubs). It returns nothing for a `stub`; for a `draft` only `contract_failures` (the author is mid-edit, EV-7 is stated for `ready`); for a `ready` task all of it. Pair rule HB-RDY-007 (two tasks per property, different bases) is evaluated across the BOM by `problems`, not per task. `cli.py` `cmd_validate` calls `problems` (W0 §2; the line is X-C's, SR-E2 re-states it). `baseline` is the campaign's manifest when validating for a campaign (EV-7: "or the campaign baseline").

### 8.2 EV-1 / EV-7 bullet to item to code to test

| EV bullet | Item and rule | Code | Test (section 14) |
| --- | --- | --- | --- |
| EV-7 b1: a record with the current task version hash | the file `<tv16>-<id16>-<platform>.json` exists **and** its full `task_version` equals the current hash. A stale one for the same task is named ("record is for `<other tv16>`; the task changed; run `bench discriminate`") | 001 | T-E7a, T-E10b |
| (O1) b1': made by the real host | **R-HOST:** for every role, `probe.deliverable == "ran"`, `set(probe.cases) == the declared case ids`, `probe.hosts_ready >= len(cases)`; for a `loopback` or non-property-grader path, not applicable in E1 (those fail 005). A record without `probe` (hand-written, or made before the host existed) fails with "record lacks real-host probe evidence" | 001 | T-E8a/b/c |
| EV-7 b2: identity equals current (or baseline) | `record.identity_hash == identity_hash(manifest(root,[task],builds=None))`, or, with `baseline`, the baseline manifest's hash with `builds/*` dropped. A difference lists `identity.diff` components | 002 | T-E7b |
| EV-7 b3: reference primary is 1 | `scores.reference.property_check_pass == 1` | 003 | T-E7c |
| EV-7 b4: other reference metrics equal expected | for each metric in the narrowed set (`runner.applicable(catalog, task["graders"], task["property"]["name"])["property"]`, imported), `at_scale(observed) == at_scale(expected)`; `{na: reason}` equals only `{na: reason'}` for the same declared reason. Names metric, expected, observed | 003 | T-E10 (SCAN-A), T-E7d |
| EV-7 b5: naive primary 0, secondaries equal | same, role `naive` | 003 | T-E7e |
| EV-7 b6: SCAN-A shape | fixture `scan_a` (below) | 003 | T-E10 |
| EV-7 b7: expected has provenance (GLD-A) | each `expected.<role>.<metric>` value line carries a `#` comment of at least three words in `task.yaml`'s raw text (a presence check; independence from the grader's output stays a review item, stated) | 005 | T-E22 |
| EV-7 b8: frozen value equals the canonical function (HASH-A) | registry `FROZEN: dict[field path, callable]`; **empty for property tasks in E1** (scan: 3 `task.yaml` files carry `statement_hash`, G1, G2 and `_template`, none a property task). Built so X-LG's size recipe registers in E4. A registered field whose value differs fails | 009 | T-E23 (injected registry with a red fixture) |
| EV-7 b9: container runtime / Linux-only tool | `toolchain` entries matched against `CONTAINER_RUNTIMES = {docker, podman, nerdctl, ...}` and `LINUX_ONLY = {...}` named constants; `deliverable.build`/`start` argv[0] too | 008 | T-E24 |
| EV-1 contract fields | `property.name` in `config.PROPERTY_NAMES`; `latent_requirement` non-empty; `evidence_paths` non-empty and each exists in the **base tree** (`workspace.task_source`, not a script clone); `latent_terms` non-empty; `primary_metric` equals the catalog's one untagged primary; `graders` contains `correctness` and `property`; `expected` present for every metric of the narrowed set or `{na}`; `interface`/`app.kind`/`kind` inside what E1 builds (`in-process`; `callable`, `wsgi`; `probe`); `env` names in `_env.TOOLCHAIN_ENV` or `HB_CHECK_*`, none in `profiles.DROP_EXACT`/`DROP_PREFIXES`; `paths` relative and inside the root; `oracle/solutions/{reference,naive}/` present; overlays pass section 6 rule 4 | 005 | T-E25 (parametrized, one defect per case) |
| EV-1 latent terms not in the prompt | no `latent_terms` entry occurs in `prompt.md` (case-insensitive, whole-word); names term and line | 006 | T-E26 |
| EV-1 two tasks per property, different bases | pair rule over the BOM; "different base" = different `source.repo` + `source.commit` | 007 | T-E27 |
| ADR-0016 §4 read-time reconciliation | the linked run's current grading pass equals the record's scores; `copy <a>, run <b>` | 004 | T-E28 |
| W0 §6 second production | in `discriminate` (4.3) | 010 | T-E6 |
| O3, O4 | trial untrustworthy | 011 (new row, SR-E1) | T-E13..T-E16 |

**The SCAN-A red fixture:** `tests/fixtures/property_tasks/scan_a/` is a minimal in-process task (`callable`) whose `deliverable.build` is the Python task's mandated step that writes `build/out.txt`, and whose check carries a probe `scan-1` that reads the deliverable tree afterwards and calls any file outside `src/` an artifact, so the **reference's** mandated build output flips `scan-1` to `exploited`. Reference observed: `exploit_probes_blocked` `"0.8000"` against expected `"1.0000"` (4 of 5 probes blocked), and `property_check_pass` 0 against expected 1. T-E10 runs this fixture through the real discriminate path and asserts the record's `readiness_failures` and `problems()` name the metric, the expected value and the observed value. Deleting the comparison rule turns it green-by-accident, so the test's assertion is on the failure list, not on the run completing.

### 8.3 `hidden_test_disagreements` (O4; R-90 condition 3, R-93, R-96)

```python
def hidden_test_disagreements(run_dir, grading_id) -> list[str] | None
```

Three states (R-96's clarification, quoted: "list non-empty -> the warning with count and ids; empty list -> no element; `None` -> the `hidden-test-agreement-not-recorded` element with the reason, no count, no ids"):
- **A list of cell ids**: the cells of a property task where the pass recorded both `property.json.hidden_tests[final tree].hidden_tests_pass` and a `pass_at_1` row with a value, and `hidden_tests_pass != (pass_at_1 == 1)`. Sorted. `[]` means every comparable cell agreed.
- **`None`** when the reader could not run or could not read what it needs: the grading pass or its scores ledger is absent or unparseable; or a property cell whose `property_check_pass` row has a **value** has no readable `property.json`. A cell where either side is NA is **not comparable**: it is left out of the list and counted in `link.json` as `not_comparable` (telemetry, 11); it is never a silent agreement (the count is emitted) and never a disagreement.
- It reads, never writes. It does not call a grader (the R-90 (c) coupling stays refused).

R-90 condition 3's check **sits in X-E's path** twice: `discriminate` calls it on its own pass and writes a failure item when the result is non-empty or `None`; X-C's pilot command calls it for `gates.pilot` and X-H2 renders the grid-run line from it (W0 §7). T-E15 (three states, a real graded fixture) and T-E16 (the discriminate call).

### 8.4 `unbiased_failures` and HB-CHK counts (O3; seam `req-01M41DM7XQG9GYVR32TJ762V67`, `req-01M41EPKVYZQ9NH97HEJR7M5PY`)

```python
def unbiased_failures(run_dir, grading_id) -> list[str] | None     # cell ids with any span unbiased_ok false in property.json; None as above
```

In the **discrimination** path nothing is dropped: after the pass, `discriminate` examines every role's cell and records an HB-RDY-011 item (and a telemetry count) for any of: a `property_check_pass` row NA with a reason beginning `invalid (check tampered)` (HB-CHK-002), `check exceeded its bound` (HB-CHK-003), `host suspended` (HB-CHK-004, which says "re-run next pass": the trial is **not written** when the only problem is a suspend, 4.4, and the operator re-runs), `check output invalid` (HB-CHK-001); a span with `unbiased_ok: false`; or `unbiased_failures`/`hidden_test_disagreements` returning `None`. An NA that equals a declared `expected: {na: reason}` for that role is not a failure (the only exemption, EV-11). The counts of HB-CHK-001..004 rows per role go into `link.json` (11). The grader's NA is kept (W0 §3), and this is one of the two consumers that fail closed (the other is X-H1's pilot).

### 8.5 What `bench validate` prints

`x HB-RDY-003 S1: exploit_probes_blocked: reference expected 1.0000, observed 0.8000` (one line per Failure; format of `cmd_validate`, `cli.py:76-82`). Reconciliation status and skipped temps are printed as non-failing lines beginning `note:` so they are visible and cannot be mistaken for failures.

## 9. The discrimination sweeper and lock (O6; RV-DS W1-B F3, W1-B S-B4)

- **Lock.** `discriminate.run` takes `oslock.RunLock.acquire(runs/.discriminate-<task>.lock, code="HB-RUN-005")` (the lock is under `runs/`, so it needs no `.gitignore` line and never appears in `git status` of the committed folder; `RunLock.acquire` raises `BenchError(code)` when held, `oslock.py:52-58`, Verified). Held means "another trial of this task is running".
- **Sweep.** With the lock held, before a write, `atomic.sweep_temps(record_path, lock)` (S-B4 item 2 signature, **provisional (seam S-B4)**; fallback `sweep_temps(record_path)` under the same lock) deletes every `<record name>.tmp-*` sibling. Under the lock no live writer exists, so no age gate is needed. X-C's `verify` sweep (W1-C: age over 3600 s, under `campaign.lock`) remains safe beside it because it age-gates (it cannot know whether a `discriminate` writer is live).
- **Readers.** `record_failures` and `problems` list `bench/discrimination/<task>/` with `atomic.is_temp_name` and skip those names, **and name each skipped temp in a `note:` line** (W1-B: "skip and name what they skip"). They never delete (a read must not write).
- A crash between the temp write and the link leaves a temp and no record; the next `bench discriminate` sweeps it and writes the record (T-E17). `git status` of the committed folder never lists a temp (the three `.gitignore` lines are X-C's).

## 10. Patterns and the Solution-Selection Ladder

| Problem | Pattern | Rung | Rejected |
| --- | --- | --- | --- |
| Run a "harness" that is not a model | **Strategy** behind the existing port (`Launcher`); the synthetic agent is a **Test Double of the real boundary** (an ACP process), not a mock of the engine | reuse-in-codebase (the Launcher port, `FakeLauncher`'s shape) | an `engine.py` edit (a seam request, no need: S-E1); an in-process fake driver (skips `procs.spawn`, the job, the archive: ORCL-A) |
| A record that cannot be written twice differently | **Idempotent Receiver** (content-addressed, equal bytes = no-op) over `create_once` | reuse (W0 §4) | a read-first compare branch with ids in the body (the fallback, 4.3) |
| Pass/fail items with codes | a flat list of **Specification** predicates returning `Failure` (a Notification, not exceptions) so every failing item is reported at once (EV-7: "naming each item that fails") | one line each | a rule engine; a class per item |
| Task-declared variants | **Data, not code**: a literal table read by `ast.literal_eval` | stdlib | importing `variants.py` (executes task code in the operator process) |
| One narrowing, three readers | import `runner.applicable` and `property.at_scale` | reuse (W0 §2) | a copy of either |

The Simplifier's cuts, accepted in advance: no profile file (5.3); no `Readiness` class hierarchy (functions); no second store for the run link beyond one local JSON file; no async or parallel cells (`parallelism: 1`, `simplify:` marker in 7); multi-turn and loopback not built (6.5, 8.2). `simplify:` ceiling of the whole slice: one task per `bench discriminate` call; upgrade trigger: the E4 ten-task sweep wanting `bench discriminate --all`, which is a loop in the CLI, not a design change.

## 11. Telemetry (instrumentation over inference)

Questions an operator asks, each with a named emitting source (the link file, `discrimination-link.json`, always written when a trial reaches the end of the engine run, no flag):

| Question | Field in `discrimination-link.json` |
| --- | --- |
| How long, and where? | `durations_ms: {plan, engine, grade, compare, write}`; `cells: n`; per role `cell_ms` |
| How much? | `overlay: {files, bytes}` per role; `variants: n` |
| How often does it fail, and how? | `outcome` (`written`, `confirmed`, `failed-engine`, `failed-grading`, `suspend-rerun`, `determinism-defect`), `failures: [codes]` |
| Is the host trustworthy? | `chk_rows: {HB-CHK-001: n, ... -004: n}` per role; `unbiased_failures: n`; `hidden_test_disagreements: n \| "not recorded"`; `not_comparable: n`; `start_ms` max over `hosts.jsonl` |
| Was the record reconciled? | written by readiness at validate time to stdout only (`note:`), counted in `readiness.validate` log |

Structured log events through `engine.configure_logging` (same trace id): `discriminate.started`, `discriminate.finished`, `readiness.validated`, with `error_code` set to the stable code. **Constraint (Verified, `engine.py:LOG_EXTRAS`):** the engine's log keeps only `detail`, `pids`, `fact`, `win32_error` as extras, so numbers go in `detail` as a short `k=v` string and in the link file; the link file is the measurement source. Every field degrades to `null` ("not recorded"), never 0. No RFC 9457 surface (CLI only). Error codes: HB-RDY-001..011, HB-RUN-005 (reused), HB-USR-002 (bad arguments), HB-LED-007 (kept; unreachable from `discriminate` by construction, 4.3).

## 12. Surface list (E7): store to compute reader

| Surface | Change | Owner |
| --- | --- | --- |
| store | `bench/discrimination/<task>/*.json` (new folder); `runs/<run>/discrimination-link.json`; `runs/.discriminate-<task>.lock` | X-E |
| model | `Failure`; `SyntheticLauncher`; record dict shape and its `at_scale` normalisation | X-E |
| service | `discriminate.run`, `readiness.{contract_failures, record_failures, problems, hidden_test_disagreements, unbiased_failures}`, `synthetic_agent.py` | X-E |
| projection/wire | `bench-discrimination/1` JSON; `bench-discrimination-link/1`; `plan.kind == "discrimination"`; `SYNTHETIC_PROFILE_RECORD` in `plan.py`; `config.HARNESSES` gains `synthetic` | X-E; X-A1 (`kind`, `plan.py`, `config.py`) |
| CLI | `bench discriminate <task> [--runs --cells-root --root]` subcommand and the `cmd_validate` line calling `readiness.problems(root, baseline=...)` | X-C (`cli.py` is its hub file, W0 §13) by seam SR-E2 |
| identity | `discriminate`, `readiness`, `synthetic_agent` classed **grade** (W0 §9, already seeded by X-D); `identity.manifest(..., builds=None)` semantics | X-D |
| errors | HB-RDY-001..010 confirmed; HB-RDY-011 added; HB-RDY-004 text per ADR-0016 | X-D (`errors.py`, SR-E1) |
| docs | `tasks/README.md` overlay paragraph (6); ADR-0016 amendment note (4.3) | Coordinator (SR-E1, SR-E2) |
| UI / report | R-93 line renders from `hidden_test_disagreements` (X-H2); the pilot reads both readers (X-C, X-H1). **No UI in this slice** | X-H2, X-C |
| compute readers | `readiness` (record), `bench campaign verify` (name = key), `gates.pilot`, `report/campaign_section.py` | named above |

## 13. Sweeps checked against the tree (testability floor item 5)

| Claim | Scan run on base `b88746d9` | Output | Asserted by |
| --- | --- | --- | --- |
| "No `bench/profiles/synthetic.yaml`: it would break the profile-set test" | `sed -n 125p tests/test_profiles.py`; `grep -n "HARNESSES ==" tests/test_acp_record.py` | the equality of four sets; the tuple of three | T-E29: the same two tests stay green with the slice's branch merged (a join check, not a new test) |
| "10 property tasks exist as stubs" | `grep -l "^property:" tasks/*/task.yaml \| wc -l` | 10 | T-E25 reads the BOM at test time, not a pinned 10 (a count-free sweep) |
| "no property task carries a frozen hash in E1" | `grep -l statement_hash tasks/*/task.yaml` | G1, G2, `_template` (0 property tasks) | T-E23: the registry is empty for `property` tasks and the scan equals it |
| "`bench/discrimination/` does not exist yet" | `ls bench/discrimination` | not found | T-E7a: readiness handles an absent folder (a fresh clone is the normal case) |
| Run-enumerating readers a discrimination run could reach | `grep -rn "plan.json\|load_confirmed" src/harness_bench` outside `plan.py` | `cli.py:155`, `grade/runner.py:197`, `status.py:105`, `views.py:537`, `report/pack_improvement.py` (docstring references), `gateway/backend.py:286` (comment) | T-E20 drives `bench status` and the board against a real discrimination run |

## 14. Test plan (testability floor, section 2a of the Wave 1 README)

### 14.1 Skeleton commit first

X-E's first commit lands the three modules with the signatures of 5.1 and 8.1 and **well-formed wrong behaviour**, so no red test is an `ImportError`, `AttributeError` or `NameError`: `problems` and `record_failures` return `[]`; `hidden_test_disagreements` returns `[]`; `unbiased_failures` returns `[]`; `discriminate.run` plans and runs nothing and returns a result with `outcome: "skeleton"` and writes no file; `synthetic_agent.py` completes the ACP handshake and ends the turn **without copying** (so a cell completes with an unchanged tree). Every "today" column below is an assertion on that behaviour. It also lands the test fixtures of 14.4 and X-D's HB-RDY rows. Tests are pytest, `tests/test_discriminate.py`, `tests/test_readiness.py`, `tests/test_synthetic_agent.py`.

### 14.2 Rings (tests earn their place)

`push` (every push): pure file/record tests (T-E3, T-E5, T-E7, T-E19, T-E21, T-E22..T-E27), readers on hand-built records, the agent's handshake. `readiness` (at X-E's join and at each task's `ready` change): the engine-driven and host-driven trials (T-E1, T-E2, T-E6, T-E10..T-E12, T-E28) and S1's real discrimination (T-E30). One-time proofs (spike S-E1's repeat on 3.14.6, the wall-time measurement) are not in a ring; they are join checks.

### 14.3 The tests

"Today" is the assertion that fails on the skeleton, and why. "Real wiring" is the test beside any fake that drives the real composition. "Mutant" is the single edit that must turn the test red.

| Id | Test (file) | Assertion that fails today, and why | Red fixture | Real wiring beside a fake | Distinguishing mutant |
| --- | --- | --- | --- | --- | --- |
| T-E1a | `test_discriminate_end_to_end_through_the_real_engine_and_correctness_grader` | `record_path.exists()` is False: the skeleton writes no record. Task `DISC-C`: `graders: [correctness]`, hidden tests that pass on the reference overlay and fail on the naive | `tests/fixtures/property_tasks/disc_c/` (real `tasks/`-shaped tree, a pytest hidden test) | **is** the real path: real `plan.build_plan`, `engine.Engine`, `SyntheticLauncher`, `runner.run_pass`, `correctness.grade`, `atomic.create_once` | the launcher applies the overlay to a fresh temp dir not the cell's `ws` (T-E2 also) |
| T-E1b | `test_a_real_deliverable_through_the_real_probe_host_to_a_record` (**the required end-to-end test**) | same `exists()` assertion; plus `record["scores"]["reference"]["property_check_pass"] == 1`, `["naive"]["property_check_pass"] == 0`, `probe.reference.hosts_ready == len(cases)` | `tests/fixtures/property_tasks/disc_p/`: a `callable` task with a real `check.py` using `bench_check` (2 probes), a base tree, a reference and a naive overlay | **is** the real path: real `bench_check` probe host spawned by the real grader, no stub host; needs X-F merged (join order, section 15) | the grader's host replaced by a stub that returns `blocked` for every case: the naive would score 1; the test asserts naive 0 |
| T-E2 | `test_overlay_lands_in_the_engine_built_working_copy` | the archived `ws/pkg/app.py` equals the **base** content: the skeleton copies nothing | task with base `pkg/app.py` (content A), overlay replacing it (B) and adding `pkg/new.py` | real engine (S-E1 shape) | agent writes to `cwd.parent` (the ORCL-A shape): the archive still has A and no `new.py`: red |
| T-E3 | `test_overlay_refuses_unsafe_paths` (parametrized) | `readiness.contract_failures` is `[]` for each: the skeleton accepts everything | one temp solution tree per form: absolute path, `..`, `.git/x`, junction (made with `mklink /J`), symlink where permitted, case-collision pair, 2001 files | the agent's own re-check: the same trees run through the real agent exit non-zero and the engine records a failed cell | drop the `..` check: only that param goes green; delete the case-fold check: only the collision param |
| T-E4 | `test_overlay_never_deletes_and_never_writes_outside_cwd` | the agent copies nothing, so "a file in the base but not the overlay still exists" passes today: the **fails-today assertion is** `sorted(overlay_written) == sorted(expected_relative_paths)` (the skeleton writes none) | base with an extra `keep.txt`; overlay of two files | real engine | agent also removes files absent from the overlay: `keep.txt` assertion red |
| T-E5 | `test_retry_at_an_unchanged_key_is_a_confirmation` | first run: `exists()` False (skeleton). After X-E: second `run` returns `outcome == "confirmed"`, the bytes are identical, no HB-LED-007 | `disc_c` run twice with different run ids | real `create_once` | **M-ID:** put `run_id` back into the body: the second run's bytes differ, `create_once` raises HB-LED-007, test red. (Under the fallback form the mutant is: compare the whole body, not the five fields.) |
| T-E6 | `test_a_real_score_difference_at_one_key_is_hb_rdy_010_and_leaves_the_file` | no exception is raised today and the file is absent; after X-E the second run raises HB-RDY-010 naming metric, stored and new value, and `sha256(file)` is unchanged | `tests/fixtures/property_tasks/disc_flaky/`: an overlay whose output depends on a counter file kept outside the working copy, so run 2 differs | real engine and `create_once` | `create_once` called with `overwrite`-like behaviour, or HB-RDY-010 replaced by HB-LED-007: the code assertion or the hash assertion goes red (adjacent pair: equal bytes vs different scores) |
| T-E7 | `test_each_record_item_fails_with_its_code` (a..e) | `record_failures` is `[]` for every defect: the skeleton finds nothing | a hand-built record file per defect: (a) none, and a stale one for another version; (b) identity differs; (c) reference primary 0; (d) reference secondary differs; (e) naive primary 1 | T-E1b produces a record that `record_failures` accepts (the wiring partner for hand-built records) | change `==` to `>=` in the score comparison: (c)/(d) pass, red; compare `task_version[:16]` not full: a fabricated record with equal 16 prefix passes (add that case) |
| T-E8 | `test_ready_without_a_real_host_record_is_refused` (a..c) | `problems()` returns `[]` for each | (a) no record; (b) a record with correct scores and expected and **no `probe`**; (c) a record whose `probe.hosts_ready` is 0 | T-E9 (the real `cmd_validate`) and T-E1b (a real record passes) | drop the `probe` check: (b) and (c) go green. Adjacent pair (R-HOST vs HB-RDY-003): input (b) has equal scores, so only R-HOST can fail it; a mutant swapping R-HOST into the score comparison keeps (b) green |
| T-E9 | `test_cmd_validate_prints_hb_rdy_001_for_a_ready_task_with_no_record` | `cli.main(["validate", ...])` returns OK today (exit 0, "ok: ...") | a temp repo with `disc_p` marked `ready`, no record | **is** the real `cli.cmd_validate` through `cli.main` | delete the `readiness.problems` line in `cmd_validate`: red (this is the README floor item 3 test; it lives in X-C's line, joined at X-INT) |
| T-E10 | `test_scan_a_fixture_fails_naming_metric_expected_observed` | `problems()` is `[]` and the skeleton wrote no record | `scan_a` (8.2) | the real engine, grader and host (readiness ring) | remove the secondary comparison (check only the primary): the primary also reads 0 here, so add the sibling fixture `scan_a_secondary` whose primary stays 1 and only `exploit_probes_blocked` is wrong; the mutant is green on it only if the secondary rule is gone |
| T-E11 | `test_variant_trial_runs_on_the_real_host_and_compares_flips` | `record["variants"]` is absent: the skeleton runs no variants | `disc_p` + `oracle/variants.py` with two variants: one flips `p-2`, one flips `p-1` | real host (as T-E1b) | compare only `hidden_tests_pass` and `deliverable`, not `flips`: a variant that flips the wrong probe passes; fixture `wrong_flip` catches it |
| T-E12 | `test_a_crash_variant_is_rejected_not_counted_as_a_flip` | no variants run today | a variant that makes every handler raise: every case reads `exploited` | real host | drop assertions (1) and (2): the crash variant's flipped set can equal a "flips all" declaration; the fixture declares exactly that |
| T-E13 | `test_a_check_tampered_cell_is_a_failure_item_not_a_dropped_cell` | `readiness_failures` is `[]`: the skeleton ignores NA rows | a trial whose naive cell is NA `invalid (check tampered)` (the `disc_p` naive overlay mutates `check/` hash through a fixture hook, or a hand-built scores ledger row if the hook is not available; the hand-built form is the push test, the hook form the readiness one) | the discriminate path over a real pass | count only HB-CHK-002, not -001/-003: the sibling param goes green |
| T-E14 | `test_unbiased_failures_lists_cells_and_none_when_unreadable` | returns `[]` for both a failing and an unreadable fixture | `property.json` with one span `unbiased_ok: false`; a run folder with no scores ledger | a real graded fixture run (T-E1b's) read by the function | return `[]` on exception: the unreadable case goes green |
| T-E15 | `test_hidden_test_disagreements_three_states` | returns `[]` for all three | graded fixtures: (i) one cell where `hidden_tests_pass` true and `pass_at_1` 0; (ii) all agree; (iii) `property.json` deleted for a cell with a recorded `property_check_pass`; (iv) a cell with `pass_at_1` NA (not comparable) | the real function over a **real** graded run (X-INT join test `test_section_reads_the_real_readiness_function`, W1-H) | return `[]` instead of `None` on (iii); count (iv) as a disagreement |
| T-E16 | `test_discriminate_fails_the_trial_on_a_disagreement_or_none` | no failure item exists today | `disc_flaky` (its tests disagree with the pass) | real path | skip the call in `discriminate`: red |
| T-E17 | `test_a_leaked_temp_is_swept_before_the_write` | the temp still exists after `run` (the skeleton sweeps nothing) | a `x.json.tmp-1-<32 hex>` file and a temp **folder** beside the key | real `atomic.sweep_temps` | sweep before taking the lock, or glob `*.tmp-*` instead of `is_temp_name`: a non-temp name `x.tmp-notes` (kept in the fixture) gets deleted: red |
| T-E18 | `test_readers_skip_and_name_temps_and_never_delete` | `problems()` output has no `note:` line for the temp | a temp beside a valid record | real `problems` | the reader deletes: the temp is gone: red |
| T-E19 | `test_readiness_recomputes_the_stored_failure_list` | a record with a tampered empty `readiness_failures` and a wrong score passes | hand-built | T-E1b real record | trust the stored list: red |
| T-E20 | `test_a_discrimination_run_is_not_a_leaderboard_row` | `bench status`/the board lists the run without a label (the sweep of section 13) | a real discrimination run folder | real `status.build` and board call | skip the kind check: red |
| T-E21 | `test_variants_file_is_read_as_data_never_executed` | the skeleton ignores variants, so the sentinel file is not created; the assertion is that variants load (`flips` parsed) | `variants.py` whose module body writes `sentinel.txt` | real `ast.literal_eval` path | `importlib` the file: the sentinel appears: red |
| T-E22 | `test_expected_values_need_a_provenance_comment` | `problems()` is `[]` | `task.yaml` with an `expected` value and no comment; one with a one-word comment | real YAML text scan | drop the check |
| T-E23 | `test_a_registered_frozen_field_must_equal_its_canonical_function` | `[]` | an injected registry `{"fixture.hash": f}` and a task with a hand-derived value (HASH-A) | the real (empty) registry equals the scan of section 13 | register nothing: red |
| T-E24 | `test_container_runtime_or_linux_only_tool_fails` | `[]` | `toolchain: [docker]`; `build: ["podman", ...]` | real | match only `toolchain`, not `build` argv: second param green |
| T-E25 | `test_contract_field_defects_each_fail_with_hb_rdy_005` (parametrized over the EV-1 list of 8.2, one defect per param, built by `tests/fixtures/property_tasks/make_task.py`) | `[]` for each | one fixture task per defect | real `problems` over `make_task` trees; plus the ten real stubs on the base (all `stub`, so `[]`) | per param |
| T-E26 | `test_latent_term_in_the_prompt_names_term_and_line` | `[]` | prompt containing the term at line 3 | real | substring (not whole-word) match: a fixture with `authoriz` inside `Authorization` must NOT fail (W1-I found this false hit): mutant fails it |
| T-E27 | `test_pair_rule_one_task_or_one_base` | `[]` | BOM with one task for a property; two tasks one base | real BOM load | compare `source.repo` only (not commit): two bases at one repo pass wrongly |
| T-E28 | `test_reconciliation_detects_a_regrade_and_says_not_reconciled_without_a_run` | no HB-RDY-004; no `note:` | a real trial, then a re-grade under a changed grader fixture; a clone with `runs/` removed | real run folder | treat a missing run as a pass without the note: the note assertion is red |
| T-E29 | join check: `tests/test_profiles.py` and `tests/test_acp_record.py` unchanged and green on the merged branch | n/a (existing tests) | | | |
| T-E30 | `test_s1_real_discrimination` (X-I's task, X-E's run; readiness ring) | n/a: S1 is `stub` | S1 | real | |
| T-E31 | `test_two_discriminate_calls_for_one_task_exactly_one_proceeds` | both proceed today (the skeleton takes no lock) | two processes started together on `disc_c` | real `oslock` | take the lock after the plan step: both plan, one fails late; assert the loser raised HB-RUN-005 before any run folder exists |
| T-E32 | `test_an_incomplete_engine_run_writes_no_record_and_names_the_cell` | the skeleton returns `outcome: "skeleton"` with exit 0 | an overlay whose agent exits non-zero (a failed cell) | real engine | write the record anyway: file exists, red |
| T-E33 | `test_the_record_is_written_after_the_grading_job_closes` | no record, no ordering evidence | an overlay file that, when the deliverable runs, tries to create the final record path | real engine, grader and `create_once` | call `create_once` before `run_pass` returns: the forged file is the one that stays: red |
| T-E34 | `test_record_and_link_hold_no_absolute_path_or_username` | no files exist | `disc_c` trial under a temp root named with the `USERNAME` | real | write `str(root)` into the link: red |
| T-E35 | `test_a_measurement_plan_with_a_synthetic_combo_is_refused` | the plan is built today | a matrix with `synthetic-reference` and `kind: measurement` | real `plan.build_plan` (X-A1's refusal) | drop the refusal: red |
| T-E36 | `test_synthetic_environment_excludes_credentials` | the skeleton's launcher passes `os.environ` unfiltered, so the four names appear in the agent's recorded keys | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GH_TOKEN`, `HB_CLAUDE_OAUTH_TOKEN` set before the run | real engine | pass `os.environ` unfiltered: red |

Fixtures built by `make_task.py` use the **public** `readiness.problems` path (no private import), so a renamed internal never makes a test red for the wrong reason.

## 15. Join order, dependencies, seam requests, decisions

- **Order.** X-B1 (`create_once`, `is_temp_name`, `sweep_temps`) and X-D (`identity`, `errors.py` rows, `tests/import_graph.py`) first; X-A1 (`kind`, `SYNTHETIC_PROFILE_RECORD`, `config.HARNESSES`); then X-E's skeleton, T-E1a..T-E6, T-E17..T-E28 on the real `correctness` grader; then X-F (the property grader and host) enables T-E1b, T-E10..T-E13; X-I's S1 and T-E30 last. T-E1a does not wait for X-F, so the engine/overlay/record chain is proven before the host exists.
- **Seam requests (filed to `coord-opus-e1e4`; SR-E1 = `req-01M41H86JNZ3XPT1T1RJZJE35X`, SR-E2 = `req-01M41H86X2ENXFWMWGTHTDDHMN`):**
  - **SR-E1** (W0 §6, ADR-0016 §4, W0 §11, W0 §5): (1) the record body drops `run_id` and `grading_id` and gains `probe` and `variants` (fallback: W0 rev 2 option (a)); (2) no `bench/profiles/synthetic.yaml`, and one hunk in `plan.py` for `profile_record("synthetic")`, plus `synthetic` in `config.HARNESSES` (X-A1); (3) the record's identity excludes `builds/*` (X-D states `builds=None` semantics); (4) a row HB-RDY-011 "trial untrustworthy: a check NA row, an unreadable clock, or a hidden-test disagreement in a trial cell" (X-D); (5) `readiness.hidden_test_disagreements` and `unbiased_failures` return `list | None`; (6) `sweep_temps(target, lock)` as S-B4. Needed by: X-A1, X-D, X-E.
  - **SR-E2** (W1-I/X-I, `tasks/README.md`, X-C): (1) `oracle/variants.py` is a literal table (7); (2) the overlay paragraph in `tasks/README.md` (6); (3) W1-I's status note: flip to `ready` before discriminating (4.1); (4) X-C's `cmd_validate` line calls `readiness.problems(root, baseline=...)` and the `bench discriminate` subcommand dispatches to `discriminate.run`.
  - **Fallbacks while unanswered:** design to this text; X-E's skeleton works under either record form; sections 4.2-4.3, 5.3, 7 and 8.4 are marked **provisional (seam SR-E1/SR-E2)**.
- **Decisions made here (no Owner request needed; reversible by editing X-E's modules):** D-E1 variants are cells of the same run; D-E2 `parallelism: 1`; D-E3 a trial that is incomplete writes nothing, one that disagrees with `expected` writes a failing record; D-E4 a NA on either side of the disagreement comparison is "not comparable", counted, never silent.
- **Open measurement (not modelled):** the wall time of a 15-cell S1 trial. First X-E join check; the figure goes in `discrimination-link.json` and in `oracle/evidence.md`.

## 16. Spikes

| Id | Question | Method | Result |
| --- | --- | --- | --- |
| S-E1 | Can the real engine drive a stdlib ACP agent behind a `Launcher` with no `engine.py` edit, end a turn, and leave the overlay in the archive, with `records()==[]` and `usage_source="acp_turn"`? | A scratch script (not committed; the `FakeLauncher` shape of `tests/test_engine.py:41-77`, a 30-line stdlib agent): two synthetic cells (`synthetic-reference`, `synthetic-naive`), `engine.Engine(...).run()`, Python 3.12.x | **Confirmed.** `exit_code 0`; both cells `outcome completed, cause None, stop_reason end_turn`; the archive held `attempt-1/ws/pkg/app.py` with `ROLE = 'synthetic-reference'` and `'synthetic-naive'` per cell; no spend row; events included `cell.workspace_built`, `cell.archived`, `run.completed`. Not covered: the grading pass over the archive, 3.14.6 |
| (read) | Does a profile file for `synthetic` break existing tests? | read `tests/test_profiles.py:125`, `tests/test_acp_record.py:249` | Yes: both assert the harness set (5.3) |
| (read) | Is `status` inside the task version hash? | read `plan.py:113-115` | Yes (4.1) |

## 17. Failure modes, adversarial analysis, privacy

### 17.1 Failure-mode analysis

| Id | Mode | Disposition | Telemetry | Test |
| --- | --- | --- | --- | --- |
| F1 | A legitimate retry at the same key | **prevent**: equal bytes are a no-op (4.3) | `outcome: confirmed` | T-E5 |
| F2 | A flaky task: the same key scores differently | **detect**: HB-RDY-010, file untouched | `outcome: determinism-defect` | T-E6 |
| F3 | Crash after the temp write, before the link | **recover**: the next run sweeps and writes (9) | temp named in `note:` | T-E17 |
| F4 | Two `bench discriminate` for one task at once | **prevent**: per-task `RunLock`, HB-RUN-005 | `failed` outcome | T-E31 (two processes; exactly one proceeds) |
| F5 | A cell fails or times out in the engine | **detect**: no record, non-zero exit naming the cell and cause (4.4) | `failed-engine` | T-E32 |
| F6 | Host suspend during a grading span | **mitigate**: no record, "re-run" (4.4, 8.4) | `suspend-rerun` | T-E13c |
| F7 | A load-driven `timeout` flips a variant wrongly | **mitigate**: serial cells; **detect**: `flips` mismatch names the case and `start_ms`; **accept** residual (a slow host can still miss a bound; RV-DS W0 4's accepted residual) | `start_ms` max | T-E11 |
| F8 | The task's check is tampered by the deliverable (NA) | **detect and fail closed**: HB-RDY-011, never dropped (8.4) | `chk_rows` | T-E13 |
| F9 | The unbiased clock is unreadable | **detect**: `unbiased_ok: false` becomes HB-RDY-011 | `unbiased_failures` | T-E14 |
| F10 | Hidden tests nondeterministic | **detect**: the disagreement reader fails the trial | `hidden_test_disagreements` | T-E15, T-E16 |
| F11 | The record is hand-written to look right | **detect**: R-HOST needs the probe digest; reconciliation when a run exists; the commit is operator-reviewed (git is the witness). **Accept** residual: a hand-forged digest on a fresh clone is accepted by readiness; the pilot ring (EV-8/EV-14) re-measures every ready task, so a forged record cannot reach a verdict | `reconciled` note | T-E8, T-E28 |
| F12 | The overlay is applied to a tree the engine did not build | **prevent**: the agent writes only to its cwd = the engine's working copy (6) | | T-E2 |
| F13 | A solution overlay escapes the working copy | **prevent**: rule 4 refuses `..`, absolute, `.git/`, reparse points | | T-E3 |
| F14 | The run folder is absent on a fresh clone | **mitigate**: the record is self-contained; `reconciled: no` is printed | note | T-E28 |
| F15 | Disk full while writing | **detect**: `OSError` propagates with the path (W0 §4); no partial file (create-once) | `failed` | covered by W1-B's crash tests, not repeated |
| F16 | A task file runs code in the operator process (variants) | **prevent**: data-only read (7) | | T-E21 |
| F17 | A stale record after `task.yaml`, a check file, the catalog or the engine changes | **prevent**: the key holds the version and identity; HB-RDY-001/002 | | T-E7 |
| F18 | Platform differs (a macOS clone reading a Windows record) | **mitigate**: the key holds the platform; HB-RDY-001 names "no record for `<platform>`" and lists the platforms present | | T-E7a |

### 17.2 STRIDE-lite

**Trust boundaries.** B1: agent-written content versus the operator's committed records. In a *trial* there is no agent: the overlay is task-author content (trusted as the operator's own, hashed in the task version); the deliverable it forms is still **untrusted at grade time** (W0 §3 probe host, ADR-0018), because the reference is the task author's code but a variant or a mistaken task is not safe to assume benign. B2: the operator process reading `oracle/variants.py` and `cases.yaml`. B3: the committed `bench/discrimination` folder versus any later hidden check running agent code in the same user session (ADR-0016 §8 accepted residual). B4: the synthetic agent process (operator rights) versus the oracle tree it reads.

| Id | Threat | Disposition | Negative test |
| --- | --- | --- | --- |
| S1 | Spoofing: a hand-made record claims the real host ran | **mitigate** (R-HOST digest, reconciliation) and **accept** the fresh-clone residual (F11) | T-E8 |
| T1 | Tampering: a deliverable edits `bench/discrimination/*` during a trial's check | **transfer, named:** `bench campaign verify` after every grading pass of a campaign run (ADR-0018 §11(b), X-C, includes `git status` of this folder) and ADR-0018's job/handle rules; **mitigate:** the trial runs in a cells root outside the repo, and the record is written by `discriminate` *after* the pass and the check's job closed | T-E33 `test_the_record_is_written_after_the_grading_job_closes` (a fixture overlay that tries to write the record path: the file written by the deliverable is never the final record because `create_once` runs only after the pass; and verify names a changed tracked file) |
| T2 | Tampering: `variants.py` as code | **prevent** (7) | T-E21 |
| T3 | Tampering: path traversal in an overlay | **prevent** (6.4) | T-E3 |
| R1 | Repudiation: who produced a record | **mitigate:** the record is committed (git author); the link file holds the run id and times | |
| I1 | Information disclosure: the record or telemetry leaks a path, user name or canary | **mitigate:** the record holds task ids, hashes, metric values, case ids and outcomes only; the link file holds repo-relative paths; no `os.environ` value; canary tokens never enter either (the grader's evidence is egress-scanned by W1-F, and the digest copies outcomes, not bodies) | T-E34 `test_record_and_link_hold_no_absolute_path_or_username` (scan for the temp root, `USERNAME` and `BENCHCANARY-`) |
| I2 | The synthetic agent reads oracle solutions, then they leak into a measured cell | **prevent:** the solutions folder is read only by `synthetic_agent` in discrimination runs; a measured plan has no `synthetic` harness (`plan` refuses the harness outside `kind: discrimination`, SR-E1 asks X-A1 for the check: `kind == "measurement"` with a `synthetic` combo is HB-PLN-002-style refusal) | T-E35 |
| D1 | Denial of service: a variant or overlay that fills the disk or hangs | **mitigate:** overlay size/count caps (6.4); the engine's per-cell budget and the grader's bounds; `parallelism: 1` | T-E3 (caps) |
| E1 | Elevation: the agent process runs with operator rights and reads `HB_SYNTH_OVERLAY` | **accept:** it is the operator's own script reading the operator's own task files. Residual: none beyond ADR-0013 | |
| E2 | Elevation: `HB_CHECK_*` or credential names reach the synthetic process | **prevent:** `SyntheticLauncher.argv_env` passes `os.environ` through the same denylist (`profiles.DROP_EXACT`, `DROP_PREFIXES`) the real profiles use, so `ANTHROPIC_API_KEY` and the Claude/Codex/Copilot prefixes are removed | T-E36 `test_synthetic_environment_excludes_credentials` (sets the four names, the agent writes its `os.environ` keys, none present) |

### 17.3 Privacy (LINDDUN-lite)

The slice touches **no personal data**: task ids, hashes, scores, case ids. Operator identifiers are kept out of the record and the link file (I1, T-E34).

## 18. Residual risk and unknowns

- R1 Wall time of the 15-cell S1 trial is not measured (Inferred minutes).
- R2 Score-row field names and the evidence-pointer directory (`Score.evidence`) are read through existing readers I did not open line by line (`views.py`, `grade/runner._score`); the skeleton commit confirms them. **assume:** `scores/<grading_id>.jsonl` exists as W1-C writes it; confirm: read `runner.py` at the skeleton; breaks if false: `_pass_scores` is the single function to change.
- R3 `identity.manifest(builds=None)` and the `profiles/<h>` set are W1-D text, not code (4.1).
- R4 The synthetic agent was spiked on Python 3.12, not 3.14.6.
- R5 R-HOST cannot stop a careful forgery on a fresh clone (F11); the pilot ring is the second measurement.
- R6 The `clauses.json` hand-off (7) is a small new contract with every task author that declares clauses.

## Gate

**Reviewers (leave pending; the author never clears a veto):** RV-PAT (Patterns Expert), RV-SIM (Simplifier, soft veto), RV-TA (Test Architect, **hard veto**), RV-SEC (Security & Identity, **hard veto**).

```
GATE w1-e-discriminate · Patterns Expert · pending
GATE w1-e-discriminate · Simplifier · pending
GATE w1-e-discriminate · Test Architect · pending
GATE w1-e-discriminate · Security & Identity · pending
```
