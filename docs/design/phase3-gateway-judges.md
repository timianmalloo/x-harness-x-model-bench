---
id: "design-phase3-gateway-judges"
title: "Design: the model gateway and the two judges (phase 3, row 17)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 3 · wave 3 (row 17: the gateway, the judges, calibration; built by W3-GW-I)"
tags: [benchmark, gateway, judges, calibration, kappa, blinding, US-26, US-35, US-46, US-47, R-58, R-59]
links:
  - { to: spec-harness-bench, rel: implements }
  - { to: arch-harness-bench, rel: implements }
  - { to: adr-0009-model-gateway, rel: refines }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: adr-0005-egress-control, rel: depends-on }
  - { to: adr-0013-native-cells, rel: depends-on }
  - { to: adr-0012-proportionate-security, rel: depends-on }
  - { to: adr-0003-harness-profile, rel: depends-on }
  - { to: design-phase1-walking-skeleton, rel: refines }
  - { to: note-spike-gw-headless, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2027-03-25"
summary: >-
  Row 17 per R-58 and R-59: one tool-less gateway calls two judges (Anthropic claude-fable-5-1, or the R-58 fallback
  claude-opus-5-5; OpenAI gpt-6-sol) through the pinned headless CLIs, only under bench grade --allow-model-calls and
  never while a run is live. Requests are scrubbed of pack markers and harness, model and combo ids, scanned, egress-
  gated and schema-validated; verdicts live in the create-if-absent cache and each lookup is a verdict_uses row.
  Calibration is one human label per (artifact, rubric item); the header shows inter-judge kappa, each judge's
  agreement with the operator's labels (not recorded until they exist) and the per-cell-vendor verdict split.
  DRAFT (phase A): every measured fact is marked pending spike; the gate runs in phase B.
review-suggested: []
---

# Design: the model gateway and the two judges (phase 3, row 17)

- **Status:** Draft, phase A. Measured facts are marked `pending spike`; the probe is written and self-tested, and its
  five turns are the Leader's (`docs/notes/spike-gw-headless.md`). The gate (Patterns Expert, Simplifier, Test
  Architect, Security & Identity, Data & Persistence) runs in phase B, after the results.
- **Spec / architecture:** `docs/specs/harness-bench.md` US-25, US-26, US-31, US-35, US-46, US-47, the judged-score
  and calibration terms (`:203`, `:208-209`); ADR-0009 (the gateway), ADR-0006 (facts, cache), ADR-0005 (egress),
  ADR-0012 (US-47 scope), ADR-0013 (native processes). Rulings R-58..R-62.
- **Delivery phase:** wave 3, row 17. Built by W3-GW-I (Codex `gpt-6-sol`) in six slices (section 16). The judged scope
  is C1: 6 smoke cells × 7 rubric items (plan version 5).
- **Author:** W3-GW-D (Claude `claude-opus-5-5`), paired with the AI Systems Engineer lens.

## 1. Responsibility

The gateway is the one place where the bench itself calls a model (ADR-0009:34). This design covers its judge path:
build a blinded, scanned, delimited request; call each stipulated judge through its headless CLI with no tools;
validate the answer; cache it; record every lookup. It also covers calibration (κ) and the header's judge block.

Not in this design: the AI summaries (`summarize`, phase 4, ADR-0009:44); the matcher's model rung beyond its contract
(section 14); per-metric definitions and aggregation, which W3-GRADE-D owns (R-59 c2); the egress scanner itself,
which W3-EGRESS owns (R-60).

## 2. Rulings and promises bound here

| Source | Clause | Where it lands |
| --- | --- | --- |
| R-58 DR-1 | Jury: `claude-fable-5-1` + `gpt-6-sol`; ordered fallback `claude-opus-5-5`; fixed and named before any verdict is cached; a switch after is a new catalog version | §5 |
| R-58 DR-2, c3 | Never in-run; only `bench grade --allow-model-calls`; refuse while a run is live | §6 |
| R-58 DR-3, c5 | κ: inter-judge plus each judge vs the operator's labels; human half `not recorded` until labelled; 30 items = 30 labels; labels before any verdict | §11 |
| R-58 c1 | `model_calls` rows, principal `gateway`; US-11 pin check on judges; header names both served ids | §8, §9.3, §12 |
| R-58 c2 | Header: mean (Claude verdict − GPT verdict) by cell vendor, with n; disclosed, never a gate | §12 |
| R-58 c4 | US-46 fixture asks for a command; 0 tool calls per vendor, in the spike note | spike note; §8 |
| R-58 c6 | Second gate pass makes 0 backend calls; the key carries model id and backend | §9.1, test T-GW-12 |
| R-59 DR-5, c2 | `bench/rubrics/<metric>.md` is the rubric; C1's `oracle/rubric.md` byte-identical; NA `no rubric for this task` | §13 |
| R-59 c1 | `catalog_hash` on `grading.started` | §5 (judge stipulation joins the hash; seam) |
| R-60 c2 | The injection fixture goes to a judge only through a qualified backend | §8.4; not in the probe |
| R-62 a3 | Disclose: Claude-authored calibration items judged by a Claude judge | §11, §12 |
| US-35 c1 | Rubric + artifact + oracle; scrubbed; a scan of the captured request finds none | §7 |
| US-35 c2 | > 1 rubric step apart: NOT_RECORDED, flagged, both verdicts shown | §10 |
| US-46 c1 | No tools, no file or shell access; schema-constrained; agent text only as delimited data | §7, §8 |
| US-46 c2 | Injection fixture: ≤ 1 step difference; the item is flagged | §10.3 (the check is EGRESS s2's live run) |
| US-47 | Scan before every judge send; a hit is `withheld: sensitive content` | §7.4 |
| US-26 | Pure re-grade; a miss is reported; judges only when P1 allows | §6, §9 |

## 3. Domain model (DM1–DM3)

**Bounded context:** *Judging*, inside Grading. It borrows cells, archives and grading passes; it owns judge
requests, verdicts, the verdict cache and calibration.

**Ubiquitous language** (spec terms first; new terms marked *new*):
- *Judge*: one stipulated (vendor, harness CLI, model) triple in `bench/gateway.yaml`.
- *Judge request* (*new*): the rendered, scrubbed text sent to one judge for one (artifact, rubric) pair.
- *Verdict set* (*new*): one judge's answer to one judge request: one verdict per rubric item.
- *Judge verdict* (spec `:208`): one judge's score on one rubric item for one artifact.
- *Judged score* (spec `:209`): the pair of verdicts on an item, plus the synthesized value (their mean), or
  NOT_RECORDED when they differ by more than one step.
- *Calibration item* (spec `:203`, R-58 DR-3): one (artifact, rubric item) pair with one human label.
- *Verdict use* (ADR-0006:70): one lookup of one judge's verdict on one rubric item for one cell, by one grading pass.

**Aggregates** (each bounded by one invariant; referenced by identity only):

| Aggregate | Root | The one invariant |
| --- | --- | --- |
| Verdict cache entry | the cache key | Immutable once written: the first writer wins and no process replaces an entry (ADR-0006:102). |
| Grading pass (existing) | `grading_id` | Single writer under `grade.lock`; its facts are sealed before `grading.completed` (ADR-0006:54). `verdict_uses` joins its facts. |
| Calibration set | `(task, rubric hash)` | No judge verdict on a calibration item exists before every item has its human label (R-58 c5, mechanized in §11). |
| Judge stipulation | `bench/gateway.yaml` content hash | Fixed before any verdict is cached; a change is a new catalog version (R-58 DR-1). |

Cells, archives and runs are referenced by `cell_id`, `archive_attempt` and `run_id`; nothing here writes them.

## 4. Durable representation (DM5–DM11)

Facts are append-only rows in the run's hash-chained ledger (ADR-0006); the cache is a content-addressed store outside
any run; κ, agreement and the vendor split are derived at report time and never stored.

### 4.1 `verdict_uses` (fact): grain re-declared (proposed ADR-0006 amendment; numbering at merge, W3-COST takes Amendment 2)

- **Grain:** one row is exactly one lookup of one judge's verdict on one rubric item for one cell, by one grading pass.
  It is recorded whether the lookup succeeded or not, so a miss is reported (US-26 c2) in the same fact.
- **Key:** `(run_id, grading_id, cell_id, item_id, judge)` (ADR-0006:70, unchanged). `item_id` is
  `<metric_id>#<n>`; `judge` is the stipulated model id.
- **Measures and attributes:**
  - `outcome` (non-additive enum): `hit` (read from the cache) · `stored` (called now, cached now) ·
    `not_allowed` (a miss without `--allow-model-calls`) · `unavailable` (CLI error, timeout, provider error) ·
    `invalid_output` · `model_mismatch` · `withheld` (the egress scan hit) · `over_bound` (artifact too large).
  - `cache_hit` of ADR-0006:70 is derived: `outcome == "hit"`. It is not a second column (DM7).
  - `cache_key` and `entry_sha256`: set only for `hit` and `stored`, else null. `entry_sha256` is the sha256 of the
    entry file's bytes when read; it is the tamper evidence of §9.4.
  - `flags` (list): `injection pattern` when the artifact matches the injection list (§10.3). Empty otherwise.
- **Additivity:** row counts per outcome are additive across cells and passes of one run; `outcome` itself is not.
- **History rule:** append-only; a re-grade is a new pass with new rows. Nothing is Type-1.
- **Writer:** the grading pass (`bench grade`), through `grade/judge.py`, into a sealed `verdict_uses` segment of
  its own. **Compute readers:** the synthesis (§10), the κ/agreement/vendor-split projections (§11, §12), and
  `bench verify` (the entry hash check, §9.4).
- **Migration:** additive. No run has `verdict_uses` rows today (`grep verdict_uses src/` is empty at `87606c6`). A
  pass written before this design has no such segment and reads as "no judged metric graded".

### 4.2 `model_calls`, principal `gateway` (R-58 c1; ADR-0006:66 Amendment 1 grain unchanged)

- One row is one model's usage in one native usage report of a judge CLI, read by one extraction. `principal` is
  `gateway`; `cell_id` is null (judge spend is overhead, never a cell's: spec US-17; ADR-0006 "coordinator overhead").
- The report comes from the judge call's own native record, read by the same readers the cells use
  (`telemetry/claude_code.py`, `telemetry/codex.py`). `native_session_id` ties the rows to the cache entry's provenance.
- **Usage source for the Claude judge:** `pending spike`. Under ACP the Claude record misses the final and
  auxiliary calls (`bench/profiles/claude-code.yaml` `usage_source: acp_turn`). In print mode the probe compares the
  record's usage with stdout's `usage`. If they differ, the gateway reads stdout's totals and records one row with
  `requests` = stdout `num_turns`; that is decided from the measurement, not assumed.
- A cache hit writes no row. A second pass with a warm cache writes none (R-58 c6).
- **Writer:** the grading pass, in the same `model_calls` segment it already writes. **Reader:** the header's judge
  spend line and `coordinator_overhead`.

### 4.3 The verdict cache (a content-addressed store; dimension-like, Type-2 by identity)

- **Grain:** one file is exactly one verdict set: one judge's validated answer to one judge request, served by the
  pinned model on one backend.
- **Path:** `cache/verdicts/<key>.json` (ADR-0006:102). `cache/` joins `.gitignore` (it is run state, like `runs/`).
- **Content:** `{format: "verdict-set/1", key, components: {request_sha256, rubric_sha256, artifact_sha256,
  oracle_sha256, template_version, schema_version}, judge: {vendor, harness, model}, served_models: [...],
  backend: {harness, version, exe_sha256, gateway_config_sha256}, native_session_id, created_utc, verdicts:
  [{item, score, rationale}]}`. No run id: an entry is shared by every run whose request is byte-equal.
- **Never cached:** any outcome other than a validated verdict set from the pinned served model.
- **Retention:** kept while any run references it (ADR-0006 "Retention"). Pruning makes those re-grades call again,
  and the run says so (`not_allowed` rows without the flag).

### 4.4 Calibration data (§11)

- `bench/calibration/C1/items/<id>.md` and `manifest.yaml` (W3-CAL): one synthetic artifact per file; the manifest
  names each item's rubric item and its provenance. **Grain:** one manifest row is exactly one calibration item.
- `bench/calibration/C1/labels.yaml` (the operator): **grain:** one row is exactly one human label of one calibration
  item: `{item, score, labelled_utc}`. Append-only in git history; a relabel is a new commit, disclosed.
- κ and agreement are derived at report time from labels + cache entries. Not stored.

## 5. The judge stipulation (R-58 DR-1, R-33)

`bench/gateway.yaml` (new, W3-GW-I):

```yaml
schema: bench-gateway/1
backend: headless-cli
judges:
  - { vendor: anthropic, harness: claude-code, model: <claude-fable-5-1 | claude-opus-5-5: pending spike> }
  - { vendor: openai,    harness: codex,       model: gpt-6-sol }
call_timeout_seconds: 300          # pending spike: set from the measured wall seconds per call
schema_mode: <text | native: pending spike>
```

- **Choice rule, applied once from the spike:** Fable if its probe turn qualifies (served = pin, 0 tool events,
  nothing but the credential read, the output contract met); else `claude-opus-5-5` if its turn qualifies; else no
  Anthropic judge qualifies and that is a decision request, never a silent substitute.
- **Fixed before any verdict is cached:** `bench/gateway.yaml` joins the `catalog_hash` recipe (R-59 c1:
  `task_version_hash`'s recipe over `bench/metrics.yaml`, `bench/rubrics/**` and now `bench/gateway.yaml`). A judge
  change therefore changes `catalog_hash`, and R-59 c1's frozen-fixture test fails unless `version` changes: the
  "model switch after a cached verdict is a new catalog version" rule has a control. **Seam request to W3-GRADE-CORE**
  (owns the recipe). Independently, the model id is in every cache key (§9.1), so an old entry is never reused.
- **Never passed:** `--fallback-model` (Claude Code 2.1.282 `--help` offers it; it would switch the judge silently,
  ADR-0009:60). A down judge is NOT_RECORDED; a re-grade fills it (spec `:614`).
- **Header:** names both stipulated ids and both served ids, from the pass's cache entries (§12).

## 6. When judges run (R-58 DR-2, c3; US-26 c2)

- **In-run pass** (`cli.py:163`, `runner.run_pass` called by `bench run`): never calls a judge. For every judged
  metric in the task's graders it writes `verdict_uses` rows `not_allowed` for cache misses and uses cache hits.
  A metric whose items are not all synthesized is NOT_RECORDED with reason `judge calls not allowed in this pass`.
  `assume:` the in-run pass may read cache hits. Confirm: R-58 DR-2 forbids calls, not reads; a hit is a lookup
  (ADR-0009:38). Breaks: if the Owner means "no judged value in-run at all", the in-run pass skips the lookup too
  (one line in `judge.py`), so the change is cheap either way.
- **`bench grade --allow-model-calls`** (the spec's flag, `:438`): the only path that calls a judge. Before any call
  it reads `status.build` for every run folder under `--runs` and **refuses with `HB-GRD-003`** when any run is live.
  "Live" is the status view's `liveness` in {`alive`, `stalled`} (the run lock is held, `status.py:3-5`, `:107`).
  See DR-GW-4 for why liveness, not the literal `phase == running`.
- **Without the flag:** a miss is `not_allowed`; the pass prints `judge misses: <n>` (US-26 c2).
- **Day hours** (R-58 DR-2) stay an operator rule. The code enforces the part that is checkable: no live run.
- **`--allow-model-calls` refuses on the in-run path**: `bench run` never passes it (it has no such flag).

## 7. The judge request

### 7.1 Inputs (US-35 c1)

- **Rubric:** `bench/rubrics/<metric>.md`, the catalog's authoritative copy (§13), verbatim.
- **Artifact:** the files the catalog entry's `artifact:` list names, read from the cell's archived working copy
  (`runs/<run>/archive/<cell>/attempt-<n>/ws/`). For C1: `docs/architecture.md` and `priority_queue.py`.
- **Oracle:** `pending decision` (DR-GW-2). Proposal: for C1 the rubric is the oracle (`tasks/C1/task.yaml`: "Judge
  rubric text is oracle/rubric.md"), and no reference file is sent.
- **Bounds:** each artifact file ≤ 64 KiB after decoding as UTF-8; else `over_bound`, NOT_RECORDED
  `artifact over the judge bound`. `simplify:` a fixed bound, no excerpting. Ceiling: C1's reference files are a few
  KiB. Upgrade trigger: a judged task whose artifact exceeds it.

### 7.2 Rendering and delimiting (US-46 c1)

- One template, `template_version` `judge-request/1`, in `gateway/templates/judge.md`. Order: instructions, rubric,
  then each artifact file as data, then the answer shape.
- Agent-derived text enters only between fences `<<<DATA <nonce> <path>>>` and `<<<END DATA <nonce>>>`. The nonce is
  the first 12 hex digits of the artifact's sha256, so the request stays deterministic for caching, and an agent
  cannot write a matching closing fence into content whose hash it does not know. A file containing the literal
  prefix `<<<END DATA` is rendered with that prefix escaped (`<<<END⁠DATA`), recorded as a flag.
- The rendered request's sha256 is `request_sha256`, the first key component.

### 7.3 Blinding scrub and scan (US-35 c1)

- **Denylist** (one function, one versioned list, `scrub_version`): every line of `bench/pack-markers.txt`; harness
  ids and names (`claude-code`, `Claude Code`, `codex`, `Codex`, `copilot`, `Copilot`, `GitHub Copilot`); every model
  id in `bench/prices.yaml` and the plan's combos; every combo id of the plan; model family words as whole words,
  case-insensitive (`Claude`, `GPT`, `Gemini`, `Grok`).
- **Scrub:** each hit in artifact text becomes `[redacted]`. The same token for every cell, so the replacement itself
  carries no signal. The rubric and template are operator text; `bench validate` fails if they contain a denylist
  entry.
- **Scan (the independent check):** after rendering, the gateway scans the whole request for every denylist entry.
  A hit means the scrub has a defect: the item is NOT_RECORDED with `HB-GW-004 blinding scan hit`, nothing is sent,
  and the pass continues.
- **What the CLI adds after the gateway:** the harness's own context (system prompt, environment block, skill
  listings) is outside this scan. The spike measures it per CLI: `reads.pack markers`, `reads.operator skills`,
  `context_kinds` in the probe summary. `pending spike`. If a CLI injects a pack marker or the operator's skills
  (N5 found Codex 0.156 reads `~/.agents/skills` whatever `CODEX_HOME` says), US-35 c1 fails for that judge, and
  DR-GW-1 goes to the Owner.

### 7.4 Egress (US-47, ADR-0005:36-41, ADR-0012:71,:85)

- The rendered request passes `egress.scan_and_send` (W3-EGRESS s1's module and the only path to the backend, by its
  import lint) before the CLI starts. A hit: `withheld`, NOT_RECORDED `withheld: sensitive content`, nothing sent;
  the egress module writes the `egress_events` row.
- **Identifiers the CLI adds** (the working folder path, a home path in a system prompt) are also outside the scan.
  Controls: the call's working folder and home live under the cells root, whose path has no user name
  (`plan.py:237`, default `<root>/../bench-cells`); the Claude judge gets `--system-prompt`, which replaces the default
  prompt that carries the working folder and environment. Measured: `reads.operator identifiers` per CLI.
  `pending spike`.

## 8. The call: the headless backend (ADR-0009:42, as amended by ADR-0013)

### 8.1 Launch shape

The probe's argv is the gateway's argv (`tests/fixtures/gateway/probe_judge.py` `claude_argv`, `codex_argv`). W3-GW-I
moves it into `gateway/backend.py` unchanged except for the fields the spike settles:

- **Claude Code 2.1.282:** `-p <request> --model <pin> --tools "" --strict-mcp-config --safe-mode
  --disable-slash-commands --permission-mode dontAsk --permission-prompts none --settings
  {"disableClaudeAiConnectors": true} --system-prompt <judge system prompt> --output-format json --session-id <uuid>`
  [`--json-schema <schema>`: `pending spike`]. Every flag was read from the pinned build's `--help` (2026-09-25).
- **Codex 0.156.0:** `exec -c model=<pin> -c approval_policy="never" -c web_search="disabled"
  -c project_doc_max_bytes=0 -c include_apply_patch_tool=false --disable <20 tool features> --ignore-user-config
  --ignore-rules --skip-git-repo-check -s read-only -C <work> --json -o <last message>` [`--output-schema <file>`:
  `pending spike`] `<request>`. The feature names were read from `codex.exe features list` on the pinned build.
  Two config keys are `assume:` markers in the probe (whether they exist on 0.156.0); the spike's canary and tool
  counts confirm or refute them.
- Neither CLI exposes a temperature (both `--help` outputs, Verified). The `judge.py` docstring's "temperature 0" is
  false for this backend; W3-GW-I corrects it. Determinism comes from the cache (US-26), not from sampling.

### 8.2 Process and home

- One fresh folder per call: `runs/<run>/grading/<grading_id>/gateway/<call_id>/{home,work}`. `call_id` is
  `<cell_id>-<metric>-<judge>`.
- The home gets only the credential copy (`profile.credential_source` → `home/<credential_name>`); no settings file,
  no config file. The copy is deleted in a `finally` (`profile.clean_home`), whatever the outcome. The native record
  stays, as a cell's does, for the extraction and the audit.
- The environment is `profile.cell_env(...)`: API keys, harness overrides and enclosing-session markers dropped
  (`profiles.py:28-31`). USERPROFILE/HOME: `pending spike` (the decoy profile of the probe; kept only if the turn
  authenticates with it and it changes what reaches the model).
- Spawned through `procs.run` in its own Job Object (ADR-0013; `procs.py:264`), with `call_timeout_seconds`.
- The executed build is re-hashed before the first call of a pass (`tools.resolve`, `tools.check_build` against
  `bench/gateway.yaml`'s recorded build): a changed build is `HB-CELL-115`-style refusal for the whole pass
  (`tools.py:45`), because the backend id is in every key.

### 8.3 Reading the answer

1. Served model: from the native record (`ModelCall.model`); every call must be the pin or a declared auxiliary
   (`profiles.model_allowed`, US-11). Else `model_mismatch`, `HB-GW-003`, not cached.
2. Final text: Claude stdout JSON `structured_output`, else `result`; Codex the `-o` file.
3. Parse as JSON and validate against `gateway/schemas/verdict-set.v1.json` with a closed-shape stdlib validator
   (no new dependency; `pyproject.toml` has none that validates JSON Schema). Exactly one verdict per rubric item,
   `score` in {0, 1, 2}, `rationale` a string ≤ 400 characters. Else `invalid_output`, `HB-GW-002`, not cached.
4. Tool events in the record must be 0 on every call, not only in the spike. A call with any tool event is
   `HB-GW-006 tool event in a judge call`, not cached, and the pass prints it: the qualification is re-checked on
   every call for free.

### 8.4 Qualification (R-58 c4) and re-qualification

- The backend qualifies per judge when its spike turn meets all four criteria (spike note). `pending spike`.
- Re-qualification is required when the pinned build changes (a new backend id), before any verdict from the new
  build is cached: the Leader re-runs the probe for that judge.
- The US-46 c2 injection fixture runs only through a qualified backend (R-60 c2), in EGRESS s2's live window.

## 9. The cache

### 9.1 Key (ADR-0006:102; R-58 c6)

`key = sha256(canonical({"request_sha256", "schema_sha256", "model", "backend"}))`, canonical as ADR-0006:49.
`backend` is `headless-cli/<harness>@<version>+<exe_sha256[:12]>/<gateway.yaml sha256[:12]>`.

ADR-0006 lists: artifact hash, rubric version, prompt-template version, output-schema version, model id, backend. The
request hash covers the first three (the rendered request contains the rubric, the artifact and the template), and
also the scrub version and the oracle, which the ADR's list misses. The entry keeps each component hash, so every
listed part stays inspectable. A conformance note, not a deviation; the Data & Persistence gate decides.

### 9.2 Create-if-absent write

Write the entry to `cache/verdicts/.<key>.<rand>.tmp`, flush, `os.fsync`, then `os.rename` to `<key>.json`. On
Windows `os.rename` fails when the target exists, so the first writer wins atomically. A loser deletes its tmp file
and uses the winner's entry (`outcome: hit`). A crash leaves only a `.tmp` file, which no reader opens.

### 9.3 Hit

Read, parse, check `format`, the key's components, and that `served_models` are allowed for the pin. Record
`entry_sha256`. Any mismatch is `HB-GW-005 cache entry invalid`: NOT_RECORDED, never overwritten.

### 9.4 Tamper evidence

The cache is plain files, writable by the operator's account, as are cells (ADR-0012). A pass that reads an entry
compares `entry_sha256` with every earlier `verdict_uses` row of the same run and key; a difference is `HB-GW-005`.
`bench verify` reports, as a warning, each `verdict_uses` key whose entry is missing or changed (pruned or edited).

## 10. Synthesis and scores

### 10.1 Per item (spec `:209`, US-35 c2)

| Verdicts | Item result |
| --- | --- |
| both recorded, `|a − b| ≤ 1` | synthesized value `(a + b) / 2`, a decimal string at scale 1 |
| both recorded, `|a − b| = 2` | NOT_RECORDED `judges disagree by 2 steps`; flagged; both verdicts shown |
| either not recorded | NOT_RECORDED with that judge's outcome as the reason |

### 10.2 Per metric (seam: W3-GRADE-D owns the metric definition)

Proposal for C1's rubric metric: the value is Σ synthesized item values (0–14, scale 1) when all 7 items are
synthesized; otherwise NOT_RECORDED naming the items (US-27: NA, never a partial sum as if complete). Every other
judged metric on every task is NOT_RECORDED `no rubric for this task` (R-59 c2).

### 10.3 Injection flag (US-46 c2)

A pure function over the artifact text flags known injection patterns (`ignore (the|all|any|previous) (rubric|
instructions)`, `score (this|it)? ?\d+`, `you are (now )?the (judge|grader)`). The flag goes on every `verdict_uses`
row of that cell and metric, and on the report's item view. The flag never changes a score. The ≤ 1 step criterion is
measured by EGRESS s2's live fixture run, through the qualified backend.

## 11. Calibration and κ (R-58 DR-3, c5; spec US-35 c3)

- **Unit:** one calibration item = one (artifact, rubric item) pair = one human label (spec `:208`). 30 items = 30
  labels. Coverage (R-58 c5): all 7 rubric items, ≥ 4 each, and the 0/1/2 range; W3-CAL authors, the operator labels.
- **Request shape:** a calibration item is judged with the same template and the full rubric as a cell; the verdict
  on its labelled item is the one compared. So calibration measures the production prompt, not a variant.
- **Label before verdict (mechanized):** `tools/calibrate.py` refuses with `HB-CAL-001` while `labels.yaml` has fewer
  labels than `manifest.yaml` has items. No calibration verdict can exist before every label does. Items are
  synthetic, never a cell artifact (R-58 c5).
- **Where calibration's spend goes:** `tools/calibrate.py` writes its own hash-chained ledger,
  `runs/calibration-C1-<rubric_sha256[:8]>/` (`events` `calibration.started`/`completed`, `model_calls` principal
  `gateway`), with the existing `ledger.SegmentWriter`. No scores, no `verdict_uses`: its verdicts are cache entries.
  `simplify:` a separate ledger, not a run. Upgrade trigger: a second calibrated rubric.
- **κ:** Cohen's κ, unweighted, over categories {0, 1, 2}: `κ = (p_o − p_e) / (1 − p_e)`, `p_e = Σ_k p1(k) · p2(k)`.
  Non-additive; a decimal string at scale 3. When `p_e = 1` (one category only), κ is NOT_RECORDED
  `kappa undefined: one category`. Reported with n and exact agreement. No threshold (the spec cut it, `:1173`).
- **Human half:** each judge vs the labels, κ and exact agreement. `not recorded: labels pending` until
  `labels.yaml` is complete. US-35 c3 stays open as a named wave-4 row until then (R-58 DR-3).
- **Disclosure (R-62 a3):** "Calibration items were written by `claude-opus-5-5`; the Anthropic judge is a Claude
  model." In the header's About text.

## 12. The header's judge block (report `header` section; W3-GW-I owns the hunk)

| Row | Content | Source |
| --- | --- | --- |
| Judges | both stipulated ids, both served ids, backend and build | `bench/gateway.yaml`, cache entries of the current pass |
| Calibration | n; inter-judge κ; each judge's κ and exact agreement vs the labels, or `not recorded: labels pending` | labels + cache |
| Agreement on this run | items judged; exact; within one step; disagreements (NOT_RECORDED) | `verdict_uses` + cache |
| Verdict split by cell vendor (R-58 c2) | mean (Claude verdict − GPT verdict) per cell vendor, with n; "disclosed, not a gate" | as above, joined to the plan's combos |
| Judge spend | tokens by judge | `model_calls` principal `gateway` |
| Probe versions | a `.dev` catalog is a `probe pass` (R-59 DR-4) | `grading.started` |

The vendor split's cell vendor comes from the plan's combo model id (`claude-*` → Anthropic, `gpt-*` → OpenAI).
C1 wave 3: 2 Anthropic cells and 4 OpenAI cells (plan version 5: copilot-sol, codex-sol are `gpt-6-sol`), so n is
14 and 28 items.

## 13. C1's rubric in the catalog (R-59 DR-5, c2)

- `bench/rubrics/<metric>.md` is the authoritative rubric. `<metric>` is the id W3-GRADE-D names (R-59 c2). **Seam
  request to W3-GRADE-D:** the id, and whether a C1-specific rubric under a generic id is acceptable.
- The catalog entry gains `rubric: bench/rubrics/<metric>.md`, `artifact: [docs/architecture.md, priority_queue.py]`,
  `tasks: [C1]`. Any other task with `judge` in `graders` gets NOT_RECORDED `no rubric for this task`.
- `bench validate` asserts `tasks/C1/oracle/rubric.md` is byte-equal to `bench/rubrics/<metric>.md` (the spec `:255`
  equality-test pattern). C1's file becomes a pointer at C1's next task version, never in wave 3 (R-59 c5).
- **Conflict found:** R-59 c2 asks the rubric's preamble to state why no mechanical oracle applies, but DR-5 keeps the
  file byte-identical to C1's frozen copy and c5 freezes `tasks/C1/`. The preamble cannot change in wave 3. DR-GW-3.

## 14. The matcher's model rung (contract only; GR-CLAR sizes it)

The gateway's second request kind, `match(question, clarifications) → {clarification_id | none}`, uses the same
backend, cache and egress path with its own template, schema and `matcher_version` in the key (R-53: the match key is
(question hash, clarification set)). Its qualification is the Leader's held-out run (US-31 c2, T = 0.80). The hunk in
`clarify.py` is serial after W3-GR-CLAR (plan version 5).

## 15. Change-surface list (E7)

| Surface | Change | Owner |
| --- | --- | --- |
| store | `cache/verdicts/`; `.gitignore` gains `cache/` | GW-I |
| store | `verdict_uses` segment per pass; `model_calls` rows principal `gateway` | GW-I via GRADE-CORE's runner (seam) |
| store | `runs/calibration-C1-<hash>/` ledger | GW-I |
| config | `bench/gateway.yaml`; `bench/rubrics/<metric>.md`; catalog entry fields | GW-I; id from GRADE-D |
| model | `VerdictSet`, `VerdictUse`, `JudgeRequest` dataclasses | GW-I |
| service | `gateway/` (request, scrub, backend, cache), `grade/judge.py` | GW-I |
| hash | `catalog_hash` covers `bench/gateway.yaml` | GRADE-CORE (seam) |
| CLI | `bench grade --allow-model-calls`, `HB-GRD-003` | GW-I after STOP-I joins |
| validate | rubric byte-equality; rubric/template contain no denylist entry | GW-I |
| projection | κ, agreement, vendor split, judge spend | GW-I (`views` functions) |
| UI | the header's judge block; the item view with both verdicts and flags | GW-I (`report/html.py` hunk) |
| compute reader | C1 metric aggregation (§10.2) | GRADE-D / GRADE-CORE |
| verify | missing or changed cache entries: warning | GW-I |

## 16. Slice plan for W3-GW-I (Codex `gpt-6-sol`, ≤ 6 slices, red first)

| Slice | Content | Proof |
| --- | --- | --- |
| s1 | Request rendering, fences, scrub + scan, closed-shape schema validator, cache key and create-if-absent store, all behind a `Backend` protocol with a fake | unit + property tests; the concurrent-writer test; no process spawned |
| s2 | Headless backend: argv from the probe, per-call home, credential deletion, `procs.run`, served-model check, tool-event check, `model_calls` principal `gateway` | contract tests on the spike's native records, scrubbed into `tests/fixtures/gateway/records/` |
| s3 | `grade/judge.py`: lookups, `verdict_uses` rows and outcomes, synthesis, NA reasons, injection flag; wired through GRADE-CORE's dispatch | a fake-backend pass over a fixture archive; the warm re-grade makes 0 backend calls |
| s4 | `--allow-model-calls` and `HB-GRD-003` (after STOP-I joins); in-run NA | a fixture run folder with a held lock refuses |
| s5 | `tools/calibrate.py`, κ, the header block, the rubric in the catalog, `bench validate` checks | κ tests on hand-computed tables; the header renders `not recorded` states |
| s6 | the `clarify.py` model-rung hunk after GR-CLAR | GR-CLAR's fixtures |

Live turns (the calibration run, the judge pass, EGRESS s2's fixture) stay the Leader's.

## 17. Error and concurrency model

- **Codes (new):** `HB-GRD-003` live run, refusing model calls · `HB-GW-001` judge unavailable (CLI error, timeout,
  provider error) · `HB-GW-002` invalid output · `HB-GW-003` served model not the pin · `HB-GW-004` blinding scan hit ·
  `HB-GW-005` cache entry invalid or changed · `HB-GW-006` tool event in a judge call · `HB-CAL-001` labels incomplete.
- **No retry.** A failed call is NOT_RECORDED and a later re-grade fills it (spec `:614`). `simplify:` no retry.
  Upgrade trigger: more than 5 % of calls in a pass end `unavailable`.
- **Serial calls.** One judge call at a time per pass. `simplify:` parallelism 1. Ceiling: C1 is 12 calls per pass,
  60 for calibration. Upgrade trigger: a pass's judge wall time over 30 minutes.
- **Concurrency across passes:** `grade.lock` is per run; two runs' passes can race on one key; §9.2 resolves it.

## 18. Failure-mode analysis

| Failure mode | From which choice | Disposition | How | Detection | Test |
| --- | --- | --- | --- | --- | --- |
| CLI serves a different model | headless CLI, subscription account | detect + prevent caching | §8.3 step 1 | `HB-GW-003`; `model_mismatch` rows | T-GW-07 |
| Judge advertises or calls a tool | headless coding CLI | prevent + detect | §8.1 flags; §8.3 step 4 on every call | `HB-GW-006`; spike | T-GW-08; spike |
| Answer not JSON / wrong shape | free-text CLI output | detect | closed-shape validator | `HB-GW-002` | T-GW-05 |
| Judge down, rate-limited, slow | vendor dependency | degrade | NOT_RECORDED; re-grade fills | `HB-GW-001` | T-GW-09 |
| Call hangs | subprocess | mitigate | `procs.run` timeout, Job Object kill | `unavailable` row | T-GW-09 |
| Credential copy left behind | per-call home | prevent | `finally: clean_home` | test asserts absence | T-GW-10 |
| Two passes write one key | shared cache | prevent | rename-no-overwrite | loser reads `hit` | T-GW-11 |
| Crash mid-write | shared cache | prevent | tmp + fsync + rename | `.tmp` ignored | T-GW-11 |
| Cache entry edited or pruned | plain files | detect | §9.4 | `HB-GW-005`; `verify` warning | T-GW-13 |
| Judge switched after verdicts cached | stipulation file | prevent | `catalog_hash` covers `gateway.yaml`; key has model | R-59 c1 test fails | T-GW-14 |
| Build bump changes judge context | pinned CLI | prevent | backend id in key; build re-check | refusal | T-GW-15 |
| A run starts during a judge pass | operator timing | accept | checked once at pass start; R-9 rule 1 procedure covers the rest. Residual: a run started mid-pass shares the account for up to the pass's length | pass start/end in `events`, run start in its ledger | — |
| Blinding leak via artifact | scrub | prevent + detect | scrub, then scan | `HB-GW-004` | T-GW-03, T-GW-04 |
| Blinding leak via CLI context | harness adds context | detect | the spike; DR-GW-1 | spike summary | spike |
| Scores differ across re-grades | model non-determinism | prevent | cache: a re-grade reads, never calls | export hash equal | T-GW-12 |
| Calibration labelled after verdicts | order | prevent | `HB-CAL-001` | refusal | T-GW-16 |
| κ undefined | one category | degrade | NOT_RECORDED with reason | header text | T-GW-17 |
| Artifact too large | bound | degrade | `over_bound` | row | T-GW-06 |

## 19. Adversarial analysis (STRIDE-lite)

| Trust boundary | STRIDE threat | Disposition | Control / rationale | Negative test |
| --- | --- | --- | --- | --- |
| Cell artifact → judge request | T/E: prompt injection steers the verdict or a tool | mitigate | no tools (§8.1, checked per call §8.3), fenced data (§7.2), schema, ±1 step check (US-46 c2), injection flag | T-GW-08; fence-escape test T-GW-02; EGRESS s2 live fixture |
| Cell artifact → judge request | I: artifact carries a secret or the operator's identifiers | mitigate | egress scan before send (W3-EGRESS) | T-GW-18 (canary artifact → `withheld`, fake backend receives nothing) |
| Cell artifact → judge request | I: identity of harness/model/pack leaks to the judge (bias) | mitigate | scrub + scan (§7.3) | T-GW-03, T-GW-04 |
| Gateway → CLI process | I: credential exposure | mitigate | copy in a per-call home, deleted in `finally`; env scrubbed (`profiles.py:28-31`); never an API key | T-GW-10; env test |
| Gateway → CLI process | S: a different binary runs | mitigate | exe re-hash vs the recorded build (`tools.check_build`) | T-GW-15 |
| CLI → vendor | I: the CLI adds the operator's paths, skills or pack markers | detect; DR if present | the spike; cells-root paths; `--system-prompt` | spike |
| Vendor → verdict | T: malformed or oversized answer | mitigate | closed-shape validator, rationale ≤ 400 chars | T-GW-05 |
| Cache store | T: an entry edited between passes | detect | entry hash vs earlier uses; `verify` | T-GW-13 |
| Cache store | R: which call produced a verdict | mitigate | entry provenance (served model, build, native session id); record kept under the pass | T-GW-07 |
| `bench grade --allow-model-calls` | E/D: model calls during a live run (account confound, R-9) | mitigate | `HB-GRD-003` from the status view | T-GW-19 |
| Calibration | T: labels shaped by seeing verdicts | mitigate | `HB-CAL-001` order control | T-GW-16 |

## 20. Privacy analysis (LINDDUN-lite)

| Data flow / category | LINDDUN finding | Disposition | Control / rationale | Retention & rights path |
| --- | --- | --- | --- | --- |
| Artifact text → vendor | D: an agent wrote the operator's e-mail, user name or home path into an artifact | mitigate | US-47 scan; `withheld` | Nothing is sent; the local archive follows `runs/` retention (P1 deletes) |
| CLI context → vendor | D/I: the CLI adds the working folder path or user-level files | detect; DR if present | cells-root paths; the spike measures | — |
| Judge calls → vendor account | L/I: calls are linked to the operator's subscription | accept | ADR-0009 accepted it (subscriptions only); recorded as the backend | Vendor retention per the operator's plan |
| Calibration labels | I: the operator's judgements, committed | accept | labels are scores, no personal data beyond authorship | git history; the operator can remove the file |

## 21. Telemetry

The bench's telemetry is its ledger (ADR-0006; ADR-0008). Every question an operator asks has an emitting row:

| Question | Source |
| --- | --- |
| How many judge lookups, and how did each end? | `verdict_uses.outcome` |
| Which calls happened, how long, how many tokens? | `model_calls` principal `gateway` (start/end, tokens) |
| Which model answered? | cache entry `served_models`; `model_calls.model` |
| What was sent, and was it withheld? | `egress_events` (payload hash, destination, result) |
| Was the request blinded? | `HB-GW-004` count; the scrub version in the entry |
| Why is a judged score missing? | the `scores` reason; the item's outcome |
| Calibration state | labels count vs items; κ or `not recorded` |

`bench grade` prints one line per outcome kind with its count. No new OpenTelemetry surface: the bench has none
(ADR-0008); a gap is not recorded, never a plausible number.

## 22. Test plan (Testing Strategy: D0 plus the triggered directives)

Triggers: pure functions (scrub, render, key, synthesis, κ): unit and property tests. Parsers of untrusted input
(the CLI's output, the native record, cache entries): boundary and negative tests. A process boundary: contract tests
on recorded native files. Concurrency (shared cache): a race test. Security controls: negative security tests.
Persistence (a new fact): an append-only test and a golden-ledger regression. Mutation testing:
`tests/mutations/gateway.json`.

| Id | Promise | Test |
| --- | --- | --- |
| T-GW-01 | render is deterministic | same inputs → same bytes; property over random artifacts |
| T-GW-02 | data cannot close its fence | an artifact containing `<<<END DATA` is escaped and flagged |
| T-GW-03 | scrub removes every denylist entry | property: random text with planted entries → none remain; idempotent |
| T-GW-04 | the scan is independent | a scrub stub that leaves one entry → `HB-GW-004`, the fake backend receives nothing |
| T-GW-05 | output validation | valid set passes; missing item, extra key, score 3, bool score, duplicate item, long rationale fail |
| T-GW-06 | bound | a 65 KiB file → `over_bound` |
| T-GW-07 | served-model check | a native record serving another model → `model_mismatch`, no entry |
| T-GW-08 | tool events fail a call | a native record with one `tool_use` → `HB-GW-006`, no entry |
| T-GW-09 | unavailable | fake backend timeout and provider error → NOT_RECORDED, no entry |
| T-GW-10 | credential deleted | after success, error and timeout, the copy is absent |
| T-GW-11 | create-if-absent | two writers race on one key: one file; a leftover `.tmp` is ignored |
| T-GW-12 | warm re-grade makes 0 backend calls (R-58 c6) | a counting fake backend: pass 2 count is 0; `views.export` bytes equal |
| T-GW-13 | tamper evidence | edit an entry between passes → `HB-GW-005`; `verify` warns |
| T-GW-14 | judge switch is a catalog change | change `gateway.yaml` → `catalog_hash` changes; R-59 c1 test red without a version bump |
| T-GW-15 | build change | another exe hash → refusal before any call |
| T-GW-16 | labels before verdicts | 29 labels for 30 items → `HB-CAL-001`, no backend call |
| T-GW-17 | κ | hand-computed tables: identical → 1; independent → ≈ 0; one category → NOT_RECORDED |
| T-GW-18 | egress | a planted canary → `withheld`; the fake backend receives nothing (with W3-EGRESS) |
| T-GW-19 | live-run refusal | a run folder with a held lock → `HB-GRD-003` before any call |
| T-GW-20 | synthesis table | every (a, b) in {0,1,2}²: mean, or NOT_RECORDED at distance 2 |
| T-GW-21 | append-only `verdict_uses` | an attempted rewrite fails `bench verify` |
| T-GW-22 | NA reasons | in-run pass: `judge calls not allowed in this pass`; other tasks: `no rubric for this task` |
| T-GW-23 | rubric equality | a one-byte change in either copy fails `bench validate` |

## 23. Conformance notes

- LOA: AI Gateway + Read-Through cache + Guardrail Filter (LOA 6.2), as ADR-0009:34 names; Self-Consistency across
  providers (LOA 3.5) with the calibration set as verifier (ADR-0009:47).
- Reuse (Solution-Selection Ladder): the cell profiles, readers, `procs.run`, `ledger.SegmentWriter`, `status.build`,
  `task_version_hash`'s recipe. No new dependency.
- Conformance note: the cache key hashes the rendered request (§9.1), which covers ADR-0006:102's list and more.

## 24. Decision requests and seam requests

- **DR-GW-1 (conditional on the spike):** if a judge CLI injects a pack marker or the operator's skill listing into
  its own context (Codex and `~/.agents/skills`, N5), US-35 c1 fails for that judge. Options: accept and disclose;
  run that judge under a separate OS user profile; or drop to one judge for the wave. `pending spike`.
- **DR-GW-2:** what "the oracle" in the judge input is for C1 (US-35 c1). Proposal: the rubric (C1's `task.yaml`
  calls it the judge's oracle); no reference file is sent, because the rubric scores against the submitted code.
- **DR-GW-3:** R-59 c2 wants the rubric preamble to state why no mechanical oracle applies; DR-5 and c5 freeze the
  file. Proposal: the catalog entry's `note:` carries that sentence in wave 3; the rubric file gains it at C1's next
  task version.
- **DR-GW-4:** R-58 c3 says "phase `running`". A crashed run keeps its last phase but its lock is free, so a
  phase-only check would refuse forever. Proposal: refuse when any run's `liveness` is `alive` or `stalled`.
- **Seam requests:** W3-GRADE-CORE: `bench/gateway.yaml` in `catalog_hash`; `verdict_uses` in the pass's facts.
  W3-GRADE-D: the C1 metric id and its aggregation (§10.2). W3-COST: the ADR-0006 amendment number. W2-STOP-I: the
  `cmd_grade` flag.

## 25. Flagged risks and residual unknowns

- `pending spike`: whether 2.1.282 serves Fable; tool events; reads beyond the credential; system prompt in record;
  record-vs-stdout usage; prompt intact on the command line; the native schema flags; wall seconds per call.
- ADR-0009:23 says ADR-0013 amends it, but ADR-0013 has no gateway text (a one-sided link). Inferred: the native
  process + Job Object model applies; this design follows it (§8.2).
- n is small: 42 items per pass, 30 calibration items. κ and the vendor split are disclosed with n, never gated.
- Self-preference is measured, not removed (R-58 DR-1): 4 of 6 C1 cells are `gpt-6-sol`.

## 26. Status

| | |
| --- | --- |
| **Completed** | Phase A: the probe, its offline self-test (39 checks, exit 0), the spike note's method and commands, this draft |
| **Remaining** | The Leader's five probe turns; phase B: results into the spike note, the `pending spike` fields filled, the five-persona gate, the decision requests |
| **Best next action** | The Leader runs the five probe commands in `docs/notes/spike-gw-headless.md` |

## 27. Gate record

`pending (phase B)`.

---
**Handoff:** → `/implement` (W3-GW-I) after the gate.
