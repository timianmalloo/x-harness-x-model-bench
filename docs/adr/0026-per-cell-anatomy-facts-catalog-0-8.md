---
id: "adr-0026-per-cell-anatomy-facts-catalog-0-8"
title: "ADR-0026: Per-cell anatomy - four new grading-pass fact streams (served, reasoning, prompt_parts, harness_events), the existing report-time derivations extended, and catalog 0.8's drift split and attention drift"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Lean re-run at equal reasoning (operator 2026-10-11)"
tags: [benchmark, telemetry, reasoning, fact-stream, drift, catalog, instrumentation]
links:
  - { to: arch-lean-rerun, rel: refines }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: adr-0019-catalog-0-7-property-metrics, rel: depends-on }
  - { to: adr-0024-combo-settings-and-served-read-back, rel: depends-on }
review-by: "2027-04-11"
summary: >-
  The grading pass reads four native facts into hash-chained streams that bench verify checks: served settings,
  every reasoning item (visible text or summary, else encrypted-only or omitted, never reconstructed), the fixed
  prompt parts each harness sends, and hook, skill-load and compaction events. Tool phases, bytes returned, context
  curves, re-reads and time anatomy extend the report-time derivations that already exist (tool_inputs,
  context_growth, pack_improvement's classifier, views' busy and idle time); nothing is defined twice. Catalog 0.8
  splits drift into machine-written, task-implied and discretionary lines by grader rule (no task-version bump),
  makes the drift metrics apply to every task with a radius, and adds attention drift.
review-suggested:
  - { by: arch-lean-rerun, on: 2026-10-11, reason: "lean re-run amendment: bench-matrix/3 settings, served read-back (HB-VAL-010/011), Grok and agy cells, catalog 0.8 drift split, cost-compare report (ADR-0024..0027)" }
---

# ADR-0026: Per-cell anatomy facts and catalog 0.8

- **Status:** Proposed (revised at the gate, 2026-10-11: council findings 11, 12, 13, 14, 15, 21)
- **Date:** 2026-10-11
- **Deciders:** @timianmalloo (Ruling 117 item 3: reasoning text in the run record); authored by the Leader seat.
- **Context:** the prompt's R-REASON, R-ANATOMY, R-DRIFT-FIX; `harness-cost-comparison.html` §5; the 2026-10-11
  spikes.

## Context

- Last run's cost page explained Copilot's 9.56x pack-on cost by hand (its footer). None of it is in the bench's
  records.
- Reasoning reaches no bench record. `normalize.BUCKETS` leaves reasoning tokens out of totals (`normalize.py:29`);
  Claude Code's reader returns `reasoning: None` (`claude_code.py:126-128`). Verified.
- Report-time derivations already exist and are the reuse targets (Verified at the gate): every reader's
  `tool_inputs()` returns `paths`, `command`, `is_write` (`telemetry/__init__.py:206-215`);
  `report/pack_improvement.py:250-312` classifies tool calls; `report/context_growth.py` and `grade/cost.py` derive
  the context curve; `views.py:241-300`, `:388` derive busy and idle time.
- Model time is `not recorded` for Claude Code and Codex, because their rows have `start == end` (Inferred from
  `views.py:241-300` with the two readers).
- Drift: `.pytest_cache` is not excluded (`_changes.py:34`). **None of the ten lean tasks runs the drift grader**;
  all list `graders: [correctness, property]` (Verified at the gate), so the 2026-10-10 page's drift was a hand
  re-grade. Five tasks' radius omits the needed test file (RW2, NG1, NG2, SM1, SM2). The property graders already
  skip test paths (`diffstats.py:123`, `rework.py:75`, `noguess.py:197`), so pass/fail is not affected.
  `report/pack_improvement._matches_blast_radius` is a second radius definition (`fnmatch`, case-insensitive on
  Windows, against `_changes.in_radius`'s `fnmatchcase`, `_changes.py:262`).

## Decision

1. **Four new grading-pass fact streams**, written by `grade/runner.py` beside `model_calls` and `tool_calls`
   (`PASS_FACTS`), declared in `views.FACTS` and `views.KEYS`, hash-chained, sealed and checked by `bench verify`.
   Rows use the ledger's canonical types (str, int, None, list, dict; flags are 0/1 ints). Requested values are
   never stored: they are the plan's.

   | stream | one row is exactly one … | columns (beyond `kind, run_id, extraction_id, cell_id, native_session_id`) |
   | --- | --- | --- |
   | `served` | setting of one cell, as one source showed it | `field` (model_served · model_api · effort · context_tokens · context_tier · reasoning_summary), `value`, `not_recorded`, `source` |
   | `reasoning` | reasoning item the harness recorded | `native_ordinal` (its request), `item_ordinal`, `source_kind` (text · summary · encrypted-only · omitted), `text`, `chars`, `reasoning_tokens`, `opaque_sha256` |
   | `prompt_parts` | part of the fixed prefix one cell's harness sent | `part` (system · tools · skills · instruction_file · agents_md), `path`, `chars`, `delivery` (inlined · on-demand · listed), `source` |
   | `harness_events` | hook invocation, skill load or compaction | `event` (hook · skill_load · compaction), `name`, `start`, `end`, `ok` (0/1/None), `detail` |

   **Sources per harness.** Verified where a spike read it; Flagged where design-slice must spike it. A Flagged
   source that turns out absent is `not recorded: <reason>`.

   | harness | reasoning | prompt parts | hooks · skills · compaction |
   | --- | --- | --- | --- |
   | claude-code | thinking `summary` (display `summarized` via `session/new` `_meta`; Verified) | instruction files from transcript attachments (Flagged); system prompt and tools (Flagged) | hook attachments (Flagged); skill loads (Flagged); compaction boundary rows (Flagged) |
   | codex | `response_item reasoning` `summary_text` + `encrypted_content` (Verified) | rollout developer/user items, incl. the injected AGENTS.md block (Verified, `codex.py:61-65`); tools not in the record (Verified) | hooks (Flagged); compaction events (Flagged) |
   | copilot | `assistant.message.reasoningText` (summary; Verified) | debug-log request body (Verified: full request bodies) | `hook.start`/`hook.end` (Verified, `copilot.py:126-130`); skill tool calls (Verified: `skill` tool) |
   | grok | `chat_history.jsonl` `reasoning.summary` + `encrypted_content` (Verified) | `system_prompt.txt`, `tool_definitions.json`, `prompt_context.json` (Verified) | `events.jsonl` (Verified: timing, tools; hooks Flagged); compaction (Flagged) |
   | agy | thinking text in `conversations/<id>.db` `steps.step_payload` (protobuf, stdlib wire decoder; Verified present); failed decode → `omitted` with `thinking_tokens` | `gen_metadata` (Verified: full prompt) | steps (Flagged) |

   - **Reasoning.** Text is stored as the harness stored it; nothing is reconstructed or paraphrased. An item with
     only an encrypted payload is `encrypted-only` with its sha256. A harness that reports only tokens yields one
     `omitted` row per request with the count.
   - **Location (Ruling 117 item 3).** The `reasoning` segments are `runs/<run>/reasoning/<segment>.jsonl` (`runs/`
     is git-ignored, Verified). `docs/audit/audit-log.jsonl` gets one entry per batch with the stream name, row
     count and sealed head hash.
   - **Pack-off check for every harness.** `prompt_parts` rows with `part: instruction_file` make the pack-off rule
     (0 instruction files) checkable for every harness at the probe (ADR-0024 §6), not only Copilot's plan probe.
   - **Erratum (Coordinator #2, 2026-10-12; J0 rulings on R-CONTRACT-FACTS's DR1 and DR2, landed in `f1a65146`).**
     `harness_events` rows also carry **`native_ordinal`** (the event's position in its record), and the stream's
     key is `(run_id, extraction_id, cell_id, native_session_id, native_ordinal)`, so two identical events never
     collide. The `served` stream is **multi-source**: a reader's `served` hook may return a tuple of
     `ServedSettings`, one per source, and every source's rows are written; an identical row (a field no source
     read) is written once. Separately, Copilot's "Verified: full request bodies" above is Flagged until
     R-COPILOT-P's `-p`-mode debug-log records show it (Leader addendum). Recorded in
     `docs/coordination/coordination-lean-rerun.md`, *Errata* E8 and E12.
2. **Per-request rows in `model_calls`** (columns unchanged; readers fill them where the record allows):
   - Claude Code: per `requestId`, deduplicated (Verified); `start` not recorded (the stamp is write time).
   - Codex: per `token_usage_record` / `token_count` (Verified).
   - Copilot: per response from the debug process log (`--log-level debug`; Verified); without it, the session
     totals as today, marked `per-session totals only`.
   - Grok: per turn (`usage.json`), `requests` = `modelCalls`; per request `not recorded: per-turn totals only`.
   - agy: per `agent_response` step, times from the stream driver's sidecar (ADR-0025 §3).
3. **An ACP update timeline, generic in `driver.py`.** The driver writes `acp-timeline.jsonl` in the cell home, no
   content: consecutive messages of the same `update_kind` (and `tool_call_id`) collapse into one line
   `{first_mono_ns, last_mono_ns, count, method, update_kind, tool_call_id}`, so its size is bounded by the number
   of kind changes, not by streamed chunks. Writes are buffered and best-effort: a write failure stops the timeline
   and is noted, never a cell failure (the stderr-tail pattern, `engine.py:799-803`). Its size is measured at the
   probe. It gives every ACP harness a **model-time estimate** (from a prompt or tool result to the next tool call
   or turn end), a separate labelled measure, *derived from ACP arrival times*.
4. **Derived, never stored: the existing derivations, extended.** No `anatomy.py`.
   - *Tool phases and bytes:* `ToolInput` gains `bytes_returned`. The phase rule extends the classifier in
     `report/pack_improvement.py` (moved to one shared report module): `edit` for an
     edit-class tool or a write; `verify` for a command matching the declared test and lint patterns (pytest, tox,
     ruff, mypy, pyright, unittest); `explore` for read, search and list tools and other commands before the first
     edit; `other` for the rest. `pack_improvement`'s existing categories are computed from the same function.
   - *Context curve:* `report/context_growth.py`, per request, with the peak against the served window from
     `served` and compactions from `harness_events`.
   - *Re-reads:* a path read again with no edit to it in between, from the same `ToolInput` sequence.
   - *Time anatomy:* new measures beside `views._model_time` and the existing idle (`views.py:269-276`), which keep
     their meaning in `report.html`: native model time where recorded, the ACP-arrival estimate as its own labelled
     measure, hook time, and `idle` = wall − the union of the model, tool and hook intervals used. With no model
     intervals of either kind, idle is `not separable`, never a number.
   - `_matches_blast_radius` (`fnmatch.fnmatch`, case-insensitive on Windows, `pack_improvement.py:255`) is replaced
     by `_changes.in_radius` (`fnmatchcase`), the one radius definition. This is a stated output change: where a
     path differs from its radius entry only by case, pack-improvement values move. The track runs
     `tests/test_pack_improvement_golden.py` and the non-lean golden before and after, and re-captures any moved
     golden with the reason "radius match is case-sensitive (one definition)".
5. **Catalog 0.8 (drift; R-DRIFT-FIX).** Register entries first (§6), then:
   - **One machine-written list** in `grade/_changes.py`, separate from `BUILD_OUTPUT` (which the property graders
     use, `property.py:487`, `diffstats.py:92`, and which does not move): tool caches (`config.GENERATED_DIR_NAMES`
     reused, plus `.mypy_cache` and `.ruff_cache`) and the exact paths the pack's hooks and audit script write
     (read from the pack's hook files, not a broad `docs/audit` glob). The prompt classes hook and audit logs as
     machine-written; the report shows those lines on their own row beside the tool caches, so a pack-induced audit
     edit is visible, never hidden in a total.
   - **Task-implied** = a path `_changes.is_test_path` accepts, outside the radius. Stated limit: an unrequested new
     test file counts as task-implied.
   - **Discretionary** = every other changed line outside the radius.
   - Metrics: `drift_machine_lines`, `drift_task_implied_lines`, `scope_creep` **redefined** as discretionary lines
     (id kept; the 0.8 note says so; its anchor `[1504, 0]` came from smoke-1 under the old definition and is
     Flagged for re-anchoring before the freeze), and `attention_drift`: the share of read and search targets
     outside the *neighbourhood* (the radius, the modules the radius files import by a static scan of the base
     tree, test paths, and paths the task prompt names). Calls with no extractable path are excluded and counted.
   - **Applicability without a task-version bump.** A catalog field (`all_tasks: true`, validated by
     `config.validate_metrics`) makes `runner.applicable` include these drift metrics for every task with a
     `blast_radius`, whatever its `graders` list. Mechanism Flagged until design-slice reads `runner.applicable`
     against the freeze controls.
   - **Freeze steps:** `0.8.dev` while tracks build; then the `bench/catalog-freeze.yaml` entry, the X1 export and
     board goldens (`tests/test_catalog_version.py`). The non-lean report golden prints `loaded: 0.7`
     (`tests/goldens/report-nonlean-arms.html`), so 0.8 moves it: its GOLD-A move (ADR-0027 §5) is sequenced first,
     and its re-capture states "catalog version only".
   - **Fix by grader rule, not by task version.** The five tasks keep their versions: the property graders already
     tolerate the test file, a bump would re-key five tasks' discrimination records, and the rule fixes the class
     for every task.
6. **Register entries (classes, before the code).** `DRIFT-MACHINE-A`: machine-written files counted as
   discretionary scope creep. `RADIUS-TEST-A`: a task radius omits a file the task needs, and a radius consumer
   that does not use `is_test_path` counts it. Sweep: every radius consumer (`diffstats`, `rework`, `noguess`,
   `drift`, `pack_improvement._matches_blast_radius`). Controls: a drift-split test on a fixture working copy
   holding a cache, a hook log, a test file and a README edit; a test that every radius consumer calls
   `_changes.in_radius` and either calls `is_test_path` or is named exempt. `LEAK-HOME-A` (candidate): a home
   variable relocates only part of a harness's user state (Grok's `GROK_HOME`, Verified); control: the probe's
   pack-off `prompt_parts` list 0 instruction files for every harness.
7. **Bounds (BND-A).** The probe's pack-on cells measure the largest debug-log request body, agy stream line and
   reasoning row; the readers' bounds are sized from those with a stated margin. The Copilot debug log counts in
   the HB-PRE-003 disk projection.

## Consequences

- The cost page's hand measurements become bench facts, emitted on every graded cell with no flag.
- `bench verify` covers the reasoning text.
- Catalog 0.8 moves `scope_creep`; last run's 0.7 values are not comparable on that axis, and the report says so.
- Old runs have none of the new streams; every new view reads `not recorded (stream absent)`.

## Alternatives considered

- **A new `anatomy.py` and stored tool arguments.** Rejected at the gate (finding 11): two definitions of tool
  classification and of the context curve.
- **Compute reasoning and served settings at report time.** Rejected: `bench verify` could not cover the text, and
  validity needs the served settings at view time.
- **Fix the five radii by task-version bumps.** Rejected (§5).
- **Class all of `docs/audit` as machine-written.** Rejected at the gate (finding 12): it would hide agent-authored,
  pack-induced edits.
- **Reasoning text in `docs/audit`.** Rejected by Ruling 117 item 3.

## Amendment 1 (2026-10-14): `prompt_parts` gains an optional `tokens` column

- **Why.** Copilot (`copilot -p`) records its tool definitions' size only in tokens: each `session.usage_checkpoint`
  carries `promptCacheBreakState[].models[].tool_tokens` beside `tool_count` (2187 for 9 tools in every checkpoint of
  the 2026-10-13 lean runs lean-20261013T222133 and lean-20261013T222416; Verified on the archived records). The full
  definitions are in no file of the cell home, so the `tools` part has no character count. Plan row A7.
- **Column.** `prompt_parts` rows gain `tokens: int | None` (after `source`), and `PromptPart` gains the same field with
  a `None` default. `None` is "not recorded", never 0. `chars` and `tokens` are separate measures: nothing converts one
  into the other, and a part may carry either, both or neither.
- **Measure class.** Non-additive across requests (it is the size of one catalogue, not a count of tokens sent); it
  is per cell, read from the first usage checkpoint that states one size for its models. If the models of that
  checkpoint disagree, or no checkpoint states one, the value is `None`.
- **Who fills it.** Only Copilot's `tools` part. Claude Code, Codex, Grok and agy leave `tokens` `None` by the dataclass
  default; their parts keep their `chars` unchanged.
- **Migration.** The streams are append-only. A `prompt_parts` row written before this amendment has no `tokens` key
  and reads as `None` (`pack_cost` maps rows with `r.get("tokens")`). No rewrite and no backfill. The key
  `(run_id, extraction_id, cell_id, native_session_id, native_ordinal, part, path, source)` is unchanged. A grading pass
  run after the join writes a new `extraction_id` (the hash covers `telemetry/*.py`), so a re-grade adds new rows
  beside the old.
- **Consumers.** `normalize.prompt_part_rows` emits it; `pack_cost` carries it through `CellFacts.prompt_parts`.
  `pack_cost`'s fixed-prefix derivation and `cost_compare`'s characters-per-part table read `chars` only, so they are
  unchanged: the `tools` part is still an exact zero delta when its fingerprint is identical in both cells of a pair
  (`pack_cost._identical`). Showing the catalogue's tokens on a report is a later, separate change.
