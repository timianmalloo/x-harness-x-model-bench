---
id: "design-eval-discriminate"
title: "W1-E design: discriminate, the synthetic profile and the readiness check (EV-7; X-E)"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 design slice W1-E; builds in E1 (X-E: discriminate.py, readiness.py, synthetic_agent.py)"
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
  and grading pass (and so, for check-based properties, the real probe host), and writes a create-once, idempotent
  discrimination record; readiness.py then refuses `ready` unless that record exists, matches the current task
  version and engine, was made by the real host where the property has one, and every expected value is observed.
  Settles the record's data model (no run id in its body, so a legitimate retry is a no-op; R-98), the synthetic agent
  (a stdlib ACP process behind Launcher; engine.py unchanged, Verified by spike S-E1), the one overlay path rule, the
  disagreement and clock-failure readers, the sweeper, and names every red-first test with its fixture, real-wiring
  partner and mutant. Revision 2 applies the four first-round reviews.
---

# W1-E design: discriminate, the synthetic profile and the readiness check (EV-7)

**Author:** Claude Sonnet 5.5 (`claude-sonnet-5-5`), 2026-10-03. Rev 1 session `w1e-discrim-e1e4` (base `b88746d9`); **rev 2** session `w1e-discrim-r2-e1e4` (main merged: W0 rev 5, R-98). Branch `design/eval-discriminate`. T2, fan-out 0. Gate record: the Gate section.

Confidence labels: **Verified** (I opened the file or ran it on this base), **Inferred** (reasoned, not observed), **Flagged** (a contradiction or gap the reader must resolve). A sibling design on a branch is cited by its section; it is Verified as *text*, not as code. **R-98** is cited from the Coordinator's dispatch text; its ruling entry is not yet in `docs/notes/rulings.md` on this base (Flagged: W0 rev 6, owed, carries it).

## Status

| | |
|---|---|
| **Completed** | Data model; the record (R-98); synthetic agent and launcher (spike S-E1); the one overlay path rule; variant trial; real-host control scoped by `CHECK_PROPERTIES`; readiness items EV-1/EV-7 to HB-RDY to test; the readers (`list \| raise`); sweeper; E7 surface list; failure modes; STRIDE-lite; telemetry; test plan folded to 25 tests plus 3 join checks; rev 2 review disposition |
| **Remaining** | Gate re-review (RV-TA, RV-PAT); seam answers (section 15, SR-E3); X-E's build, which waits on X-A1 (`kind`, `SYNTHETIC_PROFILE_RECORD`, `CHECK_PROPERTIES`), X-B1 (`create_once`), X-D (`identity.for_task`, HB-RDY-011 row), X-F (`grade/_env.py` first, then the host) |
| **Best next action** | Re-review; then `/implement` X-E starting with the skeleton commit of section 14.1 |

## 1. What this slice owns, and the obligations routed to it

One responsibility: **a property task is `ready` only because the engine itself showed that its hidden check discriminates, and the proof is a record nobody can fake by hand or lose by retrying.** It owns `src/harness_bench/discriminate.py`, `readiness.py`, `synthetic_agent.py` (all three grade class, W0 §9). Its `profiles.py` hunk is **empty** (5.3, 5.1: no denylist copy exists). It owns `bench discriminate`'s composition (the subcommand's `cli.py` line is X-C's, section 12).

| # | Obligation (source) | Design element | Section | Test |
| --- | --- | --- | --- | --- |
| O1 | RV-TA W1-I D4: readiness refuses `ready` without a real-host record | Rule R-HOST (check-based properties only, `config.CHECK_PROPERTIES`): the record's `probe` digest shows the real probe host ran every declared case; `bench validate` fails otherwise (HB-RDY-001) | 8.2 | T-E8 |
| O2 | RV-TA W1-I D1: the variant test runs on the real host before `ready` | Variants are synthetic cells of the same run; the record holds each variant's observed values; readiness compares them with the declared ones (HB-RDY-003) | 7 | T-E11, T-E12 |
| O3 | Seam `req-01M41DM7XQG9GYVR32TJ762V67`: never drop an HB-CHK-002 count or a failed clock reading silently | Rule R-NA: any trial cell with an HB-CHK-001..004 NA row, an `unbiased_ok` false span, or an unreadable reader is an HB-RDY-011 item and **no record is written** (4.4) | 8.4 | T-E13, T-E14 |
| O4 | R-93 / R-96: the disagreement reader's three states | One function: a list, `[]`, or a raised error carrying the reason; the trial fails on a non-empty list or a raise | 8.3 | T-E15, T-E16 |
| O5 | RV-DS W0 F2 / R-98: the record is idempotent | The body is a pure function of (task version, engine, platform, scores, probe, variants); the run link is local, written after created-or-equal only | 4.2, 4.3 | T-E4, T-E5, T-E6 |
| O6 | RV-DS W1-B F3: X-E owns the sweeper for discrimination temps | Per-task lock, `sweep_temps` before a write, `is_temp_name` skip-and-name in readers | 9 | T-E17 |
| O7 | RV-PAT W1-I 7: state the solutions-overlay rule | Section 6 states it once, in one function (`safe_relpath`, `overlay_files`) | 6 | T-E2, T-E3 |

**Done when (the plan row):** Gate PASS incl. Security (the Gate record); the SCAN-A red fixture named (section 8.2, fixture `scan_a`, test T-E10); the synthetic agent mechanism (section 5; a stdlib ACP fake behind `Launcher`, no `engine.py` edit, **Verified** by spike S-E1, section 16).

## 2. Inputs read (quoted where a control rests on them)

- ADR-0016 §4: "**Grain:** one file is exactly one discrimination trial of one task version under one engine identity on one platform." **R-98 amends the body**: no `run_id` or `grading_id`; the ADR amendment note and W0 rev 6 are the Coordinator's.
- ADR-0016 §5: "its 'driver' copies `tasks/<ID>/oracle/solutions/<reference|naive>/` ... into the working copy and ends the turn. Everything else is the engine's own path".
- W0 §2 rev 5: the `expected` set is `runner.applicable(catalog, graders, property)["property"]`, compared "by exact equality after both sides pass through one function, `grade/property.py: at_scale`"; check-based and check-less properties (`config.CHECK_PROPERTIES = {security, resilience}`; `rework`, `no-guessing`, `simplicity` have **no** `oracle/check/`); the `ready` order; the variants literal; the overlay paragraph.
- W0 §6 rev 5: `identity.for_task(m, task)` "the one definition of a manifest seen from one task"; `manifest(root, tasks, builds=None)` writes no `builds/*` key; `profiles/<h>` covers `profiles.HARNESSES`; the record gains `probe` and `variants`; HB-RDY-002 against a campaign compares with `identity_hash(identity.for_task(<baseline manifest>, task))`. **W0 §6 still shows option (a) for a second production; R-98 overrides it** (4.3).
- W0 §7 condition 3, R-93, R-96 (8.3); W0 §11 HB-PLN-004 and HB-RDY-001..011.
- Merged W1-F rev 3 (`docs/design/eval-property-grader.md`): `Score.evidence` is the `property.json` **file** (line 348); `check.hosts` is the path of `out_dir/check/hosts.jsonl` (line 155); `grade/_env.py` holds the grader's one allowlist (`grading_env`, §5.9).
- Code read on this base: `engine.py:69-85` (`Launcher`), `:618-634` (`_run_cell`, `check_build`), `:852-854`; `profiles.py:36-41,106` (the credential denylist inside `cell_env`); `plan.py:240,282-295` (`builds` must hold the harness); `config.py:34` (`HARNESSES` has five names, no `synthetic`); `oslock.py:46-60`; `tests/test_engine.py:41-77`.

## 3. Bounded context, ubiquitous language, aggregates

**Context:** *Task readiness*, inside the Evaluation Campaign context. Language: **trial**, **role** (`reference`, `naive`, or a variant name), **overlay**, **key** (task version, engine identity, platform), **expected set**, **probe digest** (the per-role summary of what the real host did).

| Aggregate | Root | One invariant it protects | Referenced by identity only |
| --- | --- | --- | --- |
| `DiscriminationTrial` (the record) | file at `bench/discrimination/<task>/<tv16>-<id16>-<platform>.json` | **One discrimination result of one key: a key holds at most one record, and a second production either equals it or is a reported determinism defect.** | task version hash and engine identity hash (by value in the key); the run by a local link (4.3) |
| `ReadinessVerdict` | none, never stored | n/a: a derivation (DM7) of {task files, catalog, record, current identity} | |

`readiness_failures` is stored in the record (W0 §6) but **readiness never trusts it**: it recomputes the list from `scores`, `expected`, `probe` and `variants` and compares (T-E18 tampers the stored list). The stored list is the audit copy of what the author saw.

## 4. Durable representation

### 4.1 Grain, measures, history

- **Grain:** one row is exactly one trial of one task version, under one engine identity, on one platform. **Measures:** each score is a non-additive per-cell value; nothing is summed. **History rule:** the record is an immutable fact. A new task version or identity is a new key (Type-2 by key). Nothing is updated.
- **Engine identity, for the key (W0 §6 rev 5; PAT 2, TA 2).** `identity_hash(identity.manifest(root, [task], builds=None))`, hashed with `ledger.canonical`. For a campaign, HB-RDY-002 compares the record's hash with `identity_hash(identity.for_task(<baseline manifest>, task))` and, on a difference, lists `identity.diff(<those two manifests>)`. `for_task` is the one definition of "seen from one task": it drops every `builds/*` key and every `tasks/<other>` key (the baseline holds a `tasks/<id>` for every campaign task, so a drop of `builds/*` alone never equals a single-task hash). `profiles/<h>` covers `profiles.HARNESSES`. **`readiness.py` contains no hand-rolled drop**: a grep test (T-E7) asserts no `startswith("builds/")` and no `builds/` key literal in `readiness.py`.
- **Status is inside the version hash (Verified, `plan.py:113-115`).** The order is W0 §2 rev 5: **flip to `ready`, discriminate, commit task and record together.** A failed trial writes no record; the task is reverted to `draft` before any commit (`bench validate` names HB-RDY-001 meanwhile).

### 4.2 The record (W0 §6 rev 5 and R-98)

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

- **No `run_id`, no `grading_id`** (R-98; W0 §6's JSON still shows them: Flagged, rev 6). `probe` is present **only when the task's property is in `config.CHECK_PROPERTIES`** (security, resilience). For a check-less property (`rework`, `no-guessing`, `simplicity`) there is no host and no `probe`; the real-engine/real-grader evidence is `scores` itself, and R-HOST does not apply (8.2). `variants` is present only when the task declares variants.
- Values are `at_scale` normalised (a JSON int, a string with exactly the catalog scale of decimals, or `{"na": "<reason>"}`). **Bytes** are `ledger.canonical(obj)` and are written once with `atomic.create_once`.
- **Why `probe` copies a digest:** `runs/` is gitignored, so on a fresh clone the run does not exist and `bench validate` must still decide. The digest copies fields of `property.json` (`check.deliverable`, `check.cases[].outcome`) and the count of `end: ready` lines in the file at `check.hosts` (`hosts.jsonl`), all read **through the pointers `property.json` holds** (5.5).
- **The body must equal its name (SEC 7).** Readiness checks the body's `task` equals the folder name, `platform` equals the name's platform, and `task_version[:16]`, `identity_hash[:16]` equal the name's prefixes. A mismatch is HB-RDY-001 "record name does not match its body".

### 4.3 Idempotence and the run link (R-98)

- **Idempotence.** The body holds no run or grading id, so a retry at an unchanged key produces equal bytes and `create_once` returns "equal, no-op" (W0 §4: "True = created; False = path existed with equal bytes"). **There is no option-(a) branch** (RV-PAT 1, TA 3).
- **Why `discriminate.run` still reads the key first:** to tell why bytes differ. A difference at an existing key is **HB-RDY-010, raised before HB-LED-007** (the file is never touched, so the two codes cannot both be right). The message names the **first differing JSON path** (`scores.naive.exploit_probes_blocked`, `probe.reference.cases.inj-3`), the stored value and the new value (PAT 9). T-E5 asserts the code, the path, and that the stored bytes are unchanged.
- **The link** is `runs/<run_id>/discrimination-link.json` (`bench-discrimination-link/1`), local and gitignored with `runs/`. Fields: `record_stem` (the record's file name without `.json`, the key field), `record_sha256`, `run_id`, `grading_id`, `recorded_at` and `mono_ns` (the ledger `stamp`), the timings and counts of section 11. **It is written only after `create_once` returned created or equal, and never after HB-RDY-010, a failed trial, or HB-RDY-011** (R-98 condition 1; T-E5b).
- **Reconciliation (HB-RDY-004) never degrades to a pass.** Readiness picks the link with the newest `recorded_at` stamp among `runs/*/discrimination-link.json` whose `record_stem` equals the record's stem. It prints exactly one line, `reconciled: yes` or `reconciled: no (<reason>)`, `<reason>` from this closed set: `no link`, `run folder absent`, `no completed grading pass`, `record hash differs from the link`, `run is not a discrimination run`, `run task version differs`, `run combos are not the synthetic ones` (SEC 6; `plan.json` `kind`, task version, combos). `reconciled: yes` needs all checks green **and** the recomputed scores equal to the record's; only a score difference fails (`HB-RDY-004: <metric> copy <a>, run <b>`). `no (...)` never fails and never counts toward readiness. T-E6 has one parametrized case per reason. **Partly accepted (SIM 3):** the lookup scans `runs/*/` because R-98 fixes the link's place under the run folder; the key field makes the match a string compare. Re-open trigger: the scan is measurably slow with thousands of runs.
- **A forged mid-trial record (TA 5).** At trial start the key must be absent or hold a record (the confirm path). If it was absent at start and a file exists at the key **before the write**, that is an HB-RDY-011 item ("record appeared during the trial"), nothing is written, and the file is left for the operator. `create_once` never overwrites, so without this check a file the deliverable pre-created would be read as the stored record. B3 (a deliverable that edits the committed folder with operator rights, ADR-0016 §8) stays the named residual; `bench campaign verify` witnesses it (T1).

### 4.4 When no record is written (changed by TA 4)

`discriminate` writes a record only when the trial **ran to the end and has no HB-RDY-011 item**. Nothing is written, and the exit is non-zero naming the cell and cause, when: a cell did not complete (`failed`, `timed_out`, the run stopped); the grading pass raised; any HB-RDY-011 item exists (a check NA row, a failed clock span, an unreadable or disagreeing reader, a not-comparable cell, a record that appeared mid-trial, a host suspend). **The retry trap is closed:** a transient fault (a bound fired under load) cannot leave a record that a clean retry then contradicts as HB-RDY-010. A trial that ran cleanly but **disagrees with `expected`** (HB-RDY-003: a task defect) is still written, with `readiness_failures` non-empty; its fix changes the task version and so the key. (A mismatch is not transient by construction: a host fault is an NA row, which is HB-RDY-011, never a wrong value.)

### 4.5 Writer and compute reader of every persisted field (DM15)

| Field | Writer | Compute reader |
| --- | --- | --- |
| record: `task`, `task_version`, `identity_hash`, `platform` | `discriminate.run` | `readiness` (HB-RDY-001/002), `bench campaign verify` (name = key; X-C) |
| `scores`, `probe`, `variants` | `discriminate.run`, copied from the grading pass and `property.json` | `readiness` (HB-RDY-003, R-HOST, variant compare), reconciliation (HB-RDY-004) |
| `expected` | `discriminate.run`, copied from `task.yaml` at the trial | `readiness` (recomputed from the current `task.yaml`; a difference is a tamper tell) |
| `readiness_failures` | `discriminate.run` | humans; `readiness` recomputes and compares (T-E18) |
| `discrimination-link.json` | `discriminate.run` | `readiness` (reconciliation), the operator |
| `oracle/solutions/<role>/` overlay tree | task authors (X-I, X-L) | the synthetic agent, at the trial only |

## 5. The synthetic profile and agent (Strategy behind `Launcher`; no `engine.py` edit)

### 5.1 Mechanism

`synthetic_agent.py` is a stdlib-only script run as `<sys.executable> <path of synthetic_agent.py>`. It speaks the minimum ACP the driver needs (`initialize`, `session/new`, `session/prompt`). On `session/prompt` it applies the overlay (section 6) to its **cwd**, which the engine sets to the cell's working copy (`engine.py:696`, Verified), then replies `stopReason: end_turn`. `SyntheticLauncher` (in `discriminate.py`) satisfies the `Launcher` protocol (`engine.py:69-85`):

| member | value | why |
| --- | --- | --- |
| `harness` | `"synthetic"` | the cell's harness. `config.HARNESSES` does **not** list it (`config.py:34`, Verified); W0 §6 rev 5 has X-A1 add it, but the discrimination path does not need it (5.2) |
| `credential_names`, `credential_kind` | `frozenset()`, `"none (synthetic)"` | no login is read or copied |
| `usage_source` | `"acp_turn"` | with no usage in the reply, `_spend` returns None ("not recorded", never 0; `engine.py:857-863`) |
| `mode`, `set_model`, `shutdown_grace` | `None`, `False`, `1.0` | |
| `check_build()` | returns the constant `{"version": SYNTHETIC_VERSION}` | **No re-hash (SIM 4).** `synthetic_agent.py` is grade class (W0 §9), so the identity manifest already hashes it and the record's key carries that identity; the plan and its cells run in one process. `plan.builds` needs the key (`plan.py:288-290` raises HB-PRE-007 without it); `discriminate.run` passes `builds={"synthetic": {"version": SYNTHETIC_VERSION}}` itself (PAT 11). `tools.check_build` is called for `copilot` only (`plan.py:295`) and `tools.LAYOUT` has no synthetic entry, so neither is reached |
| `seed`, `clean` | create the home folder; nothing | |
| `argv_env(cell, home, traceparent)` | `[sys.executable, <agent path>]` and an environment built **from the grader's allowlist**: `grade/_env.py: grading_env()` (X-F's one definition) plus exactly `HB_SYNTH_OVERLAY=<abs overlay path for cell["combo"]>` and `TRACEPARENT` | **One rule (SEC 2, 8; PAT 6).** Never `os.environ` and never a denylist: an allowlist cannot miss a new credential name (the denylist `profiles.DROP_EXACT` lacks Google/Gemini/xAI/AWS/HF/NPM names). Because no denylist is re-implemented here, there is nothing to extract from `profiles.cell_env` (PAT 6's fix was for the denylist form); `profiles.py` stays untouched |
| `records`, `read` | `[]`, never called | no native record exists; `_read_records` gets an empty list (`engine.py:852-854`) |

**Spike S-E1 (run, section 16):** the real `engine.Engine`, with this launcher shape and a prototype agent, ran two cells to `outcome completed, cause None, stop_reason end_turn`; the overlay file was present in each cell's archive; no spend row; `engine.py` was not edited. Not covered: grading the archived tree (X-F's path) and Python 3.14.6 (the spike ran 3.12).

### 5.2 Cells, combos, matrix

A trial is one run of `kind: "discrimination"` (W0 §5). Combos: `synthetic-reference`, `synthetic-naive`, and `synthetic-v-<name>` per declared variant (`^[a-z0-9]{1,16}$`); each `{harness: synthetic, model: "synthetic-1"}`. **`discriminate` builds its `bench-matrix/1` in memory and calls `plan.build_plan` directly; it does not call `config.validate_matrix`** (the only reader of `config.HARNESSES`, `config.py:117-118`; PAT 7), with `packs: ["off"]`, one arm, rep 1. The combo-to-overlay map is a table built from validated role names (never a string split of a label; SEC 10). The task id is matched against the `tasks/` listing before it becomes a path part (lock name, record folder, run id). **Inferred** from W1-A that an `off` arm needs no pack clone; T-E1a confirms it.
Run id: `disc-<task lowercased>-<tv[:8]>-<UTC yyyymmddThhmmss>`; every cell label matches `config.LABEL` (at most 80 characters; the longest case is about 35).

### 5.3 What is, and is not, a profile

W0 §6 rev 5 (granted): no `bench/profiles/synthetic.yaml` (a fourth stem turns `tests/test_profiles.py:125` and `tests/test_acp_record.py:249` red). `plan.profile_record(root, "synthetic")` returns `plan.SYNTHETIC_PROFILE_RECORD` (X-A1). X-E's `profiles.py` hunk is **empty**.

### 5.4 Exclusion from leaderboards, measurement and the qualification suite

Structural: `synthetic` is in neither `profiles.HARNESSES` nor `tools.LAYOUT`, so the qualification suite never sees it; `build_plan` refuses a **measurement** plan naming a `synthetic` combo (HB-PLN-004 naming the combo; X-A1). The remaining readers are not X-E's files, so this slice states one behaviour and asks (seam **SR-E3**, section 15): every reader that takes a run id **refuses** a run whose `plan.kind != "measurement"` with HB-PLN-004 naming the kind, namely `bench run`, `attach`, `pilot attach`, `campaign.run_side_check`, the report and the board's run listing (SEC 1, TA 8); `bench status` only **labels** it (`kind: discrimination`; read-only, harmless). T-E19 drives each with a real discrimination run folder; the test joins at X-INT and its owners are X-C (`cli.py`, `status.py`, `campaign.py`) and X-A1 (`views.py`).

### 5.5 Evidence is read through pointers only (PAT 4, TA 12)

`discriminate` reads every evidence file through the pointers in `property.json` (`Score.evidence` is that **file**): `check.deliverable`, `check.cases`, `hidden_tests[tree]`, `spans`, `check.hosts` (the path of `hosts.jsonl`; the count of `end: ready` lines, one host per case, so `hosts_ready == len(cases)`), and for variants `check.clauses`. W1-F rev 3 has no `check.clauses` pointer yet; until SR-E3 (2) is granted, the path is `<dir of Score.evidence>/check/clauses.json` (W1-F: evidence dir `out_dir/check`), marked **provisional (seam SR-E3)**. A pointer that does not resolve fails closed (HB-RDY-011), never a pass.

## 6. The solutions overlay rule (O7): one function, one rule

**The rule.** A synthetic cell's final tree is the **engine-built working copy** (`workspace.task_source` then `cell_working_copy`) with the role's overlay applied by the synthetic agent, inside the cell, to the working copy's root:

1. The overlay is `tasks/<ID>/oracle/solutions/<role>/`. A variant's overlay is a materialised copy of `reference` with the variant's edits applied (section 7), held under the trial's run folder, never in the task folder.
2. Every regular file under the overlay is copied to the **same relative path** in the working copy, creating folders and replacing a file already there. A solution ships **only the files it changes or adds**.
3. **No file is deleted or renamed.** (`assume:` no E1 task needs a deletion; confirm: S1's and S2's overlays hold only replacements; breaks if false: a stale file the check sees. Upgrade trigger: a task whose naive needs a deleted file; then a `delete:` list file, a design change.)
4. **Refused, with a named error, before any copy.** The rule is defined **once**, in `synthetic_agent.py` (stdlib-only, importable as `harness_bench.synthetic_agent` and runnable as a script):
   - `safe_relpath(rel: str) -> PurePosixPath` raises on: an absolute path or drive/UNC prefix; any `..` or empty segment; a first segment `.git`; a `:` in a component (an NTFS stream); a trailing dot or space; a Windows device name as a stem (`CON PRN AUX NUL COM1-9 LPT1-9`, with or without an extension).
   - `overlay_files(root: Path) -> list[Path]` scans with `os.scandir` (never following a link) and raises on: a symlink, junction or other reparse point; a non-regular file; two paths equal after NFC-normalised case-fold; more than 2000 files or 8 MiB (`simplify:` constants; upgrade trigger: a legitimate solution above them). Each name goes through `safe_relpath`.
   - **Destination (SEC 3):** before each write the agent `lstat`s every parent below the cwd and the destination, and refuses a link, reparse point or non-regular file already in the **working copy** (a pinned third-party base tree can hold symlinks). The refusal is a non-zero exit, which the engine records as a failed cell.
   - **Callers:** `readiness.contract_failures` (HB-RDY-005), the agent (re-check at run time), and `edits[].file` of a variant (7). W1-F's `_copy_tree` stays separate by design: it copies a grading tree, is X-F's, and the agent cannot import `harness_bench` helpers. T-E3 runs each bad input through **both** callers and asserts the same verdict.
5. The task layout under `oracle/solutions/` is the only one a property task may use. A property task that has `oracle/reference/` and no `solutions/` fails HB-RDY-005. Multi-turn is **not built in E1**: a task with `turns` fails discriminate with HB-RDY-005 `not built in E1`.
6. `tasks/README.md` carries this paragraph (W0 rev 5 wrote it). W1-I cites this section.

**Why the agent copies inside the cell, not the launcher beforehand:** the point of EV-7 is that the tree was built and handed over by the engine's own path (ORCL-A). T-E2 holds it.

## 7. Variants on the real host (O2; RV-TA W1-I D1)

**Contract with the task (W0 §2 rev 5).** `oracle/variants.py` holds one top-level `VARIANTS = {...}` literal; names match `^[a-z0-9]{1,16}$`; each entry has `flips`, `clauses`, `edits[{file, old, new}]`. X-E reads it with `ast.literal_eval` of that one assignment; **the file is never imported or executed** (T-E11 asserts a sentinel is not created). Hardening (SEC 5): the file is read with a size cap (64 KiB); more than one `VARIANTS` assignment, a non-literal value, a syntax or recursion error, a bad name, or a `clauses` text longer than 200 characters is HB-RDY-005; `edits[].file` goes through `safe_relpath` (6.4) **before the first read**, so `..` or a rooted path writes nowhere; `old` must occur **exactly once** (0 or n matches is HB-RDY-005 `variant <name> edit does not apply`). The record copies the **declared** clause text only (never bytes read from `clauses.json`).

**Trial.** For each variant, `discriminate` copies the `reference` overlay to `<run>/variants/<name>/`, applies the edits, and adds a combo `synthetic-v-<name>` to the **same** run, so it is built by the engine path and graded by the real grading pass (and the real probe host for check-based properties). Cells run with `parallelism: 1` (`simplify:` ceiling serial; upgrade trigger: a trial longer than the operator accepts) so host load does not depend on cell order. S1's 15-cell wall time is **not measured** (Inferred minutes); section 11 emits it.

**Compare, per variant.**
- **Check-based property** (security, resilience): (1) `hidden_tests_pass` true, (2) `deliverable == "ran"`, (3) the flipped set equals `flips` (a *flipped* case has an outcome that is not `blocked` or `passed`), (4) the deciding clauses equal `clauses`.
- **Check-less property** (rework, no-guessing, simplicity; TA 1): there is no host and no case. (1') `hidden_tests_pass` recorded; asserted true unless `property_check_pass` is a declared flip (R-109); **erratum (Coordinator #47, CR47-1 and CR47-2):** the value is the helper's `strategy.<prop>.hidden_tests_pass`, lifted to the top level of `property.json`, and a cell with no value is a not-comparable cell, an HB-RDY-011 item (8.3) for a check-less task as for a check-based one; (3') `flips` lists **metric ids** of the narrowed set whose observed value differs from the reference role's; (4') `clauses` map a metric id to the clause name `property.json` records (simplicity: `clause: scope`, W0 §7). **assume:** the property grader writes `property.json` with `hidden_tests` and `clause` for check-less properties as well (W0 §7 says the simplicity clause is "recorded in `property.json`"); confirm: W1-L designs and X-F at the skeleton; breaks if false: check-less variants cannot be compared and fail closed as HB-RDY-011 (never pass); SR-E3 (2) asks. The simplicity `v-laundered` variant flips `property_check_pass` with clause `scope`, which (3') and (4') express.
The results go into the record's `variants` (4.2). A variant whose recomputed `flips`, `clauses` or assertions differ from the declared ones is **HB-RDY-003** naming the variant, the case or metric, and both values; a declared variant absent from the record is HB-RDY-001 (TA, PAT 3). The crash variant (every handler raises) must fail (1) or (2), not pass as a flip: a broken exchange reads `exploited` (W0 §3), so (3) alone would call a crash a flip (T-E12); for a check-less variant, (3') refuses a crash wherever the primary is not a declared flip, and (4') wherever the declared clause is a ceiling clause (R-109).

## 8. Readiness: `readiness.py`

### 8.1 API

```python
@dataclass(frozen=True)
class Failure: code: str; item: str; detail: str            # "HB-RDY-003", "exploit_probes_blocked", "reference expected 1.0000, observed 0.0000"

def contract_failures(root: Path, task_id: str) -> list[Failure]        # 005, 006, 007(task-local part), 008: no run needed
def record_failures(root: Path, task_id: str, *, baseline: Mapping | None = None) -> list[Failure]   # 001-004, 010-011, R-HOST, variants
def problems(root: Path, *, baseline: Mapping | None = None) -> list[str]   # what cmd_validate prints: "x <code> <task>: <item>: <detail>"
def hidden_test_disagreements(run_dir: Path, grading_id: str) -> list[str]   # 8.3; raises BenchError("HB-USR-002", <reason>) when it cannot run
def unbiased_failures(run_dir: Path, grading_id: str) -> list[str]           # 8.4; same
```

**The readers raise; they never return a bare `None` (PAT 8).** The reader that cannot run raises `BenchError("HB-USR-002", "<reason>")`; callers convert (R-96's third state: the `hidden-test-agreement-not-recorded` element carries the reason, no count, no ids). In the discriminate path the conversion is an HB-RDY-011 item whose detail is the reason. This is the W0 rule ("raise and convert") and W0 §7's `list[str] | None` signature is read as that conversion at the caller. **Flagged** for rev 6 to state it in one line.

`problems` covers every property task (a `task.yaml` with a `property:` block; 10 on this base, **Verified** `grep -l "^property:" tasks/*/task.yaml`, all stubs). It returns nothing for a `stub`; for a `draft` only `contract_failures`; for a `ready` task all of it. Pair rule HB-RDY-007 is evaluated across the BOM by `problems`. `cli.py` `cmd_validate` calls `problems` (W0 §2; the line is X-C's, SR-E2 re-states it); a campaign path passes `baseline`.

### 8.2 EV-1 / EV-7 bullet to item to code to test

| EV bullet | Item and rule | Code | Test |
| --- | --- | --- | --- |
| EV-7 b1: a record with the current task version hash | the file `<tv16>-<id16>-<platform>.json` exists **and** its full `task_version` equals the current hash; the body equals its name (4.2). A stale one for the same task is named. A platform with no record lists the platforms present | 001 | T-E7 |
| (O1) b1': made by the real host | **R-HOST, only when `property.name in config.CHECK_PROPERTIES`** (TA 1): for every role, `probe.deliverable == "ran"`, `set(probe.cases) == the declared case ids`, `probe.hosts_ready == len(cases)`. A record without `probe` fails "record lacks real-host probe evidence". **For a check-less property** R-HOST is not applicable; the real-engine/real-grader evidence is `scores`, and a `probe` key in such a record is itself a failure (HB-RDY-001 "probe on a check-less task") | 001 | T-E8 |
| EV-7 b2: identity equals current (or baseline) | key identity as 4.1; with `baseline`, `identity_hash(for_task(baseline, task))`; `identity.diff` names components | 002 | T-E7 |
| EV-7 b3: reference primary is 1 | `scores.reference.property_check_pass == 1` | 003 | T-E7 |
| EV-7 b4: other reference metrics equal expected | for each metric of the narrowed set (`runner.applicable(...)["property"]`, imported), `at_scale(observed) == at_scale(expected)`; `{na: r}` equals only `{na: r}` | 003 | T-E10, T-E7 |
| EV-7 b5: naive primary 0, secondaries equal | same, role `naive` | 003 | T-E7 |
| (O2) variants | recompute the 7 compare from `variants` and the current `variants.py` | 003 / 001 | T-E11 |
| EV-7 b6: SCAN-A shape | fixture `scan_a` (below) | 003 | T-E10 |
| EV-7 b7: expected has provenance (GLD-A) | each `expected.<role>.<metric>` value carries a `#` comment of at least three words in `task.yaml`'s raw text (a presence check; independence from the grader's output stays a review item) | 005 | T-E24 |
| EV-7 b8: frozen value equals the canonical function (HASH-A) | **deferred to X-LG in E4 (RV-SIM 1).** Scan on this base: no property task carries a frozen field (`grep -l statement_hash tasks/*/task.yaml` = G1, G2, `_template`). No registry, no HB-RDY-009 code path and no test are built in E1; SR-E3 (3) moves the W0 §11 row's phase | 009 (E4) | none in E1 |
| EV-7 b9: container runtime / Linux-only tool | `toolchain` entries and `deliverable.build`/`start` argv[0] matched against `CONTAINER_RUNTIMES` and `LINUX_ONLY` named constants | 008 | T-E24 |
| EV-1 contract fields | `property.name` in `config.PROPERTY_NAMES`; `latent_requirement`; `evidence_paths` each exist in the base tree; `latent_terms`; `primary_metric` equals the catalog's one primary; `graders` contains `correctness` and `property`; `expected` present for every metric of the narrowed set or `{na}`; **`oracle/check/` with its entry and `cases.yaml` present iff the property is in `CHECK_PROPERTIES`, in both directions** (rev 5); **`ceilings.outside_radius_lines` an int for simplicity** (rev 5); **case ids match `^[a-z0-9][a-z0-9_-]{0,31}$`** (rev 3); **a loopback task declares exactly one of shapes (a)/(b)** (E4, parsed and refused in E1); the `variants.py` grammar (7); `interface`/`app.kind`/`kind` inside what E1 builds; `env` names in `_env.TOOLCHAIN_ENV` or `HB_CHECK_*`, none in the profiles denylist; `paths` relative and inside the root; `oracle/solutions/{reference,naive}/` present; overlays pass `overlay_files` | 005 | T-E24 |
| EV-1 latent terms not in the prompt | no `latent_terms` entry occurs in `prompt.md` (case-insensitive, **whole-word**: `authoriz` in `Authorization` must not fail); names term and line | 006 | T-E24 |
| EV-1 two tasks per property, different bases | pair rule over the BOM; "different base" = different `source.repo` + `source.commit` | 007 | T-E24 |
| ADR-0016 §4 read-time reconciliation | 4.3 | 004 | T-E6 |
| W0 §6 second production | in `discriminate` (4.3) | 010 | T-E5 |
| O3, O4 | trial untrustworthy | 011 | T-E13..T-E16 |

**The SCAN-A red fixture:** `tests/fixtures/property_tasks/scan_a/` is a minimal in-process task (`callable`) whose `deliverable.build` writes `build/out.txt`, and whose check carries a probe `scan-1` that reads the deliverable tree afterwards and calls any file outside `src/` an artifact, so the **reference's** mandated build output flips `scan-1` to `exploited`. Reference observed: `exploit_probes_blocked` `"0.8000"` against expected `"1.0000"` (4 of 5 probes blocked), and `property_check_pass` 0 against expected 1. T-E10 runs it through the real discriminate path and asserts the record's `readiness_failures` and `problems()` name the metric, expected and observed. The sibling `scan_a_secondary` keeps the primary at 1 and gets only the secondary wrong.

### 8.3 `hidden_test_disagreements` (O4; R-90 condition 3, R-93, R-96)

Quoted (R-96): "list non-empty -> the warning with count and ids; empty list -> no element; `None` -> the `hidden-test-agreement-not-recorded` element with the reason, no count, no ids". Here the third state is a **raise** carrying the reason (8.1), converted by the caller.
- **A list of cell ids**: the cells of a property task where the pass recorded both `property.json.hidden_tests[final tree].hidden_tests_pass` and a `pass_at_1` row with a value, and `hidden_tests_pass != (pass_at_1 == 1)`. Sorted. `[]` means every comparable cell agreed.
- **A raise** (`HB-USR-002`, reason text) when the grading pass or its scores ledger is absent or unparseable, or a property cell whose `property_check_pass` row has a value has no readable `property.json`.
- **Not comparable** (either side NA): left out of the list and counted in the log event. **In the discriminate path a not-comparable cell is an HB-RDY-011 item** (TA 14; every task, check-less included: erratum, Coordinator #47, CR47-1): in a trial every cell must be gradable, and a silent agreement is the thing refused. (The pilot's reader keeps R-96's count semantics.)
- It reads, never writes, and calls no grader.

`discriminate` calls it on its own pass; X-C's pilot command calls it for `gates.pilot` and X-H2 renders the grid-run line from it (W0 §7). T-E15 (states, reasons, a real graded fixture) and T-E16 (the discriminate call).

### 8.4 `unbiased_failures` and HB-CHK counts (O3)

In the **discrimination** path nothing is dropped: after the pass, `discriminate` examines every role's cell and records an HB-RDY-011 item for any of: a `property_check_pass` row NA with a reason beginning `invalid (check tampered)` (HB-CHK-002), `check exceeded its bound` (HB-CHK-003), `host suspended` (HB-CHK-004), `check output invalid` (HB-CHK-001); a span with `unbiased_ok: false`; a reader raise; a not-comparable cell; or a record that appeared mid-trial. **Any HB-RDY-011 item means no record is written** (4.4), so a clean retry succeeds. An NA that equals a declared `expected: {na: reason}` for that role is the only exemption (EV-11). The counts of HB-CHK-001..004 rows per role go to the log event and, when a link is written, the link.

### 8.5 What `bench validate` prints

`x HB-RDY-003 S1: exploit_probes_blocked: reference expected 1.0000, observed 0.8000` (one line per Failure; `cli.py:76-82`). The `reconciled:` line and skipped temps are non-failing lines beginning `note:`.

## 9. The discrimination sweeper and lock (O6)

- **Lock.** `discriminate.run` takes `oslock.RunLock.acquire(runs/.discriminate-<task>.lock, code="HB-RUN-005")` **before planning** (`oslock.py:52-58`, Verified). Held means another trial of this task is running.
- **Sweep.** With the lock held, before a write, `atomic.sweep_temps(record_path, lock)` (S-B4 item 2) deletes every `<record name>.tmp-*` sibling. Under the lock no live writer exists, so no age gate. **W0 rev 4: `bench campaign verify` is lock-free and sweeps nothing, and X-C never deletes in `bench/discrimination`** (SEC 9: the rev-1 sentence about an age-gated X-C sweep is deleted).
- **Readers.** `record_failures` and `problems` list the folder with `atomic.is_temp_name`, skip those names, and **name each skipped temp in a `note:` line**. They never delete.
- A crash between the temp write and the link leaves a temp and no record; the next run sweeps and writes (T-E17).

## 10. Patterns and the Solution-Selection Ladder

| Problem | Pattern | Rung | Rejected |
| --- | --- | --- | --- |
| Run a "harness" that is not a model | **Strategy** behind the existing port (`Launcher`); the agent is a Test Double of the real boundary (an ACP process) | reuse-in-codebase | an `engine.py` edit; an in-process fake driver (ORCL-A) |
| A record that cannot be written twice differently | **Idempotent Receiver** (content-addressed, equal bytes = no-op) over `create_once` | reuse (W0 §4) | a compare branch with ids in the body (R-98 deleted it) |
| Pass/fail items with codes | a flat list of **Specification** predicates returning `Failure` (a Notification) | one line each | a rule engine; a class per item |
| Task-declared variants | **Data, not code**: a literal table read by `ast.literal_eval` | stdlib | importing `variants.py` |
| One narrowing, three readers | import `runner.applicable` and `property.at_scale` | reuse (W0 §2) | a copy of either |
| One manifest-from-a-task, one path rule, one env rule | import `identity.for_task`; one `safe_relpath`/`overlay_files`; the grader's `grading_env` allowlist | reuse | three copies of a refusal list; a re-implemented denylist |

Simplifier cuts accepted: no profile file; no `Readiness` class hierarchy; no `FROZEN` registry (E4); no `check_build` re-hash; no async cells; multi-turn and loopback not built. `simplify:` ceiling of the slice: one task per `bench discriminate` call; upgrade trigger: the E4 ten-task sweep wanting `--all`, a CLI loop.

## 11. Telemetry (instrumentation over inference)

Questions an operator asks, each with a named emitting source. **Sources:** the structured log events (all outcomes, always) and `discrimination-link.json` (only for a trial that created or confirmed a record, R-98). Events through `engine.configure_logging` (same trace id): `discriminate.started`, `discriminate.finished` (with `outcome` and `error_code`), `readiness.validated`. **Constraint (Verified, `engine.py:LOG_EXTRAS`):** extras are `detail`, `pids`, `fact`, `win32_error` only, so numbers go in `detail` as a short `k=v` string.

| Question | Source and field |
| --- | --- |
| How long, and where? | event `detail`: `plan_ms engine_ms grade_ms compare_ms write_ms cells=n`; link: the same plus per role `cell_ms` |
| How much? | link: `overlay: {files, bytes}` per role; `variants: n` |
| How often does it fail, and how? | event `outcome` (`written`, `confirmed`, `failed-engine`, `failed-grading`, `untrustworthy`, `determinism-defect`) and `error_code` |
| Is the host trustworthy? | event: `chk_rows` per role HB-CHK-001..004 counts, `unbiased_failures=n`, `not_comparable=n`, `start_ms_max` (from `hosts.jsonl`) |
| Was the record reconciled? | `readiness.validated` event: `reconciled=yes\|no`, and the `note:` line on stdout |

Every field degrades to `null` ("not recorded"), never 0. No RFC 9457 surface (CLI only). Error codes: HB-RDY-001..008, 010, 011 (009 in E4), HB-RUN-005 (reused), HB-USR-002, HB-PLN-004; HB-LED-007 is kept and unreachable from `discriminate` by construction (4.3).

## 12. Surface list (E7): store to compute reader

| Surface | Change | Owner |
| --- | --- | --- |
| store | `bench/discrimination/<task>/*.json`; `runs/<run>/discrimination-link.json`; `runs/.discriminate-<task>.lock` | X-E |
| model | `Failure`; `SyntheticLauncher`; `safe_relpath`/`overlay_files`; record dict shape and `at_scale` normalisation | X-E |
| service | `discriminate.run`, `readiness.{contract_failures, record_failures, problems, hidden_test_disagreements, unbiased_failures}`, `synthetic_agent.py` | X-E |
| projection/wire | `bench-discrimination/1`; `bench-discrimination-link/1`; `plan.kind == "discrimination"`; `plan.SYNTHETIC_PROFILE_RECORD`; `config.CHECK_PROPERTIES` | X-E; X-A1 |
| CLI | `bench discriminate <task> [--runs --cells-root --root]` and the `cmd_validate` line `readiness.problems(root, baseline=...)` | X-C (`cli.py` hub) by SR-E2 |
| identity | `discriminate`, `readiness`, `synthetic_agent` are **grade** (W0 §9); `for_task`, `manifest(..., builds=None)` | X-D |
| errors | HB-RDY-001..008, 010 confirmed; 011 added; 009 to E4 | X-D (`errors.py`) |
| refusals | `plan.kind != "measurement"` refused by the readers of 5.4 | X-C, X-A1 (SR-E3 1) |
| docs | ADR-0016 amendment note and W0 rev 6 (R-98) | Coordinator |
| UI / report | R-93 line renders from `hidden_test_disagreements` (X-H2); the pilot reads both readers (X-C, X-H1). **No UI in this slice** | X-H2, X-C |
| compute readers | `readiness` (record), `bench campaign verify` (name = key), `gates.pilot`, `report/campaign_section.py` | named above |

## 13. Sweeps checked against the tree (testability floor item 5)

| Claim | Scan run | Output | Asserted by |
| --- | --- | --- | --- |
| "No `bench/profiles/synthetic.yaml`: it would break the profile-set test" | `sed -n 125p tests/test_profiles.py`; `grep -n "HARNESSES ==" tests/test_acp_record.py` | four sets equal; a tuple of three | join check J1 |
| "10 property tasks exist as stubs" | `grep -l "^property:" tasks/*/task.yaml \| wc -l` | 10 | T-E24 reads the BOM at test time (count-free) |
| "no property task carries a frozen hash in E1" | `grep -l statement_hash tasks/*/task.yaml` | G1, G2, `_template` (0 property tasks) | none: nothing is built (b8 deferred to E4) |
| "`bench/discrimination/` does not exist yet" | `ls bench/discrimination` | not found | T-E7: readiness handles an absent folder |
| "no `os.environ` read and no denylist in the synthetic launcher" | `grep -n "os.environ" src/harness_bench/discriminate.py` once written | 0 | T-E1a (a canary set in the operator environment is absent from the agent's keys) |
| "`readiness.py` drops no `builds/*` key itself" | `grep -n "builds/" src/harness_bench/readiness.py` once written | 0 | T-E7 (grep assertion) |
| Run-enumerating readers a discrimination run could reach | `grep -rn "plan.json\|load_confirmed" src/harness_bench` outside `plan.py` | `cli.py:155`, `grade/runner.py:197`, `status.py:105`, `views.py:537`, `report/pack_improvement.py` (docstring), `gateway/backend.py:286` (comment) | T-E19 drives each reader named in 5.4 |

## 14. Test plan (testability floor, section 2a of the Wave 1 README)

### 14.1 Skeleton commit first

X-E's first commit lands the three modules with the signatures of 5.1, 6 and 8.1 and **well-formed wrong behaviour**, so no red test is an `ImportError`, `AttributeError` or `NameError`: `problems` and `record_failures` return `[]`; the readers return `[]`; `discriminate.run` plans and runs nothing and returns a result with `outcome: "skeleton"` and writes no file; `safe_relpath` and `overlay_files` accept everything; `synthetic_agent.py` completes the ACP handshake and ends the turn **without copying**. It also lands the fixtures of 14.4 and X-D's HB-RDY rows. Every "today" column is an assertion on that behaviour. Tests are pytest: `tests/test_discriminate.py`, `tests/test_readiness.py`, `tests/test_synthetic_agent.py`.

### 14.2 Rings (tests earn their place)

`push`: pure file/record tests (T-E3, T-E4, T-E7, T-E18, T-E24), the readers on hand-built records, the agent's handshake. `readiness` (at X-E's join and at each task's `ready` change): the engine- and host-driven trials (T-E1, T-E2, T-E5, T-E6, T-E10..T-E13, T-E22). One-time proofs are join checks, not tests.

### 14.3 The tests (25)

"Today" is the assertion that fails on the skeleton. "Real wiring" is the test beside any fake that drives the real composition. Folded in rev 2 (SIM 2): rev 1's T-E4, T-E18, T-E21..T-E24, T-E26, T-E27, T-E34, T-E36 became params or assertions of the tests named in 14.5.

| Id | Test (file) | Assertion that fails today, and why | Red fixture | Real wiring beside a fake | Distinguishing mutant |
| --- | --- | --- | --- | --- | --- |
| T-E1a | `test_discriminate_end_to_end_through_the_real_engine_and_correctness_grader` (retired when T-E1b is green) | `record_path.exists()` is False: the skeleton writes no record. Also asserted on this trial: the record and link hold no absolute path, `USERNAME` or `BENCHCANARY-`; the agent's environment keys exclude `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GH_TOKEN`, `HB_CLAUDE_OAUTH_TOKEN` **and an unlisted canary name** `HB_TEST_UNLISTED_SECRET` set before the run (the dump hook is test-only: an env var read by a test-only agent subclass, not a production branch) | `tests/fixtures/property_tasks/disc_c/` (pytest hidden test passing on the reference, failing on the naive) | **is** the real path: `plan.build_plan`, `engine.Engine`, `SyntheticLauncher`, `runner.run_pass`, `correctness.grade`, `atomic.create_once` | the launcher applies the overlay to a fresh temp dir, not the cell's `ws` (T-E2 also); `os.environ` passed unfiltered: the canary appears |
| T-E1b | `test_a_real_deliverable_through_the_real_probe_host_to_a_record` (**the required end-to-end test**; lands in the commit **after** X-F joins) | same `exists()` assertion; plus `scores.reference.property_check_pass == 1`, `naive == 0`, `probe.reference.hosts_ready == len(cases)` | `disc_p/`: a `callable` security task with a real `check.py` using `bench_check` (2 probes), base, reference and naive overlays | **is** the real path: the real probe host spawned by the real grader, no stub | the host replaced by a stub that returns `blocked` for all cases: the naive would score 1 |
| T-E1c | `test_a_check_less_property_task_discriminates_without_a_host` (TA 1) | `exists()` False; plus the record has **no** `probe` key and `problems()` is `[]` for it | `disc_rw/`: a rework-shaped task with no `oracle/check/`, `graders: [correctness, property]` | the real engine and grader | R-HOST applied to check-less tasks: `problems()` reports a missing probe: red |
| T-E2 | `test_overlay_lands_in_the_engine_built_working_copy_and_deletes_nothing` | the archived `ws/pkg/app.py` equals the **base** content (the skeleton copies nothing); a written-files list equals the overlay's relative paths | base with `pkg/app.py` (A) and an extra `keep.txt`; overlay replacing `pkg/app.py` (B) and adding `pkg/new.py`; a second param whose **base tree holds a symlink/junction** at `a/` and an overlay file `a/b.py` (SEC 3: the agent refuses; the cell is `failed`) | real engine (S-E1 shape) | the agent writes to `cwd.parent` (ORCL-A): the archive keeps A and no `new.py`; the agent also removes files absent from the overlay: `keep.txt` assertion red; the destination `lstat` removed: the link param goes green |
| T-E3 | `test_overlay_and_edit_paths_are_refused_identically_by_readiness_and_agent` (parametrized; **fails rather than skips** where a junction cannot be made: the fixture builds it with `mklink /J` and the test errors if that fails on the Windows runner) | `contract_failures` is `[]` for each: the skeleton accepts everything | one temp solution tree per form: absolute, `..`, `.git/x`, junction, symlink, case-collision pair, `a:b`, `app.py.` (trailing dot), `aux.py`, `nul`, a Unicode-normalisation collision, 2001 files; and the same `..`/absolute forms as `edits[].file` | the **same trees run through the real agent** exit non-zero and the engine records a failed cell; assert readiness and agent verdicts equal (differential) | drop the `..` check: only that param goes green; delete the case-fold check: only the collision param; the agent re-implements the rule instead of calling `safe_relpath`: the differential param for Windows names differs |
| T-E4 | `test_retry_at_an_unchanged_key_is_a_confirmation` | first run: `exists()` False; after X-E, the second `run` returns `outcome == "confirmed"`, bytes identical, no HB-LED-007 | `disc_c` run twice, different run ids | real `create_once` | **M-ID:** put `run_id` back in the body: bytes differ, `create_once` raises HB-LED-007: red |
| T-E5 | `test_a_real_difference_at_one_key_is_hb_rdy_010_names_the_path_and_leaves_the_file` (a) and `test_no_link_after_hb_rdy_010` (b, R-98 condition 1) | (a) no exception today, file absent; after X-E the second run raises HB-RDY-010 naming the first differing **path**, stored and new value, and `sha256(file)` is unchanged. (b) the failed run folder holds **no** `discrimination-link.json` | `disc_flaky/`: an overlay whose output depends on a counter kept outside the working copy; a second param where only a `probe.reference.cases.<id>` outcome differs (PAT 9) | real engine and `create_once` | (a) `create_once` with overwrite, or HB-LED-007 for HB-RDY-010: code or hash red. (b) write the link before the compare: the file exists: red |
| T-E6 | `test_reconciliation_reasons_and_never_a_pass` (parametrized, one per closed reason of 4.3, plus the `yes` and the score-difference cases) | no `reconciled:` line today | a real trial; then per param: link removed; `runs/` removed; grading pass removed; record bytes changed (hash mismatch); `plan.json` kind set to `measurement`; task version changed; combos changed; a re-grade under a changed grader fixture (HB-RDY-004) | real run folder | print `reconciled: yes` when no link: the `no link` param is red; trust the link without hashing the record: the hash param is red |
| T-E7 | `test_each_record_item_fails_with_its_code` (a..h) | `record_failures` is `[]` for every defect | hand-built record per defect: (a) none, and a stale one for another version; (b) identity differs; **(b2) a campaign baseline holding two tasks and `builds`, the record valid for task one**: must pass; (c) reference primary 0; (d) reference secondary differs; (e) naive primary 1; (f) a win32 body renamed for another platform or prefix (SEC 7); (g) a declared variant absent | T-E1b produces a record that `record_failures` accepts (the wiring partner for hand-built records) | `==` to `>=` in the score comparison: (c)/(d) pass, red; compare `task_version[:16]`: a record with equal prefix passes; (b2) compare the full baseline hash instead of `for_task`: red; a hand-rolled `builds/*` drop in `readiness.py` (a grep assertion that there is none) |
| T-E8 | `test_ready_without_a_real_host_record_is_refused` (a..d) | `problems()` is `[]` for each | (a) no record; (b) correct scores, **no `probe`**; (c) `probe.hosts_ready` 0; (d) a check-less task carrying a `probe` | T-E9 and T-E1b | drop the `probe` check: (b), (c) green. Pair (R-HOST vs HB-RDY-003): (b) has equal scores, so only R-HOST can fail it |
| T-E9 | join test (X-C's lines, owner X-C, joins at X-INT): (a) `cli.main(["validate"])` for `disc_p` marked `ready` with no record; (b) the same with a campaign baseline; (c) `cli.main(["discriminate", "DISC-C", ...])` | (a) returns OK today; (b) the baseline is not passed through; (c) the subcommand does not exist/dispatch | a temp repo | **is** the real `cli.main` | delete the `readiness.problems` line, the baseline keyword, or the `discriminate` dispatch line: the matching part goes red |
| T-E10 | `test_scan_a_fixture_fails_naming_metric_expected_observed` | `problems()` is `[]`; no record | `scan_a` and `scan_a_secondary` (8.2) | the real engine, grader and host | check only the primary: green on `scan_a`, but `scan_a_secondary` stays failing only if the secondary rule exists |
| T-E11 | `test_variant_trial_runs_on_the_real_host_compares_flips_and_never_executes_the_file` | `record["variants"]` absent: the skeleton runs no variants; the sentinel assertion is asserted **through `discriminate`** (TA 11): `record["variants"]["m9"]["flips"]` holds the parsed flips and `sentinel.txt` is absent | `disc_p` + `variants.py` with two variants (one flips `p-2`, one `p-1`) whose module body writes `sentinel.txt`; params for the grammar defects (two assignments, non-literal, name regex, `old` with 0 and 2 matches; the `..` `edits[].file` is in T-E3) each HB-RDY-005; a check-less param (`disc_rw` with a `v-laundered`-shaped variant) | real host (as T-E1b) | compare only `hidden_tests_pass`/`deliverable`: fixture `wrong_flip` passes wrongly; `importlib` the file: the sentinel appears |
| T-E12 | `test_a_crash_variant_is_rejected_not_counted_as_a_flip` | no variants run today | a variant that makes every handler raise (every case `exploited`), declaring "flips all" | real host | drop assertions (1) and (2): the crash equals the declared flip set |
| T-E13 | `test_a_check_tampered_trial_writes_no_record_and_a_clean_retry_succeeds` (TA 4) | `readiness_failures` is `[]` and a file is written/none; after X-E: the first trial exits non-zero with an HB-RDY-011 item, **no file at the key**, and a second, clean run **succeeds** (not HB-RDY-010) | a naive overlay that trips the tamper path once (a counter outside the working copy); param for HB-CHK-001/-003/-004 rows (hand-built scores ledger is the push form; the hook form the readiness one) | the discriminate path over a real pass | write the record despite an HB-RDY-011 item: the file exists, the retry is HB-RDY-010: red; count only HB-CHK-002: the sibling param green |
| T-E14 | `test_unbiased_failures_lists_cells_and_raises_with_the_reason_when_unreadable` | returns `[]` for both | `property.json` with one span `unbiased_ok: false`; a run folder with no scores ledger | a real graded fixture run (T-E1b's) | return `[]` on exception: the unreadable case goes green |
| T-E15 | `test_hidden_test_disagreements_states_and_reasons` | returns `[]` for all | (i) `hidden_tests_pass` true and `pass_at_1` 0; (ii) all agree; (iii) `property.json` deleted for a cell with a recorded `property_check_pass` (raises, reason names the cell); (iv) `pass_at_1` NA (not comparable) | the real function over a **real** graded run (X-INT join test `test_section_reads_the_real_readiness_function`, W1-H) | return `[]` on (iii); count (iv) as a disagreement |
| T-E16 | `test_discriminate_fails_the_trial_on_a_disagreement_a_raise_or_a_not_comparable_cell` | no failure item today | `disc_flaky` (tests disagree with the pass); a not-comparable cell | real path | skip the call: red; treat not-comparable as agreement: red |
| T-E17 | `test_a_leaked_temp_is_swept_before_the_write_and_readers_skip_name_and_never_delete` | the temp still exists after `run`; `problems()` prints no `note:` for it | a `x.json.tmp-1-<32 hex>` file and a temp **folder** beside the key, plus a non-temp name `x.tmp-notes` | real `atomic.sweep_temps` and `problems` | glob `*.tmp-*` instead of `is_temp_name`: `x.tmp-notes` deleted; the reader deletes: the temp is gone |
| T-E18 | `test_readiness_recomputes_the_stored_failure_list` | a record with a tampered empty `readiness_failures` and a wrong score passes | hand-built | T-E1b real record | trust the stored list: red |
| T-E19 | `test_a_discrimination_run_is_refused_or_labelled_by_each_reader` (join, owners X-C/X-A1, SR-E3 1) | each reader accepts the run today | a real discrimination run folder; params: `bench run`, `attach`, `pilot attach`, `run_side_check`, report, board (each **refuses** HB-PLN-004 naming the kind); `bench status` (**labels** `kind: discrimination`) | real readers | skip the kind check in one reader: its param red |
| T-E20 | `test_two_discriminate_calls_exactly_one_proceeds` (TA 6, deterministic) | the skeleton takes no lock | the test holds `runs/.discriminate-DISC-C.lock` itself, calls `run`, asserts HB-RUN-005 and **no run folder** | real `oslock` | take the lock after the plan step: a run folder exists: red |
| T-E21 | `test_an_incomplete_engine_run_writes_no_record_and_names_the_cell` | `outcome: "skeleton"`, exit 0 | an overlay whose agent exits non-zero | real engine | write the record anyway: red |
| T-E22 | `test_a_record_that_appears_mid_trial_is_untrustworthy_and_not_written` (TA 5) | the skeleton has no check; no HB-RDY-011 | a `disc_c`-shaped overlay whose deliverable, when it runs, writes a plausible record at the final key path (the cells root is outside the repo; the path is given by a test-only env var); the key was absent at start | real engine, grader and `create_once` | skip the second absence check: the forged file stays and the trial reports `written`: red |
| T-E23 | `test_a_measurement_plan_with_a_synthetic_combo_is_refused_naming_the_combo` | the plan is built today | a matrix with `synthetic-reference` and `kind: measurement` | real `plan.build_plan` (X-A1's refusal) | drop the refusal: red. Asserts **HB-PLN-004** and the combo name (not HB-PLN-002; TA 9) |
| T-E24 | `test_contract_field_defects_each_fail_with_their_code` (parametrized, one defect per param, built by `tests/fixtures/property_tasks/make_task.py`; folds rev 1's T-E22, T-E24, T-E26, T-E27) | `[]` for each | one fixture per defect: every EV-1 field of 8.2; `expected` value with no comment and with a one-word comment (GLD-A); `docker`/`podman` in `toolchain` and in `build` argv; `Authorization` containing `authoriz` (**must not fail**) and a real term at line 3 (006); **a security task with no `oracle/check/` and a rework task with one** (HB-RDY-005); simplicity without `ceilings.outside_radius_lines`; a case id `a:b`, `nul`; a loopback task declaring both shapes; pair rule with one task and with two tasks at one base (and two bases at one repo must pass); plus the real BOM tasks (all `stub`, so `[]`) | real `problems` over `make_task` trees | per param: substring (not whole-word) match fails the `Authorization` control; compare `source.repo` only: the two-bases param passes wrongly |

Fixtures built by `make_task.py` use the **public** `readiness.problems` path (no private import).

### 14.4 Join checks (not tests)

- **J1:** `tests/test_profiles.py` and `tests/test_acp_record.py` unchanged and green on the merged branch (rev 1's T-E29).
- **J2:** S1's real discrimination (`oracle/evidence.md` records it) when X-I's S1 is `ready` (rev 1's T-E30), and the 15-cell wall-time measurement.
- **J3:** the spike S-E1 repeat on Python 3.14.6.

### 14.5 Folded tests (SIM 2): where each rev 1 assertion went

| rev 1 id | now |
| --- | --- |
| T-E4 | T-E2 |
| T-E18 | T-E17 |
| T-E21 | T-E11 |
| T-E22, T-E24, T-E26, T-E27 | T-E24 |
| T-E23 | cut with HB-RDY-009 (E4) |
| T-E34, T-E36 | T-E1a |
| T-E28 | T-E6 |
| T-E29, T-E30 | J1, J2 |
| T-E31..T-E33, T-E35 | T-E20, T-E21, T-E22, T-E23 |

## 15. Join order, dependencies, seam requests, decisions

- **Order.** X-B1 (`create_once`, `is_temp_name`, `sweep_temps`), X-D (`identity` incl. `for_task`, `errors.py` rows) and X-A1 (`kind`, `SYNTHETIC_PROFILE_RECORD`, `CHECK_PROPERTIES`) first; **X-F's `grade/_env.py` (the allowlist) before X-E's skeleton**, because `SyntheticLauncher.argv_env` imports it; then X-E's skeleton and T-E1a..T-E8, T-E10 (engine-only parts), T-E17, T-E18, T-E20..T-E22, T-E24 on the real `correctness` grader; then X-F's host enables T-E1b, T-E10..T-E13; X-C's lines (T-E9) and the T-E19 refusals at X-INT; X-I's S1 (J2) last.
- **Seam requests.**
  - **SR-E1** (`req-01M41H86JNZ3XPT1T1RJZJE35X`): granted in part by W0 rev 5, completed by **R-98** (the body drops the ids). Applied here; the only open item is W0 rev 6's text.
  - **SR-E2** (`req-01M41H86X2ENXFWMWGTHTDDHMN`): granted, all four (W0 rev 5).
  - **SR-E3** (`req-01M41MGD2M334432XZMEHGHQY2`, new): (1) the 5.4 refusals (X-C, X-A1); (2) W1-F: `property.json` gets `check.clauses` beside `check.hosts` and is written for check-less properties with `hidden_tests` and the `clause`; (3) W0 §11: HB-RDY-009 and the registry land with X-LG in E4; (4) W0 rev 6: the record text per R-98 and "readers raise, callers convert". **Fallback while unanswered:** design to this text; 5.5, the check-less compare of 7 and T-E19 are **provisional (seam SR-E3)**.
- **Decisions made here (reversible by editing X-E's modules):** D-E1 variants are cells of the same run; D-E2 `parallelism: 1`; D-E3 a trial with an HB-RDY-011 item or an incomplete run writes nothing, one that disagrees with `expected` writes a failing record (rev 2: was "writes an HB-RDY-011 record"); D-E4 in a trial a not-comparable cell is an HB-RDY-011 item; D-E5 the synthetic environment is the grader's allowlist.
- **Open measurement (not modelled):** the wall time of a 15-cell S1 trial (J2).

## 16. Spikes

| Id | Question | Method | Result |
| --- | --- | --- | --- |
| S-E1 | Can the real engine drive a stdlib ACP agent behind a `Launcher` with no `engine.py` edit, end a turn, and leave the overlay in the archive, with `records()==[]` and `usage_source="acp_turn"`? | A scratch script (not committed; the `FakeLauncher` shape of `tests/test_engine.py:41-77`, a 30-line stdlib agent): two synthetic cells, `engine.Engine(...).run()`, Python 3.12.x | **Confirmed.** `exit_code 0`; both cells `outcome completed, cause None, stop_reason end_turn`; the archive held `attempt-1/ws/pkg/app.py` per cell; no spend row; events included `cell.workspace_built`, `cell.archived`, `run.completed`. Not covered: the grading pass over the archive, 3.14.6 |
| (read) | Does a profile file for `synthetic` break existing tests? | read `tests/test_profiles.py:125`, `tests/test_acp_record.py:249` | Yes (5.3) |
| (read) | Is `status` inside the task version hash? | read `plan.py:113-115` | Yes (4.1) |
| (read, rev 2) | Does `config.HARNESSES` list `synthetic`? Does `plan.build_plan` need a `builds` entry? | read `config.py:34`; `plan.py:282-295` | No (`("claude-code", "codex", "copilot", "grok", "agy")`); yes, HB-PRE-007 without it (5.1) |

## 17. Failure modes, adversarial analysis, privacy

### 17.1 Failure-mode analysis

| Id | Mode | Disposition | Telemetry | Test |
| --- | --- | --- | --- | --- |
| F1 | A legitimate retry at the same key | **prevent**: equal bytes are a no-op (4.3) | `outcome=confirmed` | T-E4 |
| F2 | A flaky task: the same key scores differently | **detect**: HB-RDY-010 naming the path, file untouched, no link | `outcome=determinism-defect` | T-E5 |
| F3 | Crash after the temp write, before the link | **recover**: the next run sweeps and writes (9) | temp named in `note:` | T-E17 |
| F4 | Two `bench discriminate` for one task at once | **prevent**: per-task `RunLock` before planning, HB-RUN-005 | `outcome=failed` | T-E20 |
| F5 | A cell fails or times out in the engine | **detect**: no record, non-zero exit naming the cell and cause (4.4) | `failed-engine` | T-E21 |
| F6 | Host suspend during a grading span | **detect**: HB-RDY-011, nothing written, re-run (4.4, 8.4) | `untrustworthy` | T-E13 |
| F7 | A load-driven `timeout` flips a variant wrongly | **mitigate**: serial cells; **detect**: `flips` mismatch names the case and `start_ms`; **accept** residual (a slow host can still miss a bound; RV-DS W0 4) | `start_ms_max` | T-E11 |
| F8 | The task's check is tampered by the deliverable (NA) | **detect and fail closed**: HB-RDY-011, no record (so a clean retry works) | `chk_rows` | T-E13 |
| F9 | The unbiased clock is unreadable | **detect**: `unbiased_ok: false` is HB-RDY-011 | `unbiased_failures` | T-E14 |
| F10 | Hidden tests nondeterministic | **detect**: the disagreement reader fails the trial | `not_comparable` / disagreement count | T-E15, T-E16 |
| F11 | The record is hand-written to look right | **detect**: R-HOST needs the probe digest; reconciliation when a run exists; git is the witness. **Accept** residual: a hand-forged digest on a fresh clone is accepted by readiness; the pilot ring (EV-8/EV-14) re-measures every ready task, so a forged record cannot reach a verdict | `reconciled=` | T-E8, T-E6 |
| F12 | The overlay is applied to a tree the engine did not build | **prevent**: the agent writes only to its cwd = the engine's working copy (6) | | T-E2 |
| F13 | An overlay, an edit path or a base-tree link escapes the working copy | **prevent**: `safe_relpath`, `overlay_files`, the destination `lstat` (6.4) | | T-E2, T-E3 |
| F14 | The run folder is absent on a fresh clone | **mitigate**: the record is self-contained; `reconciled: no (run folder absent)` | note | T-E6 |
| F15 | Disk full while writing | **detect**: `OSError` propagates with the path; no partial file (create-once) | `failed` | covered by W1-B's crash tests |
| F16 | A task file runs code in the operator process (variants) | **prevent**: data-only read (7) | | T-E11 |
| F17 | A stale record after `task.yaml`, a check file, the catalog or the engine changes | **prevent**: the key holds the version and identity; HB-RDY-001/002 | | T-E7 |
| F18 | Platform differs | **mitigate**: the key holds the platform; HB-RDY-001 lists the platforms present | | T-E7 |
| F19 | A deliverable pre-creates the record path | **detect**: absent-at-start then present-before-write is HB-RDY-011 (4.3) | `untrustworthy` | T-E22 |
| F20 | A check-less task is held to a host it cannot have | **prevent**: R-HOST and the case compare are scoped by `CHECK_PROPERTIES` | | T-E1c, T-E8 |

### 17.2 STRIDE-lite

**Trust boundaries.** B1: agent-written content versus the operator's committed records. In a trial there is no agent: the overlay is task-author content (hashed in the task version); the deliverable it forms is still **untrusted at grade time** (W0 §3 probe host, ADR-0018). B2: the operator process reading `oracle/variants.py` and `cases.yaml`. B3: the committed `bench/discrimination` folder versus any later hidden check running agent code in the same user session (ADR-0016 §8 accepted residual). B4: the synthetic agent process (operator rights) versus the oracle tree it reads.

| Id | Threat | Disposition | Negative test |
| --- | --- | --- | --- |
| S1 | Spoofing: a hand-made record claims the real host ran | **mitigate** (R-HOST digest, name-equals-body, reconciliation) and **accept** the fresh-clone residual (F11) | T-E7, T-E8 |
| S2 | Spoofing: a stale or planted link prints "reconciled" | **mitigate**: the link carries the record's sha256; the run's kind, task version and combos are checked; `no (...)` and `yes` never count toward readiness | T-E6 |
| T1 | Tampering: a deliverable edits `bench/discrimination/*` during a trial's check | **transfer, named:** `bench campaign verify` after every grading pass (ADR-0018 §11(b), X-C) and ADR-0018's job/handle rules; **mitigate:** the trial runs in a cells root outside the repo; the key is checked absent at start and again before the write (4.3) | T-E22 |
| T2 | Tampering: `variants.py` as code | **prevent** (7) | T-E11 |
| T3 | Tampering: path traversal or a link in an overlay, an edit or the base tree | **prevent** (6.4) | T-E2, T-E3 |
| R1 | Repudiation: who produced a record | **mitigate:** committed (git author); the link holds the run id and times | |
| I1 | Information disclosure: the record or telemetry leaks a path, user name or canary | **mitigate:** the record holds task ids, hashes, metric values, case ids and outcomes only (the declared clause text, never bytes from `clauses.json`); the link holds repo-relative paths | T-E1a (scan for the temp root, `USERNAME`, `BENCHCANARY-`) |
| I2 | The synthetic agent reads oracle solutions, then they leak into a measured cell | **prevent:** solutions are read only by `synthetic_agent` in discrimination runs; a measured plan with a `synthetic` combo is HB-PLN-004; the readers of 5.4 refuse a discrimination run | T-E23, T-E19 |
| D1 | Denial of service: a variant or overlay that fills the disk or hangs | **mitigate:** overlay caps (6.4), `variants.py` size cap, the engine's per-cell budget, the grader's bounds, `parallelism: 1` | T-E3 |
| E1 | Elevation: the agent process runs with operator rights and reads `HB_SYNTH_OVERLAY` | **accept:** the operator's own script reading the operator's own task files | |
| E2 | Elevation: credential names reach the synthetic process | **prevent:** the environment is the grader's **allowlist** plus two names (5.1); no `os.environ` pass-through, no denylist | T-E1a (including an unlisted canary) |

### 17.3 Privacy (LINDDUN-lite)

The slice touches **no personal data**: task ids, hashes, scores, case ids. Operator identifiers are kept out of the record and the link (I1, T-E1a).

## 18. Residual risk and unknowns

- R1 Wall time of the 15-cell S1 trial is not measured (Inferred minutes).
- R2 The check-less evidence (`property.json` `hidden_tests`, `clause`) and the `check.clauses` pointer are W1-F/W1-L text, not code (SR-E3 2); `identity.for_task` and `manifest(builds=None)` are W0/W1-D text, not code.
- R3 The synthetic agent was spiked on Python 3.12, not 3.14.6 (J3).
- R4 R-HOST cannot stop a careful forgery on a fresh clone (F11); the pilot ring is the second measurement.
- R5 The record key includes the whole grade-side identity, and `readiness.py`, `discriminate.py` and `synthetic_agent.py` are classed grade (W0 §9), so any edit to X-E's own modules makes every committed record stale (HB-RDY-002) and forces a re-trial of every ready task (RV-PAT residual; follows from ADR-0017 §1; not measured, Inferred).
- R6 A mismatch trial (HB-RDY-003) is written; the fix changes the task version. If the mismatch were ever transient, the key would be poisoned until the task changes (4.4 argues it cannot be).

## Review disposition

Four first-round reviews on `549f7bc4`, judged against W0 rev 5 and R-98. Every finding has a row. *Accepted* = applied in this revision.

| # | severity | disposition | where | note |
| --- | --- | --- | --- | --- |
| TA 1 | blocking | accepted | 4.2, 7, 8.2, T-E1c, T-E8, T-E11, F20 | R-HOST and the variant compare scoped by `CHECK_PROPERTIES`; check-less evidence defined (provisional on SR-E3 2); a fixture per class |
| TA 2 | blocking | accepted | 4.1, 8.2 row 002, T-E7 (b2) | `identity.for_task`; two-task baseline test; no hand-rolled drop in `readiness.py` |
| TA 3 | major | accepted | 4.3, 11, T-E4, T-E5(b), T-E6 | fallback deleted; link only after created-or-equal; `reconciled: no (<reason>)` closed set, one test per reason |
| TA 4 | major | accepted | 4.4, 8.4, T-E13 | any HB-RDY-011 item writes nothing; clean retry succeeds |
| TA 5 | major | accepted | 4.3, T-E22, F19 | absent-at-start and again before the write; B3 residual named |
| TA 6 | major | accepted | T-E20 | deterministic: the test holds the lock; lock before planning |
| TA 7 | major | accepted | T-E9 | real `cli.main` for `discriminate`, `validate`, `validate` with a baseline; owner X-C, joins at X-INT |
| TA 8 | major | accepted | 5.4, T-E19, SR-E3 (1) | one behaviour pinned (refuse; `status` labels); owners X-C and X-A1 |
| TA 9 | major | accepted | 5.1, 5.2, T-E23 | HB-PLN-004 and the combo name; `config.HARNESSES` does not list `synthetic` |
| TA 10 | major | accepted | 8.2 EV-1 row, T-E24, T-E11, T-E3 | rev 3-5 rules added; variants grammar and `old` once in T-E11; `edits[].file` traversal in T-E3 |
| TA 11 | minor | accepted | T-E11 | the sentinel is asserted through `discriminate`, with `record["variants"]` parsed |
| TA 12 | minor | accepted | 4.2, 5.5 | pointers: `Score.evidence` is the file, `check.hosts` the `hosts.jsonl` path, `==` not `>=`; `check.clauses` pending (SR-E3 2) |
| TA 13 | minor | accepted | T-E13, T-E1b, T-E3, T-E1a | one fixture pinned; T-E1b lands after X-F; second mutant; junction fails rather than skips; the env-dump hook is test-only |
| TA 14 | minor | accepted | 8.3, 8.4, T-E16 | a not-comparable cell is an HB-RDY-011 item in the discriminate path |
| PAT 1 | major | accepted | 4.3, 10, T-E4 | no fallback, no "Flagged" bullet, no provisional marks resting on SR-E1 1; grain in R-98's words |
| PAT 2 | blocking | accepted | 4.1, 8.2 row 002, T-E7 | as TA 2; `profiles/<h>` over `profiles.HARNESSES` |
| PAT 3 | major | accepted | 7, 8.2 | variant compare has its row and codes: HB-RDY-003 (differs), HB-RDY-001 (absent); scoped by `CHECK_PROPERTIES` |
| PAT 4 | major | accepted, provisional | 5.5, SR-E3 (2) | evidence read through `property.json` pointers only; `check.clauses` asked of W1-F |
| PAT 5 | major | accepted | 6.4, T-E3 | one `safe_relpath`/`overlay_files` in `synthetic_agent.py` for readiness, the agent and `edits[].file`; W1-F's `_copy_tree` stays separate and why |
| PAT 6 | major | accepted, different fix | 5.1, 17.2 E2, T-E1a | no denylist exists to extract: SEC 8 requires the grader's allowlist, so `profiles.py` stays untouched; `argv_env` row fixed |
| PAT 7 | major | accepted | 5.2, 12 | `discriminate` calls `build_plan` directly, not `validate_matrix`; `config.HARNESSES` no longer needed by this slice |
| PAT 8 | major | accepted | 8.1, 8.3, 8.4, T-E14, T-E15 | readers raise `HB-USR-002` with the reason; callers convert (flagged for rev 6) |
| PAT 9 | minor | accepted | 4.3, T-E5 | HB-RDY-010 names the first differing JSON path; a `probe`-only case |
| PAT 10 | major | accepted | 4.3, 11 | link carries `recorded_at`; written after created-or-equal only; the closed reason set |
| PAT 11 | minor | accepted | 5.1 | `discriminate.run` writes `builds["synthetic"]` itself; `tools.check_build` and `tools.LAYOUT` not reached |
| PAT 12 | nit | accepted (SIM 1) | 8.2 b8 | deferred to E4, no registry |
| SEC F1 | major | accepted, provisional | 5.4, T-E19, SR-E3 (1) | readers refuse `kind != measurement` with a named code; `synthetic` stays out of `profiles.HARNESSES`; `validate_matrix` is not called |
| SEC F2 | major | accepted | 5.1 | one rule: the allowlist |
| SEC F3 | major | accepted | 6.4, T-E2 | destination `lstat`; a base-tree link param |
| SEC F4 | minor | accepted | 6.4, T-E3 | `:`, trailing dot/space, device names, Unicode fold; differential test through both callers; there is one implementation, so the differential also guards a re-implementation |
| SEC F5 | major | accepted | 7, T-E11, T-E3 | `edits[].file` through `safe_relpath` before the first read; one assignment, size cap, errors as HB-RDY-005; declared clause text only |
| SEC F6 | minor | accepted | 4.3, T-E6 | record sha256 in the link; kind, task version, combos checked; ordered by the ledger stamp; no-link-after-010 test |
| SEC F7 | minor | accepted | 4.2, 8.2 row 001, T-E7 (f) | body equals name |
| SEC F8 | major | accepted | 5.1, 17.2 E2, T-E1a | grader allowlist plus `HB_SYNTH_OVERLAY` and `TRACEPARENT`; an unlisted canary; the credential canaries in the T-E1a scan |
| SEC F9 | minor | accepted | 9 | the stale X-C sweep sentence deleted |
| SEC F10 | minor | accepted | 5.2, 5.4 | task id matched against `tasks/`; HB-PLN-004; combo-to-overlay is a table |
| SIM 1 | major | accepted | 8.2 b8, 13, SR-E3 (3) | `FROZEN`, HB-RDY-009 and T-E23 (rev 1) deferred to X-LG in E4; W0 §11 note requested |
| SIM 2 | major | accepted | 14.3, 14.5 | 37 ids to 25 tests plus 3 join checks; every folded assertion keeps a mutant |
| SIM 3 | minor | partly accepted | 4.3 | key field `record_stem` makes the match a string compare; the link stays under `runs/<run>/` because R-98 fixes it there; re-open trigger stated |
| SIM 4 | minor | accepted | 5.1 | `check_build` returns the constant dict; no re-hash |

## Gate

**Reviewers (rev 2 awaits re-review; the author never clears a veto):** RV-TA (Test Architect, **hard veto**) and RV-PAT (Patterns Expert) re-review; RV-SEC (PASS WITH CONDITIONS) and RV-SIM (PASS WITH CONDITIONS) conditions are applied above and are theirs to confirm.

```
GATE w1-e-discriminate · Test Architect · BLOCK · 14 findings (rv-ta-w1e-e1e4, 2026-10-03)
GATE w1-e-discriminate · Patterns Expert · BLOCK · 12 findings (rv-pat-w1e-e1e4, 2026-10-03)
GATE w1-e-discriminate · Security & Identity · PASS WITH CONDITIONS · 10 findings (rv-sec-w1e-e1e4, 2026-10-03)
GATE w1-e-discriminate · Simplifier · PASS WITH CONDITIONS · 4 findings (rv-sim-w1e-e1e4, 2026-10-03)
rev 2 pending RV-TA, RV-PAT
```
