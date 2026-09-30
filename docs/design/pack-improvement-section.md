---
id: "design-pack-improvement-section"
title: "Design: the report's closing section, \"Pack on vs pack off — where to improve the pack\""
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 4 · report (follow-on to row 20)"
tags: [benchmark, report, pack-effect, continuous-improvement, statistics, transcripts]
links:
  - { to: design-phase4-report, rel: depends-on }
  - { to: design-phase4-statistics, rel: depends-on }
  - { to: proposal-pack-onoff-analysis, rel: implements }
  - { to: proposal-enterprise-production-portfolio, rel: relates-to }
review-by: "2027-03-31"
summary: >-
  Specifies a report section that is always present and always last: from a run's own facts it computes
  paired pack-on/pack-off deltas, a value-vs-waste class per (task, combo), ceremony and drift indicators read
  from the native records, inconclusive detection, per-intention verdicts and a ranked, deterministic list of
  "where to improve the pack" findings (PK-01..PK-08). Every number names its source file and field; NA always
  carries a reason and small n is always shown. Report-only (no new ledger fact); red-first test plan with
  goldens from grid-1 and grid-1-cc; six slices. Written for an engineer who was not in the analysis session.
---

# Design: "Pack on vs pack off — where to improve the pack"

## 1. Purpose

The benchmark is the pack's continuous-improvement loop. Every report therefore ends with one section that
answers four questions from the run's own data, the same way every time:

1. Did pack-on do better, worse, or no detectably different from pack-off, per task and per harness?
2. Was the extra cost **value** (it bought quality), **waste** (it bought nothing), or **harm** (quality fell)?
3. Where did the pack's own behaviour cause the difference: ceremony, drift, diverted delivery, fixed context?
4. Which intentions could this run judge at all, and which are inconclusive because the tasks cannot show them?

The section is mechanical: no LLM writes any of it. It is the automated form of the analysis in
`docs/proposals/pack-onoff-analysis.html`. Its findings are candidates for the pack's defect register, not
verdicts on the pack.

## 2. Placement and presence

- **Id** `pack-improvement`. **Heading** "Pack on vs pack off — where to improve the pack". **Nav label** "Pack
  improvement".
- **Always the last section** of `report.html`. It comes after `runs` and after `comparison` when that section
  is present. `html.render` appends it after the optional comparison section.
- **Always present.** Every state renders the heading and one state line:

| State | Condition | Renders |
| --- | --- | --- |
| one pack | the run's cells have one `pack` value | "Not applicable: this run has one pack setting." |
| no pairs | both settings exist but no (task, combo, rep) has a valid cell in both arms | "No complete pairs: every pair has an invalid or ungraded arm." plus a count by validity |
| not graded | `view.grading_id is None` | "Not graded yet: the section needs a grading pass." |
| partial | some combos lack one setting | full section; those combos show "needs both settings" |
| full | otherwise | full section (section 7) |

  R-85 item 2: the states are *evaluated* in this order too -- one pack, then not graded, then no
  pairs, then partial, then full. An ungraded run (`view.grading_id is None`) has no cell with a
  recorded `validity`, so "every (task, combo, rep) has no valid cell in both arms" is trivially
  true of it as well; evaluating "not graded" first means such a run reads "Not graded yet", never
  the more generic "No complete pairs".

- The section goes through `model.Section`, so the existing egress scan covers it and it appears in
  `report-record.json` `sections` like the others. No other file changes.

## 3. Grain and inputs

**Pair grain:** one pair is exactly one `(task, combo, rep)` with a pack-on and a pack-off cell that are both
`validity == "valid"`. **Group grain:** one group is one `(task, combo)`; its pairs are its reps. **Task
grain:** one `task` with all combos pooled.

The module reads only what the report already holds (`view`, `board_obj`, `run_dir`, `root`), plus the
archived native records through the existing profile readers. It stores nothing (ADR-0006: derive, don't
store), which is the same pattern as `report/context_growth.py`.

### 3.1 Where every number comes from

| Number | Source file | Field / rule | Reader |
| --- | --- | --- | --- |
| pass per cell | `scores/*.jsonl` | `metric_id == "pass_at_1"`, `value` | `CellView.scores["pass_at_1"]` |
| other quality metrics | `scores/*.jsonl` | `metric_id`, `value`, `reason` | `CellView.scores[...]` |
| validity | engine events + scores | as `views` derives it | `CellView.validity` |
| task, rep | `plan.json` | `cells[].task`, `cells[].rep` | `board._cell_task_rep` (reuse, do not copy) |
| tokens per cell | `model_calls/*.jsonl` (or `turn_usage` for `acp_turn` profiles) | sum of `uncached_input + cache_read + cache_write + output` over models | `CellView.tokens` via `views.sum_tokens` (R-85 c4: the one home for this sum -- `board.py`'s leaderboard and frontier rows, and this section's cost math, all call it; it no longer lives inlined at two board call sites) |
| wall per cell | `events/*.jsonl` | lifecycle-derived | `CellView.wall_ms` |
| model calls per cell | `model_calls/*.jsonl` | row count | `CellView.calls_per_cell` |
| tool calls per cell | `tool_calls/*.jsonl` | rows with `cell_id`, current `extraction_id` | `views.rows(run_dir, "tool_calls")` filtered as `views._cell_view` does |
| first-call input | `model_calls/*.jsonl` | the row with the earliest `start` where `principal == cell_id` and `model` is not in the plan profile's `auxiliary_models`; `uncached_input + cache_read + cache_write` | `views.rows(run_dir, "model_calls")`; NA reasons `SESSION_TOTALS` (Copilot) and `ACP_MISSES_CALLS` (`acp_turn`), reused from `grade/cost.py` |
| stop reason | `events/*.jsonl` | `cell.outcome.stop_reason` | events filtered by `cell_id` |
| pass interval per combo | board | `board_obj.pack_effect.rows` where `measure == "pass_at_1"` | reuse, never recompute (DM7) |
| scope creep files | `grading/<gid>/<cid>/drift/drift.log` | tab-separated `change, path, inside/outside, +a -d` | the path is `CellView.evidence["scope_creep"]` |
| regressions | `scores/*.jsonl` | `regression_count` | `CellView.scores` |
| tool inputs (paths, command) | native record under `archive/<cid>/attempt-<n>/home` | see section 4.3 | new `telemetry.<harness>.tool_inputs(path)` |
| first assistant text | native record | first assistant text block of the main session | new `telemetry.<harness>.tool_inputs(path)` result field |
| sibling worktrees | `archive/<cid>/attempt-<n>/` | directories other than `home`, `ws` whose `.git` is a file starting `gitdir:` and naming `/ws/.git/worktrees/` | directory listing plus a 200-byte read |
| blast radius, test globs | `tasks/<task>/task.yaml` | `blast_radius` | `yaml.safe_load`; NA "task.yaml not found" |

## 4. Computations

All arithmetic is `Decimal` under the stats module's context. Ratios round half-even to 2 places for display.

### 4.1 Paired quality

- Per group: `passes_on`, `passes_off`, `n_pairs`. Display "k/n".
- Per task (combos pooled): the same counts, plus a **two-sided Fisher exact p** on the 2×2 table
  `[[passes_on, fails_on], [passes_off, fails_off]]`.
- **Holm adjustment** across the run's tasks (m = number of tasks with ≥ 1 pair).
- Pooled over all tasks: counts and Fisher p (not adjusted; labelled "pooled").
- **One population** (R-85 item 3): the per-task Fisher table, the Holm family and the pooled test all
  exclude `stats.CONTAMINATION_PRONE` exactly as the board's own pack-effect does; the Method line
  (section 7) prints the board's `exclusion_line` so the same excluded-task set is named once.
- Per combo: the board's existing bootstrap interval for `pass_at_1` (`board_obj.pack_effect`), shown with
  `stats.no_detectable_effect`.
- Other quality metrics: for each metric in the intention map (section 5) that has ≥ 1 recorded value in both
  arms of a task, the per-task means "on / off [n_on, n_off]". No test is run on these (n is too small, and the
  board already provides intervals for areas).

New pure functions in `stats.py`: `fisher_exact_two_sided(a, b, c, d) -> Decimal` and
`holm(ps: Mapping[str, Decimal]) -> dict[str, Decimal]`.

### 4.2 Cost

- `tokens_ratio(pair) = tokens_on / tokens_off`. NA when either side is NA or `tokens_off == 0`, with the reason
  from the side that is NA.
- Per group and per task: **median** pair ratio, and "k of n pairs > 1". The same for wall (`wall_ms`), model
  calls and tool calls.
- Per harness: `Σtokens_on / Σtokens_off` over pairs where both are recorded.
- `tokens_per_pass(arm) = Σtokens / passes` over complete pairs. NA "no passing cell" when passes = 0.
- `tokens_per_extra_pass(group) = (Σtokens_on − Σtokens_off) / (passes_on − passes_off)` only when
  `passes_on > passes_off`; otherwise NA "no extra pass".
- **Fixed context** per harness: the median first-call input for on and off, and the delta. **Modeled share**
  (always labelled Inferred) = `delta × Σcalls_on / (Σtokens_on − Σtokens_off)`, capped at 1.00 -- **NA
  "no extra tokens"** (R-85 item 1), never capped to a number, when `Σtokens_on − Σtokens_off <= 0`.

### 4.3 Ceremony indicators (pack-on and pack-off both computed; off is the baseline)

A new function per harness reader, `tool_inputs(path: Path) -> ProcessTrace`, reads the same record the
extractor reads:

```text
ProcessTrace(first_assistant_text: str | None,
             calls: tuple[ToolInput, ...])      # main session, then each sub-agent record, in native order
ToolInput(native_ordinal: int, name: str, paths: tuple[str, ...], command: str | None, is_write: bool)
```

- Claude Code: from each `tool_use` block. `paths` comes from `input.file_path`, `input.path`, `input.notebook_path`.
  `command` comes from `input.command`. `is_write` is true for `Write`, `Edit`, `MultiEdit`, `NotebookEdit`.
- Codex: from `function_call` and `custom_tool_call` payloads. `paths` comes from JSON `path`/`file_path` fields
  and from `*** Add File: ` / `*** Update File: ` headers inside an `apply_patch` body. `command` comes from
  `cmd`/`command`. `is_write` is true for an apply_patch with an Add or Update header.
- Copilot: from `assistant.message.toolRequests[].arguments`, with the same field names. `is_write` is true for
  `create`, `edit`, `str_replace_editor` and `apply_patch`.
- Paths are normalised to forward slashes and made relative to the cell's `ws` when they are under it. A path
  outside `ws` keeps only its last three segments. The trace never leaves the module (section 8).

Classification (pure, `pack_improvement.classify(call) -> set[str]`). The constants are named and versioned in
the module (`PACK_RULES_VERSION = "1"`):

| Class | Rule |
| --- | --- |
| `pack_read` | not `is_write`, and a path or the command contains a `PACK_PATHS` entry: `.claude/knowledge/`, `.claude/skills/`, `.claude/agents/`, `.github/instructions/`, `.github/knowledge/`, `.github/agents/`, `.github/prompts/`, `.agents/skills/`, `.grok/`, `docs/ai-forward-pack/`, `AGENTS.md` |
| `skill_load` | `name` in `{"Skill", "skill"}` |
| `pack_script` | command contains one of `audit-log.py`, `prompt-log.py`, `docs-graph.py`, `coord-core.py`, `pack-doctor.py` |
| `worktree_create` | command matches `\bgit\s+worktree\s+add\b` or `\bworktree\s+new\b`, or `name == "EnterWorktree"` |
| `git_identity` | command matches `\bgit\s+config\s+(--global\s+)?user\.(name|email)\b` |
| `test_write` | `is_write` and a path matches `TEST_PATH = (^|/)tests?/|Tests?\.cs$|(^|/)test_[^/]*\.py$|_test\.py$` |
| `product_write` | `is_write`, not `test_write`, and a path matches the task's `blast_radius`. **NA, never a guessed match, when `blast_radius` could not be read** (R-85 item 1: `task.yaml` unreadable or has no `blast_radius`) -- reason `NA_BLAST_RADIUS = "blast radius not readable"`. |

Per cell:

- `ceremony_calls` = calls in any of `pack_read`, `skill_load`, `pack_script`, `worktree_create`.
- `ceremony_share` = `ceremony_calls / len(calls)`. NA "no tool calls" when 0.
- `goal_state_present` = `first_assistant_text` matches `\bGoal\b\s*[:*]` and `Done when` (case-insensitive).
- `test_first` = the first `test_write` ordinal < the first `product_write` ordinal, or a `test_write` exists and
  no `product_write` does. NA `NA_BLAST_RADIUS` when `product_write` is itself NA (R-85 item 1's cascade --
  never "zero product writes"); NA "task has no test path in its blast radius" when the blast radius is
  readable but names no test-shaped path at all.
- `git_identity_set` = any `git_identity` call.

### 4.4 Drift indicators

- `pack_files_written` = drift.log lines with `outside` whose path starts with one of `PACK_WRITE_PATHS`:
  `docs/audit/`, `docs/docs-index.js`, `.agents/`, `docs/coordination/`, `docs/lessons/`. Count files and lines
  (`+a` + `-d`). NA when the task has no drift grader (the evidence key is absent). The reason is "no drift
  grader for this task". Implemented (S5 hand-off): the line format is pinned against `grade/drift.py`'s own
  writer (`_measure()`), not guessed -- `tests/fixtures/pack_improvement/drift-pack-files.log`, confirmed
  byte-for-byte against a real `runs/grid-1` drift.log.
- `worktree_left` = the attempt directory has ≥ 1 sibling worktree (section 3.1 rule).
- `diverted_delivery` = `worktree_left` and some file under the task's `blast_radius` exists in a sibling
  worktree and is missing from `ws` or differs from it byte for byte. Compare file bytes only; never run git.
  **NA `NA_BLAST_RADIUS`** when the blast radius could not be read (R-85 item 1) -- never a guessed False.
  Matching a `blast_radius` glob (`src/**`, a bare file name) against a sibling's files uses `fnmatch` on each
  file's path relative to the sibling, the same matcher `product_write` uses for the identical syntax (one
  definition, not two) -- found necessary against the real `grid-1-cc` archive (S5 hand-off): `Path.glob(pattern)`
  per pattern silently misses every leaf file under a `**` segment (pathlib's `**` matches directories at each
  depth, never the files inside them, without a trailing `/*`).
- `diverted_and_failed` = `diverted_delivery` and `pass_at_1 == 0`. NA when `diverted_delivery` is NA (same reason).
- `stopped_without_product` = pack-on cell, `outcome == "completed"`, `stop_reason == "end_turn"`,
  `pass_at_1 == 0`, and zero `product_write` calls in the trace (sub-agents included). **NA `NA_BLAST_RADIUS`**
  when the blast radius could not be read (R-85 item 1's cascade, since firing needs `product_write`) -- not
  only "when the trace is NA".

### 4.5 Value vs waste (per group)

Evaluate the rules in this order; the first match wins:

| Class | Rule |
| --- | --- |
| `inconclusive` | `n_pairs < 2`, or the token ratio is NA in every pair |
| `harm` | `passes_on < passes_off` and (the task's Holm p < 0.05, or ≥ 1 on-cell in the group is `diverted_and_failed` or `stopped_without_product`) |
| `value` | `passes_on > passes_off` and the task's Holm p < 0.05, or a mapped quality metric's board interval has `lo > 0` for this combo |
| `waste` | median token ratio ≥ `WASTE_RATIO = 1.25` |
| `neutral` | otherwise |

A group whose off arm passes every pair (`passes_off == n_pairs`) and has no other recorded quality metric is
flagged **`ceiling_off`** (R-85: renamed from this section's original "saturated" -- `saturated` is reserved for
section 4.6's task-level reason below, a different condition on *both* arms). Its `waste` renders as
"waste (ceiling_off: no gain was possible)".

### 4.6 Inconclusive detection (per task)

A task is **inconclusive** with every reason that applies. R-85: `saturated` and `floor` are **exact equality**,
not a percentage band -- below 20 pairs per arm a 95%/5% threshold cannot differ from "every"/"none", so it is a
knob with no measurement behind it. `saturated` and `ceiling_off` (4.5) are two different names for two
different conditions; do not conflate them.

- `saturated`: `passes_on == n_pairs` **and** `passes_off == n_pairs` (both arms passed every pair).
- `floor`: `passes_on == 0` **and** `passes_off == 0` (both arms passed no pair).
- `same failure both arms`: every failing cell in both arms has the same failing hidden-test name set. This
  reads the correctness evidence (`oracle.log` failing test names). When it cannot be read, this reason is
  skipped, never guessed.
- `judge not recorded`: every judge-sourced metric the task's graders name is NA.
- `few pairs`: `n_pairs < 3`.
- `no mapped metric`: for an intention, no metric in its map (section 5) is recorded for this task.

## 5. Per-intention verdicts

The intention map is a module constant. A metric in the map that is absent from the catalog is skipped, so
metrics the portfolio proposal adds later join without a code change.

| Intention | Mapped metrics (quality) | Indicators (behaviour) |
| --- | --- | --- |
| Rigor | `honest_completion_claims`, `assumption_disclosure`, `verification_before_done`, gated composite | `goal_state_present` |
| Secure / compliant / private / resilient | `error_handling`, `exploit_probes_blocked`, `pii_canary_leaks`, `audit_event_coverage`, `fault_suite_pass`, `secrets_in_diff`, `licence_violations` | `git_identity_set` (negative) |
| TDD, minimise false positives | `mutation_score`, `verification_before_done` | `test_first` |
| Spike, fewer hallucinations | `hallucinated_symbol_errors`, `verified_before_use` | — |
| No excessive ceremony | — | `ceremony_share`, token ratio on `ceiling_off` tasks |
| No drift or rat-holes | `scope_creep`, `unrequested_behaviour`, `goal_drift_slope` | `diverted_and_failed`, `pack_files_written`, `stopped_without_product` |
| Extra cost is value | — | value/waste/harm group counts |
| Right first time | `rework_ratio`, `regression_count` | — |
| Simplify | `size_vs_reference`, `static_analysis_delta`, `maintainability` | — |

R-85 item 5: `test_quality` is dropped from the TDD row. R-68 item 3 already retired it as a scored metric --
its mechanical rung is `mutation_score`, which the row already carries. The dangling catalog entry
(`metrics.yaml:59`) is a separate finding for the catalog join, not this slice.

Verdict rules, applied **per intention** (R-85 item 7: only the mapped metrics and indicators in that
intention's own row can fire or decide its verdict -- a harm-type indicator that belongs to a different
intention's row never fires this one's miss), in this order:

1. **miss**: any mapped metric's board interval has `hi < 0` in the good direction, or any harm-type indicator
   fires. The harm-type indicators are `diverted_and_failed > 0`, `stopped_without_product > 0`,
   `git_identity_set` on > 0 on-cells and 0 off-cells, and, for ceremony, `ceremony_share_on ≥ 0.20` together
   with ≥ 1 `waste` group on a `ceiling_off` task. For "cost is value": `waste + harm > value` groups.
2. **hit**: a mapped metric's interval has `lo > 0` in the good direction and no miss rule fired.
3. **process only**: no mapped metric decides, but the behaviour indicator differs: on-share ≥ 0.8 and
   off-share ≤ 0.2 for `goal_state_present` or `test_first` (both thresholds required -- PI-T11).
4. **inconclusive (reason)**: otherwise. The reason is the first that applies: "not recorded: <metric ids>",
   "no task exercises it", "ceiling_off tasks", or "few pairs".

## 6. "Where to improve the pack": findings

Each rule emits at most one finding. Each finding carries: code, title, count, up to 5 evidence cell ids (then
"and N more"), a waste measure (failed pairs, or extra tokens), the pack area to look at, and a confidence label.

| Code | Fires when | Waste measure | Pack area | Confidence |
| --- | --- | --- | --- | --- |
| PK-01 Diverted delivery | ≥ 1 `diverted_and_failed` on-cell | failed pairs | session-worktree discipline (WT1) | Verified |
| PK-02 Turn ended before product | ≥ 1 `stopped_without_product` on-cell | failed pairs | turn close (CT), coordination preconditions | Verified |
| PK-03 Pack files in the product tree | on-cells with `pack_files_written > 0` exceed off-cells; escalated when such a cell has `regression_count > 0` and its pair's off-cell has 0 | files and lines | audit & change log mandate | Verified |
| PK-04 Fixed context overhead | per harness, first-call delta ≥ 5,000 tokens or ≥ 25% of off | delta × calls (modeled) | always-loaded files (AGENTS.md, `applyTo: "**"`) | Verified delta, Inferred share |
| PK-05 Ceremony on `ceiling_off` tasks | a `ceiling_off` task (4.5) with `ceremony_share_on ≥ 0.20` and median token ratio ≥ 1.5 | Σ(tokens_on − tokens_off) on those tasks | tiering (T0 means no pack reads) | Verified |
| PK-06 Quality harm without a named cause | a `harm` group with no PK-01/PK-02 cell | failed pairs | investigate (transcripts) | Verified count |
| PK-07 Git identity set | `git_identity_set` in on-cells > off-cells | cells | commit discipline | Verified |
| PK-08 Fewer clarifying questions | scenario-1 tasks, ≥ 3 pairs, mean `ask_vs_assume` on < off | pairs | no-guessing: when to ask | Inferred (watch) |

**PK-08 is never ranked** (R-85 item 6): its measure is not waste, and F-10 (the hand analysis) records that
the clarify matcher recognised no question in grid-1. `pack_improvement.rank_findings` never receives a PK-08
`Finding` at all -- it renders as one watch line under the Inconclusive section (section 7.5), with its means
and n, not as a row of the ranked "where to improve the pack" table. "Where to improve" holds Verified waste
and harm only.

**Ranking** is deterministic: by failed pairs attributed (descending), then extra tokens (descending), then code
(ascending). A finding with count 0 is not rendered. When no rule fires, the section says "No pack-attributable
waste or harm was detected in this run", followed by the inconclusive list.

## 7. Rendering (full state)

In order, built with `html_builder.el` (no `trusted()`), reusing the report's tokens and combo index `c1..c8`:

1. **Headline**: one generated sentence from a fixed template, for example "Pack on used 3.5× the tokens and
   1.9× the wall clock; pass 40/54 vs 48/54 (pooled p = 0.08); 10 of 14 pack-on failures have a
   pack-attributed cause." Every number in it also appears in a table below.
2. **Intention verdicts**: a table with intention, verdict tag, and deciding evidence (metric or indicator, n).
3. **Value vs waste**: a table with one row per (task, combo): pass k/n on·off, median token ratio (k of n > 1),
   wall ratio, class, saturated flag.
4. **Where to improve the pack**: the ranked findings as a table, with evidence cell ids as links to the
   `runs` rows (`#cell-<id>` anchors already exist in the runs section).
5. **Inconclusive**: tasks with reasons.
6. **Method** (small text): sources (section 3.1), `PACK_RULES_VERSION`, thresholds, the pair definition, the
   test used, and "p-values are exploratory at n < 10 per arm".

The page stays readable at phone width: every table sits in the existing horizontally scrolling wrapper.

## 8. Privacy and egress

Only counts, ratios, verdict codes, metric ids, task ids and cell ids leave the module. No transcript text, no
command text, and no paths other than repo-relative pack prefixes are rendered. `first_assistant_text` is used
only to compute a boolean. The section is scanned by the existing egress pass like every section. A test
(PI-T14) asserts that a canary string planted in a fixture transcript never reaches the HTML.

## 9. NA and small n

- NA renders as "NA — <reason>", never as 0 or a blank. It is excluded from every sum, median and share. A
  denominator counts only recorded values, and shows its n.
- Every count shows its denominator ("k/n"). Every median shows "k of n pairs > 1".
- Groups with `n_pairs < 3` get the tag "exploratory (n = k)". Tasks with fewer than 10 pairs get "exploratory"
  beside any p-value. No significance stars.
- Missing archive (`archive_present == False`): section 4.3–4.4 indicators are NA "archive not present". Quality
  and cost still render, and PK-01/02/05/07 do not fire.
- Unreadable native record: that cell's indicators are NA with `record_reason`.

## 10. Decision requests (recommended defaults)

- **DR-PI-1**: transcript indicators computed at report time (report-only, like `context_growth`) or by a new
  weight-0 `pack` grader writing score rows (catalog 0.6)? **Default: report time** for v1. Promote to a grader
  after one grid shows the indicators are stable. That avoids a catalog freeze bump now.
- **DR-PI-2**: thresholds (`WASTE_RATIO = 1.25`, ceremony share 0.20, fixed-context 5,000 tokens / 25%) are
  module constants versioned by `PACK_RULES_VERSION`, each with a one-line basis comment naming the grid-1
  measurement it sits against. **Default: yes.** Changing a threshold bumps the version, which the Method line
  prints. R-85: `saturated` and `floor` (4.6) and `ceiling_off` (4.5) are **not** in this list -- they compare
  `passes_on`/`passes_off` to `n_pairs` by exact equality, not a percentage, so they carry no threshold constant
  to version.
- **DR-PI-3**: `PACK_PATHS` as a constant, or derived from the pack commit's file list. **Default: constant.**
  R-85: the coverage test derives its expected prefixes mechanically from this repo's own
  `docs/ai-forward-pack/INSTALL.md` deployment-map tables (the main table plus the Grok-, Antigravity- and
  Codex-surface tables) and `pack-doctor.py:733-734`'s surface lists -- never from a hand-made fixture manifest,
  so a fixture copy cannot silently keep the test green after `PACK_PATHS` drifts from what the pack actually
  deploys (CI6). `tests/test_pack_improvement.py::test_dr_pi_3_pack_paths_covers_install_md_and_pack_doctor_surfaces`.
- **DR-PI-4**: add the section's data to `board.export` JSON? **Default: no.** It stays report-only, so board
  goldens do not move.

## 11. Red-first test plan

Write each test first and watch it fail for the stated reason. Each test names the failure it alone catches.

| Id | Test | Fails today because / catches |
| --- | --- | --- |
| PI-T1 | the rendered report's last `<section>` has id `pack-improvement` with and without a comparison | section absent; catches a later section appended after it |
| PI-T2 | a one-pack run renders the "one pack setting" state line | catches a crash or an omitted section on one-pack runs |
| PI-T3 | pairs exclude a cell whose other arm is `invalid (...)` | catches pairing on label alone |
| PI-T4 | a cell with `tokens = None` gives ratio NA with its `tokens_reason`, and the median uses the other pairs | catches NA read as 0 |
| PI-T5 | `fisher_exact_two_sided(3, 6, 9, 0)` = 0.0090 (4 dp; exact 0.009049…), `(6, 3, 9, 0)` = 0.2059, `(5, 4, 3, 6)` = 0.6372; `holm` over those three plus three 1.0 values gives 0.0543 for the first (4 dp) | catches a one-sided test or an unadjusted p |
| PI-T6 | each harness's `tool_inputs` on the committed fixture records returns the expected paths, commands and `is_write`, including an apply_patch Add header | catches a reader that misses Codex patch paths |
| PI-T7 | `test_first` uses write-target paths only: a source write whose *content* mentions `tests/` does not count | the analysis session's own detector defect |
| PI-T8 | `diverted_delivery` is true for a fixture with a sibling `.git` gitdir file and a differing blast-radius file; false when the sibling's files equal `ws`; false for a directory without a `.git` file | catches treating `scripted-user.jsonl` or `home` as a worktree |
| PI-T9 | `stopped_without_product` needs `end_turn`, pass 0 and zero product writes; one product write turns it off | catches flagging every failed cell |
| PI-T10 | value/waste/harm/neutral/inconclusive rules on a table of synthetic groups, including rule order | catches rule-order mutations |
| PI-T11 | verdict rules: a miss indicator beats a hit metric; "process only" needs both the on ≥ 0.8 and off ≤ 0.2 thresholds | catches a verdict that hides harm |
| PI-T12 | findings ranking is stable under input shuffles, and a zero-count finding is not rendered | catches nondeterministic order |
| PI-T13 | the Copilot first-call input is NA with `SESSION_TOTALS`; an `acp_turn` profile gives `ACP_MISSES_CALLS` | catches a session total shown as a per-call number |
| PI-T14 | a canary planted in fixture transcript text and in a command is absent from the HTML | catches transcript text leaking into the report |
| PI-T15 (slow ring) | golden on archived runs via `tests/archived_runs.gate_runs_root()` (skipped when absent). **grid-1-cc**: PK-01 evidence = {c4d05c98231eb3aa, 050c08027c79a944, efbedb23da7173d0}; PK-03 escalated by 73c87914995c00a9 (regression_count 3). **grid-1**: PK-01 evidence ⊇ {4a6250261f80ded4, c6a763578ef7e110, 3ff04431d3b5ac27, 757143056c649892}; PK-02 evidence = {b765f438fb811ea0, dfb4ae60b8a3d3a3, 0164cd01031f303f}; Codex first-call delta in 8,000–10,500; Codex token ratio > 5 | catches drift from the hand analysis the section automates |

Mutants to kill (add them to `tests/mutations` in the existing style): swap on/off in the ratio; treat NA as 0;
include invalid cells in pairs; match `ws` itself as a sibling worktree; drop the Holm step; reverse the
ranking; count pack-off ceremony as pack-on.

## 12. Slices for the implementer

1. **S1** `stats.fisher_exact_two_sided`, `stats.holm` (PI-T5).
2. **S2** `telemetry.{claude_code,codex,copilot}.tool_inputs` and `ProcessTrace`/`ToolInput` in
   `telemetry/__init__.py`, with fixture records (PI-T6).
3. **S3** `report/pack_improvement.py`: pairs, cost, fixed context, classification and indicators, as pure
   functions over `view`, rows and traces (PI-T3, T4, T7, T8, T9, T13). **Done.** `pairs`, `tokens_ratio`,
   `median_ratio`, `modeled_share`, `first_call_input`, `classify`, `ceremony_share`, `goal_state_present`,
   `test_first`, `git_identity_set`, `sibling_worktrees`, `worktree_left`, `diverted_delivery`,
   `diverted_and_failed`, `stopped_without_product`. `pack_files_written` (PK-03's reader) is **not**
   implemented -- no committed `drift.log` fixture to verify its column format against; left for whoever wires
   S5, per the standing no-guessing rule rather than guessed now.
4. **S4** rules: value/waste, inconclusive, verdicts, findings and ranking (PI-T10, T11, T12). **Done** as
   reusable pure primitives over already-decided inputs: `ceiling_off`/`saturated`/`floor`, `classify_group`,
   `verdict`, `Finding`/`rank_findings`. `inconclusive_reasons` (4.6's full per-task reason list, combining
   `same failure both arms` and `judge not recorded`) is wired (S5 hand-off): `failing_test_names` reads
   `oracle.log`'s two observed failing-test-name shapes (unittest verbose, xUnit `[FAIL]`) and
   `judge_not_recorded` reads the catalog's `source: [J]` metric ids against the task's own `graders:` list.
5. **S5** rendering in `html.py`: **done**. The section (`_pack_improvement`) is appended last, carries its nav
   entry, and covers the states table (PI-T1, T2, T14; `report.pack_improvement.assemble()` decides the state
   and the renderer switches on it). It wires `pack_files_written` and `inconclusive_reasons` and assembles
   real PK-01..PK-07 `Finding`s from cells/pairs/groups (PK-08 a watch line, never ranked, per R-85 item 6). The
   per-intention verdict table (section 5) is not rendered this slice: `board.py` computes a per-(combo)
   bootstrap interval for `pass_at_1` alone, never a per-metric interval for the other mapped quality metrics,
   and adding one is a `board.py` change this hand-off's scope excluded -- `quality_lo_positive` is always
   `False` (named in `report/pack_improvement.py`'s own module docstring) so no verdict this slice would render
   is fabricated. PK-01..07's Findings do not depend on that gap.
6. **S6** the golden gate-ring test on grid-1 and grid-1-cc (PI-T15; `@pytest.mark.gate`, the marker
   `test_grade_drift.py`'s own archived-run golden already uses, skipping cleanly via
   `archived_runs.gate_runs_root()` when `runs/` is absent), plus the nine mutants (the design's seven and
   R-85's two), all killed. **Done.** See section 14 for a verified deviation from this section's own PI-T15
   text, found while wiring against the real archives.

## 13. Out of scope

The CLI table, the AI summaries, and any change to grading, the catalog or the ledger. Recommending pack text
is also out of scope: the section names a pack *area*, and a human or the pack's own `/dream` loop writes the
change.

## 14. Known differences from the hand analysis

The hand analysis summed `model_calls` directly and used `cell.outcome.turn_ms` for wall time. The section uses
`CellView.tokens` and `CellView.wall_ms`, which match the leaderboard. Exact ratios may differ slightly, so
PI-T15 asserts thresholds and cell-id sets rather than the page's numbers.

**A verified deviation from this section's own PI-T15 text (S5/S6 hand-off, reported to the Leader, not
silently reconciled):** of the four grid-1 cells this section's PI-T15 row names as PK-01 evidence, two
(`3ff04431d3b5ac27`, `757143056c649892`) mechanically satisfy `diverted_and_failed` under section 4.4's own
byte-for-byte rule; the other two (`4a6250261f80ded4`, `c6a763578ef7e110`, both D1 copilot-sol) do not --
their sibling worktree's blast-radius files (297 matched under `src/AiDe.Core/Projections/**` and `tests/**`)
are byte-identical to `ws` (`diff -rq`, checked directly against the real archive). The rule compares final
file bytes only, never git history (section 4.4's own words), so a cell that detoured through a worktree and
then converged is not "diverted" by this definition, even where an earlier manual transcript read called it
that. `tests/test_pack_improvement_golden.py::test_pi_t15_grid_1_golden` pins the verified superset
(`{3ff04431d3b5ac27, 757143056c649892}`) rather than the full four-cell text above.
