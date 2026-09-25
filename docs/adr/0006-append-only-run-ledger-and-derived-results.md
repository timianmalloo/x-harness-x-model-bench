---
id: "adr-0006-results-data-model"
title: "ADR-0006: A hash-chained, append-only record per run; every result is a derived view"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, data-model, persistence, grain]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
review-by: "2027-09-23"
summary: >-
  The durable record is a set of append-only, hash-chained JSON Lines facts per run with declared
  grains (lifecycle events, model calls, tool calls, archive files, grading passes, scores, verdict uses,
  egress events), immutable content-addressed dimensions, and one shared content-addressed verdict cache.
  Current states, costs, composites and statistics are derived projections computed in memory; no
  results database is persisted.
---

# ADR-0006: A hash-chained, append-only record per run; every result is a derived view

- **Status:** Proposed
- **Amended (2026-09-24, ruling R-26; design `design-phase2-copilot-profile` section 3):** the `model_calls` grain is re-declared as one native usage report per model, with an additive `requests` count and `model` in the key; `tool_calls` gains `outcome_code` (ruling R-27). See "Amendment 1" under Facts and their grains.
- **Amended (2026-09-25, ruling R-15 Q6):** `model_calls` gains `total_nano_aiu`, Copilot's native AI-unit measure (`modelMetrics.<model>.totalNanoAiu`) stored verbatim as an additive column, null (never 0) when the native record does not carry it. See "Amendment 2" under Facts and their grains.
- **Amended (2026-09-25, R-58 c1 and c6; design `phase3-gateway-judges` sections 4.1, 4.2 and 9.1; W3-GW-I slice 3):** `verdict_uses` gets its grain, key, closed `outcome` enum, `code`, placement in the grading pass's own sealed segment and its `heads` entry; `model_calls` rows with principal `gateway` are the judge calls' usage. See "Amendment 3" under Facts and their grains.
- **Date:** 2026-09-23 (revised after council round 1)
- **Deciders:** @timianmalloo; authored by Claude Code with the Data & Persistence Architect lens
- **Context spec/architecture:** `docs/specs/harness-bench.md` (conceptual model; US-4, US-17–US-19, US-22–US-27, US-47, US-52)

## Context

The spec's model has immutable versioned entities (task version, BOM, catalog, price list, plan) and change over time as events. Its constraints:
- grading is a pure function of an archive (US-26);
- resume is idempotent (US-18);
- historical scores never move silently (US-4);
- derived quantities are never stored as truth.

The domain standard defaults to dimensions plus append-only facts (DM5), with analytical layers as derived projections (DM6). Council round 1 found:
- a re-grade would collide on the score key;
- several spec facts had no declared grain;
- cached verdicts were stored inside one run but reused by others;
- a key part could be null;
- append-only was not enforced across a crash.

## Decision

### Physical form and integrity (DM11)

- **Where facts live.** `runs/<run_id>/` holds one directory per fact. Each writer session appends to its own **segment** file (JSON Lines).
- **Every line is a hash chain.** Each line carries `seq`, `prev_hash` and `hash`. `hash` is the sha256 of the UTF-8 bytes of the line's canonical form, which includes `prev_hash`. The canonical form is `json.dumps(record_without_hash, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, with integers and strings only. No floats: a non-integer measure is a decimal string at the scale its catalog entry fixes. The form is a subset of JCS (RFC 8785). Each line is written with one `write`, then flush, then `os.fsync`.
- **Sealed segments.** A writer closes its segment with a `segment.sealed{count, head_hash}` line. `run.completed` records the head of every segment the engine process wrote, including its own grading pass. A later `bench grade` pass is self-sealed.
- **Abandoned segments.** A grading segment without a seal whose writer no longer holds `grade.lock` belongs to a dead writer. No process ever writes into another writer's file, because a torn tail there would fuse with any appended line. Instead the next grading pass, while holding the lock, records `segment.abandoned{segment_id, line_count, head_hash}` in **its own** segment, where the count and head are those of the last whole line. `verify` accepts an unsealed segment that such a record names, up to that head, and reports it as abandoned (HB-LED-004, a warning, exit 0). It skips an unsealed segment whose lock is held. Views read neither.
- **Torn tail.** Only the segment's own writer, on reopening, may drop a final line that has no newline or fails to parse, and it records a `ledger.tail_repaired` event. A reader never repairs: it ignores the torn tail of an unsealed segment. Any other broken line, chain break, or broken seal is an integrity error.
- **Verification.** `bench verify <run_id>` checks every chain. Tests that attempt a rewrite, a truncation and a mid-file insert must fail verification before phase 1 closes.
- **Single writer.** Each fact directory has exactly one writer process at a time. The run engine writes lifecycle facts. A grading pass (from `bench grade` or from the engine) writes grading facts and its `events` rows only while holding `grade.lock`, which excludes every other writer of `events` (ADR-0007).

### Identity

- `cell_id` = a deterministic hash of `(task_version_hash, combo_id, pack_setting, repetition)`, computed in the plan. Resume and run comparison (US-52) use it.
- Dimension files (plan, BOM version, catalog version, price list version, harness profile) are content-addressed. A test asserts that each id equals the file's hash.

### Facts and their grains

| Fact | Grain: one row is exactly one … | Key | Measures and additivity | Writer |
| --- | --- | --- | --- | --- |
| `events` | state transition of one run-scoped entity: the run, a cell, an attempt, a decision request, a control input, a grading pass, or the ledger itself (`ledger.tail_repaired`, `segment.sealed`). Its states are those of `models/run_lifecycle.tla`. | `(run_id, segment_id, seq)`, plus `entity_kind`, `entity_id` and `recorded_at` | none. Rows carry the transition's attributes: e.g. `attempt.process_started` holds the executed harness build and its hash, the PID and process creation time; `attempt.session_opened` the native session id; `cell.archived` the `archive_attempt` and `archive_hash`. | run engine (its engine thread only); grade process for grading passes |
| `model_calls` | model's token usage in one native usage report, by one principal (a cell, or the model gateway), as read by one extraction (Amendment 1; was "model request") | `(run_id, extraction_id, principal, native_session_id, native_ordinal, model)`; `cell_id` when the principal is a cell. `extraction_id` is the normaliser build hash; `native_ordinal` is the 1-based line number of the report in the native file; `model` separates the entries of one report | Tokens in **disjoint buckets**: uncached input, cache read, cache write, output (additive). Reasoning is a component of output, never added to it. `requests`: the number of model requests the report covers (additive; 1 when absent). Start and end timestamps (not durations), only when `requests` is 1. Native billing units (additive). | grading pass (normaliser) |
| `tool_calls` | tool invocation inside one cell, as read by one extraction | `(run_id, extraction_id, cell_id, native_session_id, native_ordinal)` | start and end timestamps; `ok` (the native success flag, null when not recorded); `outcome_code` (the native error code of a failed call, e.g. Copilot `denied`; null on success or when not recorded) (Amendment 1) | grading pass (normaliser) |
| `archive_files` | file or link in one archive attempt of one cell | `(run_id, cell_id, archive_attempt, path)` | size (additive); sha256; kind (file or link, never followed) | archiver, through the engine thread |
| `scores` | value of one metric for one cell in one grading pass | `(run_id, grading_id, cell_id, metric_id)` | value (non-additive); NULL with a reason when NOT_RECORDED; the `archive_attempt` graded and the `extraction_id` read (references by identity; the archive hash is not repeated) | grade process |
| `verdict_uses` | lookup of one judge's verdict (or one matcher's match) on one rubric item for one cell, by one grading pass; a failed lookup too (Amendment 3; was "use of a cached verdict or match") | `(run_id, grading_id, cell_id, item_id, judge_or_matcher)`; `item_id` is `<metric_id>#<n>` | `outcome` (closed enum: `hit`, `stored`, `race_lost`, `not_allowed`, `failed`) and `code` (the HB code of a `failed` row, null otherwise); `cache_key` and `entry_sha256` (set for `hit`, `stored`, `race_lost`; null otherwise). Non-additive; "cache hit" is derived (`outcome == "hit"`), not a column (Amendment 3) | grade process (`grade/judge.py`, into the pass's own sealed segment) |
| `egress_events` | scan-and-send attempt | `(scope_id, seq)`, where the scope is a run or a report (a report over two runs publishes once) | payload hash; destination; purpose; result: sent, withheld or quarantined | egress gate |

A grading pass is an entity in `events` (`grading.started` / `grading.completed`), carrying `grading_id`, catalog version and grader build hash. The **current score** of a cell for a catalog version is the value from the latest completed grading pass for that catalog version: the greatest `recorded_at` on `grading.completed`, tie-broken by `grading_id`. This rule is defined once, in the projection. A re-grade (after a judge outage or a grader fix) is a new grading pass. Nothing is overwritten.

**Amendment 1 (2026-09-24, ruling R-26 adopting the Data & Persistence Architect's C1–C3; R-27 for `tool_calls`).**
- **Grain.** One `model_calls` row is exactly one model's token usage in one native usage report, by one principal, as read by one extraction.
  - For Claude Code and Codex, a report is one model request: the phase-1 rows, unchanged.
  - For Copilot, a report is the per-model entry in the **last** `session.shutdown` event's `data.modelMetrics` in `session-state/<id>/events.jsonl`. A per-cell Copilot ACP home writes no per-request usage (capture window 1).
- **`requests`.** An additive count of the model requests one row covers:
  - Claude Code and Codex: 1;
  - Copilot: `modelMetrics.<model>.requests.count`;
  - a row written before this amendment, which has no field: 1.
- **`start` and `end`** are set only when `requests` is 1. Otherwise they are null, and model time is NOT_RECORDED rather than a span that includes tool time.
- **A row count is not a call count.** The number of model calls of a cell is Σ `requests` over its current extraction, read by one compute reader. A guard test asserts that no view counts rows.
- **Key.** Two models in one Copilot `session.shutdown` share its line number, so `model` joins the key: `(…, native_session_id, native_ordinal, model)`.
  - One report has at most one entry per model, because `modelMetrics` is keyed by model id.
  - For Claude Code and Codex, a line names one model, so the key is unchanged in effect.
  - Rejected: a packed ordinal (`line × 1000 + index`), which is a synthetic key hidden in a native field; and a new sub-ordinal column, which adds a field for what `model` already identifies.
- **`tool_calls.outcome_code`.** The native error code of a failed tool call (Copilot `tool.execution_complete.error.code`, for example `denied` when a hook refuses the call). Null on success, or when the harness records no code. It is the signal that sees a native permission denial below ACP (US-14; R-27).
- **Migration.** The ledgers are append-only. `requests` is absent from phase-1 rows and reads as 1; `outcome_code` is absent and reads as null. A phase-1 ledger has one model per line, so it satisfies the new key. No rewrite and no backfill.
  `grading.completed.unreadable_records` (cell_id → reason, R-15; W2-VIEWS) is absent from a pass written before R-15: a missing key means "not checked", and that pass's cells read as before (a golden-ledger regression test pins it). The latest completed pass decides, so a later pass with a new extraction supersedes an earlier reading.
- **Writers and readers.**
  - The grading pass (normaliser) stays the only writer.
  - `ModelCall.requests` and its docstring stating this grain live in `telemetry/__init__.py` (W1-COP-R).
  - `normalize.model_call_rows` and `tool_call_rows` emit `requests` and `outcome_code` (W1-COP-R).
  - The `views.py` key tuple (`views.py:33`), the `calls_per_cell` compute reader and the guard test belong to W1-COP-I, which wires row 4.

**Amendment 2 (2026-09-25, ruling R-15 Q6; R-26 c4 / R-31 narrow what wave 1 carries forward to `totalNanoAiu` alone).** The `model_calls` row gains `total_nano_aiu`, filling in the "Native billing units (additive)" measure named above.
- **Column.** `total_nano_aiu: int | None`, Copilot's own `modelMetrics.<model>.totalNanoAiu` (capture window 1's committed fixtures read 4,496,520,000 / 43,266,550,000 / 31,375,570,000 nano AI units for the off/on/on-rev92 samples), stored verbatim -- no arithmetic, no conversion, and **no second definition of tokens is derived from it** (R-15 c2).
- **Measure class.** Additive, at the same grain as the row it lives on (one model's usage report): a cell's AI-unit total is Σ `total_nano_aiu` over its current extraction's `model_calls`, the same rule Amendment 1 gives `requests`. Nothing sums it yet in wave 1: the column exists so a later reader (`grade/cost.py`, a later phase) has one place to sum from, never two.
- **Unit.** Nano AI units, Copilot's own native billing scale (1e9 nano-units = 1 AI unit). Read as an integer (`is_count`, the same bound every other bucket in this row uses): a float, a negative value, or a non-numeric value is treated as absent, matching the rest of the row.
- **Missing key.** Absent, or not an int, reads `total_nano_aiu: null` (never `0`) on the row itself -- that null **is** the "not recorded" evidence, degrade to not recorded (IO1), never a plausible wrong number. `0` itself, when the native record reports it, is a measured value and is stored as `0`, not treated as absent. **This absence is *not* added to `Extraction.missing`** (D&P loop-back, 2026-09-25): `grade/runner.py` nulls `cost_usd` whenever `ex.missing` is non-empty (US-27), and `total_nano_aiu` has no `cost_usd` consumer -- a column no reader consumes must never gate a scored metric. The `input_tokens` arithmetic check and the four price-relevant buckets keep flagging `ex.missing` as before; only `total_nano_aiu`'s own absence is exempt.
- **Claude Code and Codex.** Neither native record carries an AI-unit measure; their `ModelCall` rows leave `total_nano_aiu` null by the dataclass default, the same pattern `reasoning` already uses for a bucket a harness's format has no concept of.
- **Migration.** The ledgers are append-only. A `model_calls` row written before this amendment has no `total_nano_aiu` field; it reads as null (not recorded), never `0` -- the same "absent reads as the safe default" rule Amendment 1 gives `requests` and `outcome_code`. No rewrite and no backfill.
- **`extraction_id` moves.** `normalize.extraction_id()` hashes every `telemetry/*.py` source file, so this amendment's join changes it: a grading pass run after the join writes a new `extraction_id`, distinct from any pass run before it, even for an already-graded cell (ADR-0006's "extractions are written once" rule, below -- a re-grade under the new build adds new rows beside the old, it never overwrites). The Leader sequences this join before any wave-3 gate pass, so every gate-pass score names the post-join extraction.
- **Writers and readers.** The grading pass (normaliser) stays the only writer. `ModelCall.total_nano_aiu` and its docstring live in `telemetry/__init__.py`; `copilot.read` fills it from `modelMetrics.<model>.totalNanoAiu`, without flagging its own absence in `Extraction.missing`; `normalize.model_call_rows` emits it (W3-COST). `views.model_call` (the ledger-row-to-`ModelCall` mapper) treats `total_nano_aiu` the same as `requests`: a row that does not carry it (a pre-amendment ledger) uses the dataclass default, not a `KeyError` -- a mechanical consequence of the new field, not a report or view content change. No reader consumes the value yet: `grade/cost.py` and any report or view change are a later phase (R-15: "Wave 1 keeps them in the sample's provenance only, as designed" -- this amendment is the wave-3 storage row; consumption is R-15 Q6's catalog row, still to come).

**Amendment 3 (2026-09-25, R-58 c1 and c6; design `phase3-gateway-judges` sections 4.1, 4.2 and 9.1; W3-GW-I slice 3).** `verdict_uses` is fixed, and the judge calls' usage joins `model_calls` under principal `gateway`.
- **`verdict_uses` grain.** One row is exactly one lookup of one judge's verdict on one rubric item for one cell, by one grading pass. A failed lookup gets a row too, so a miss is reported (US-26 c2).
- **Key.** `(run_id, grading_id, cell_id, item_id, judge_or_matcher)`, the column name kept so a matcher row fits the same key. `item_id` is `<metric_id>#<n>`. `judge_or_matcher` is the judge's model id.
- **Attributes.**
  - `outcome`, a closed enum of 5 values: `hit` (read from the store, no call); `stored` (called now, the entry written now); `race_lost` (called now, another writer's entry used); `not_allowed` (a miss without `--allow-model-calls`); `failed` (NOT_RECORDED).
  - `code`: the HB code of a `failed` row (`HB-GW-001`..`HB-GW-011`, in `errors.RUN_CODES`), null otherwise. When several apply, the first failing step of the gateway pipeline is the one recorded; every NOT_RECORDED path maps to exactly one `(outcome, code)`.
  - `cache_key` and `entry_sha256`: set for `hit`, `stored` and `race_lost`; null otherwise.
  - "Cache hit" is derived, `outcome == "hit"`. It is not a column (DM7).
- **Additivity and the call grain.** Rows are items: one judge call yields one row per rubric item (7 for C1). A call-level quantity (calls, misses, failures) is counted over distinct `(cell_id, metric_id, judge_or_matcher)` within a pass, by one compute reader, `views.judge_calls`. A guard test asserts that no view counts `verdict_uses` rows as calls: the same rule as Amendment 1's "a row count is not a call count".
- **Placement and heads.** The grading pass writes the rows through `grade/judge.py` into its own `verdict_uses/<grading_id>.jsonl` segment, seals it with its other facts, and records its head in `grading.completed.heads` (ruling R-2), so `bench verify` ties it to the pass. `verdict_uses` is in `views.FACTS` and `runner.PASS_FACTS`.
- **History rule.** Append-only. A re-grade is a new pass with new rows.
- **The store key** (`cache/verdicts/<key>.json`, "Shared verdict cache" below): `key = sha256(canonical({"request_sha256", "schema_sha256", "model", "invocation_sha256"}))`. `request_sha256` covers the rubric, the scrubbed artifact, the template and the scrub version; `invocation_sha256` hashes the argv template with its volatile slots as placeholders, the judge system prompt, the output mode, the harness, the build version and the exe sha256. So the list below (artifact, rubric, prompt template, output schema, model, backend) is covered.
- **`model_calls`, principal `gateway`.** One row is one model's usage in one native usage report of a judge CLI, read by one extraction (Amendment 1's grain, unchanged). `principal` is `gateway`; `cell_id` is null, because judge spend is overhead (US-17). The source is the call's own native record, archived into the pass at `grading/<grading_id>/gateway/<call_id>/record.jsonl`. `stored` and `race_lost` rows came from a call, so that call's rows are written; `hit`, `not_allowed` and a `failed` row before the spawn made no call and write none. A warm second pass writes none (R-58 c6).
- **Writers and readers.** Writer: the grading pass (`bench grade`, or `bench grade --allow-model-calls`), through `grade/judge.py`. Readers: synthesis (design section 10), the calibration and agreement projections, `views.judge_calls`, and `bench verify`.
- **Migration.** Additive; no backfill. No ledger holds a `verdict_uses` row before this amendment; a pass without the segment reads as "judged metrics not graded". No rewrite, and no rollback is needed.

**Extractions are written once.** A grading pass writes `model_calls` and `tool_calls` for a cell only if no completed pass already holds that cell's `extraction_id`; it checks this under `grade.lock`. A re-grade with the same normaliser build therefore reuses the existing rows, and its scores name that `extraction_id`. A normaliser fix gives a new `extraction_id` and new rows beside the old. **The current extraction** of a cell, for a catalog version, is the one named by its current scores for that version, so totals never sum two extractions.

**Archive hash.** `cell.archived` carries `archive_attempt` and `archive_hash`, a commitment over that attempt's sorted `archive_files` rows. `verify` recomputes it from the rows and fails on a mismatch (HB-LED-005).

**Shared verdict cache.** Judge verdicts and clarification matches live in one content-addressed store outside any run, `cache/verdicts/<key>.json`, written create-if-absent (the first writer wins; an existing key is never replaced). The key covers: artifact hash, rubric or matcher version, prompt-template version, output-schema version, model id and backend. A run's own `verdict_uses` rows make its grading reproducible alone, as long as the cache is kept.

### Dimensions

Dimensions are immutable, content-addressed versions (DM10 Type-2 by identity): task version, BOM version, catalog version (definitions, weights, normalisation anchors, rubrics, radar axis order), price list version, combo, harness profile, plan. The planned harness build lives in the plan; the executed build lives in `events` (`attempt.process_started`); US-12 compares the two.

### Derived, never stored (DM7)

All of these are projections computed in memory by `bench report` from the verified facts, with no persisted database (pure-Python functions in phase 1, see `docs/notes/decision-sqlite-views.md`; a SQL engine only if its upgrade trigger fires):
- current cell outcome and validity;
- cell wall time (outcome time − launch-intent time);
- `cost_usd` (model calls × the price list version named in the report);
- coordinator overhead (the coordinator and gateway principals);
- composites, pass@k, pass^k, cost-of-pass;
- bootstrap intervals (the seed is in the plan);
- pack effect, comparison and ranking.

"Identical results" (US-26) is claimed for **canonical sorted exports** of the views. A test rebuilds them twice and compares the hashes.

**Comparison (US-52).** Each run's plan names its own catalog, price list and BOM versions. A comparison reads both plans, refuses if they differ in combos, BOM or catalog, and otherwise joins by `cell_id` ingredients (task version, combo, pack, repetition).

### Retention

- `runs/` is kept until P1 deletes it. Ledgers may outlive pruned archives: pruning records `archive.pruned` in `events`, and US-41's "archive absent" state covers it.
- The verdict cache is kept as long as any run references it. Pruning the cache makes those runs' re-grades call judges again, and the run says so.

## Alternatives considered

- **A persisted `results.duckdb` as the operational store:** rejected. It is mutable, duplicates the archive, and makes grading impure.
- **Separate current-state files (`cell_outcomes`):** rejected. They are the terminal transition of a cell, already in `events`; a second record of one fact would drift (DM7).
- **One fact file per entity kind (`decision_events`, `attempts`, `run_events`):** rejected in favour of one lifecycle log with a declared grain ("one state transition of one run-scoped entity"). One ordered, single-writer log maps one-to-one onto the TLA+ model's trace and keeps one hash chain.
- **Per-file manifest hashed at close:** rejected. A crashed run's files are never closed. The per-line chain survives a crash.
- **Normalised relational schema, or event sourcing of scores:** rejected. Nothing mutates in place, and scores are recomputed, not replayed.

## Consequences

- **Positive:**
  - The audit trail is the data.
  - Resume reads `events`.
  - Re-grades and new catalog versions append beside the old ones.
  - Integrity is checkable offline.
- **Negative / accepted trade-offs (DM13 deviation):**
  - The operational store is files, not a database.
  - Current-state reads scan `events`, accepted at ≤ 576 cells per run.
  - Token buckets must be normalised per harness: OpenAI-style input includes cached tokens; Anthropic-style input excludes them. [Verified in spike records: Codex input 19,597 includes 12,672 cached; Copilot input 12,948 includes 12,945 cache-write; Claude input 2 with cache counted separately]
- **Follow-ups / new risks:**
  - Property tests for the chain, the grains and the current-score rule.
  - Projections are pure Python until the decision note's upgrade trigger fires.

## Evidence

- Spec conceptual model (gate-cleared).
- `domain-and-data-modelling.md` DM5–DM13.
- Spike native records (token semantics) [Verified].
- Council round 1: Data & Persistence V1–V5, Distributed Systems V2 and V4, Simplifier 2–5.
- Phase-1 design gate round 2 (2026-09-23): canonical hash form, sealed and abandoned segments, owner-only tail repair, `extraction_id` and `archive_attempt` in the keys, write-once extractions, and the archive-hash commitment. These were folded into the decision above, so the ADR and `docs/design/phase1-walking-skeleton.md` carry one definition.
