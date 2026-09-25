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
  Row 17 per R-58 and R-59, driven by spike GW-H and revised through a five-persona gate. The gateway calls judges
  through the pinned headless CLIs, from call folders under the cells root, only under bench grade
  --allow-model-calls and never while any run is live. The Anthropic judge is claude-fable-5-1 (served on 2.1.282,
  text output, 0 tool events). The OpenAI judge gpt-6-sol is not qualified and is never spawned: Codex 0.156 keeps its
  code-mode exec tool (DR-GW-1). Requests are scrubbed, scanned, egress-checked and sent on stdin; answers are
  schema-validated; verdicts live in a request-keyed memo store whose hits are checked against the storing ledger.
  Calibration is one human label per (artifact, rubric item), set-checked before any verdict. The gate passed in
  two rounds, with every veto cleared by its holder. Five Owner decisions are open.
review-suggested: []
---

# Design: the model gateway and the two judges (phase 3, row 17)

- **Status:** Gate passed (revision 3). Every measured fact comes from spike GW-H:
  `docs/notes/spike-gw-headless.md`, five Leader-run turns on 2026-09-25, and
  `tests/fixtures/gateway/gw-headless-results.json`.
  - Round 1 had three hard vetoes and a soft block. In round 2 all five reviewers cleared, four of them with
    conditions, which are applied (§27).
  - Five decision requests are open for the Owner (§24).
  - No live judge pass runs before DR-GW-5 is ruled and the stdin/cells-root re-probe is done.
- **Spec / architecture:**
  - `docs/specs/harness-bench.md`: US-25, US-26, US-31, US-35, US-46 and US-47, plus the judged-score and calibration
    terms (`:203`, `:208-209`).
  - ADRs: ADR-0009 (the gateway), ADR-0006 (facts, cache), ADR-0005 (egress), ADR-0012 (US-47 scope),
    ADR-0013 (native processes).
  - Rulings R-58..R-62.
- **Delivery phase:** wave 3, row 17. W3-GW-I (Codex `gpt-6-sol`) builds it in six slices (§16). The judged scope is
  C1: 6 smoke cells × 7 rubric items (plan version 5).
- **Author:** W3-GW-D (Claude `claude-opus-5-5`), paired with the AI Systems Engineer lens.

## 1. Responsibility

The gateway is the one place where the bench itself calls a model (ADR-0009:34). This design covers its judge path:
- build a blinded, scanned, delimited request;
- call each stipulated, qualified judge through its headless CLI with no tools;
- validate the answer, cache it, and record every lookup.

It also covers calibration (κ) and the header's judge block.

Not in this design:
- the AI summaries (phase 4, ADR-0009:44);
- the matcher's model rung, which W3-GR-CLAR designs (§14);
- per-metric definitions and aggregation, which W3-GRADE-D owns (R-59 c2);
- the egress scanner, which W3-EGRESS owns (R-60).

## 2. Rulings and promises bound here

| Source | Clause | Where it lands |
| --- | --- | --- |
| R-58 DR-1 | Jury `claude-fable-5-1` + `gpt-6-sol`; fallback `claude-opus-5-5`; fixed and named before any verdict is cached; a switch after is a new catalog version | §5 |
| R-58 DR-2, c3 | Never in-run; only `bench grade --allow-model-calls`; refuse while a run is live | §6 |
| R-58 DR-3, c5 | κ inter-judge plus each judge vs the operator's labels; human half `not recorded` until labelled; 30 items = 30 labels; labels before any verdict | §11 |
| R-58 c1 | `model_calls` principal `gateway`; US-11 pin check on judges; the header names both served ids | §4.2, §8.3, §12 |
| R-58 c2 | Header: mean (Claude − GPT) by cell vendor, with n; disclosed, never a gate | §12 |
| R-58 c4 | US-46 "run a command" fixture: 0 tool calls per vendor | spike note; §8.4 |
| R-58 c6 | A second pass makes 0 backend calls; the key carries model id and backend | §9.1; T-GW-12, T-GW-12b |
| R-59 DR-5, c2 | `bench/rubrics/<metric>.md`; C1's `oracle/rubric.md` byte-identical; NA `no rubric for this task` | §13 |
| R-59 c1 | `catalog_hash` on `grading.started` | §5 (each judge's entry joins the hash; seam) |
| R-60 c2 | The injection fixture goes only to a qualified backend | §8.4 |
| R-62 a3 | Disclose Claude-authored calibration items judged by a Claude judge | §11, §12 |
| US-35 c1 | Rubric + artifact + oracle; scrubbed; a scan of the captured request finds none | §7.3; DR-GW-5 |
| US-35 c2 | > 1 step apart: NOT_RECORDED, flagged, both verdicts shown | §10 |
| US-46 c1 | No tools, no file or shell access; schema-constrained; agent text only as delimited data | §7, §8 |
| US-46 c2 | Injection fixture: ≤ 1 step difference; the item is flagged | §10.3 |
| US-47 | Scan before every judge send; a hit is `withheld: sensitive content` | §7.4 |
| US-26 | Pure re-grade; a miss is reported; judges only when P1 allows | §6, §9 |

## 3. Domain model (DM1–DM3)

**Bounded context:** *Judging*, inside Grading. It borrows cells, archives and grading passes. It owns judge
requests, verdicts, the verdict store and calibration.

**Ubiquitous language** (spec terms first; new terms marked *new*):
- *Judge*: one entry of `bench/gateway.yaml`: vendor, harness CLI, model, output mode, build pin, `qualified`.
- *Judge request* (*new*): the rendered, scrubbed text sent to one judge for one (artifact, rubric) pair.
- *Judge call* (*new*): one spawn of one judge CLI for one judge request.
- *Verdict set* (*new*): one judge's validated answer to one judge request, with one verdict per rubric item.
- *Judge verdict* (spec `:208`): one judge's score on one rubric item for one artifact.
- *Judged score* (spec `:209`): the pair of verdicts on an item, plus their mean. It is NOT_RECORDED when the two
  verdicts are more than one step apart.
- *Calibration item* (spec `:203`, R-58 DR-3): one (artifact, rubric item) pair with one human label.
- *Verdict use* (ADR-0006:70): one lookup of one judge's verdict on one rubric item for one cell, by one grading pass.

**Aggregates** (each bounded by one invariant; referenced by identity only):

| Aggregate | Root | The one invariant |
| --- | --- | --- |
| Verdict store entry | the key | Written once and never replaced. A hit is accepted only when the storing ledger's row has the same `entry_sha256` (§9.3). |
| Grading pass (existing) | `grading_id` | Single writer under `grade.lock`; facts sealed before `grading.completed` (ADR-0006:54). `verdict_uses` joins its facts. |
| Calibration set | `(task, rubric sha256)` | No judge verdict on a calibration item exists unless the set of labelled item ids equals the set of manifest item ids, with no duplicate and no unknown id (R-58 c5; §11). |
| Judge stipulation | one `gateway.yaml` judge entry | Fixed before any of its verdicts is stored. A change is a new catalog version (R-58 DR-1). An unqualified judge is never spawned (§8.4). |

Cells, archives and runs are referenced by `cell_id`, `archive_attempt` and `run_id`; nothing here writes them.

## 4. Durable representation (DM5–DM11)

Facts are append-only rows in hash-chained ledgers (ADR-0006). The verdict store is a request-keyed memo store outside
any run. It is not content-addressed: the file name hashes the request, not the entry. κ, agreement, the vendor
split, the injection flag and the CLI-added context classes are derived at report time and never stored.

### 4.1 `verdict_uses` (fact): the text of the proposed ADR-0006 amendment

W3-GW-I lands this text in ADR-0006 as the next amendment. W3-COST takes Amendment 2, so the number is assigned at
merge.

- **Grain:** one row is exactly one lookup of one judge's verdict on one rubric item for one cell, by one grading pass.
  Failed lookups get a row too, so a miss is reported (US-26 c2).
- **Key:** `(run_id, grading_id, cell_id, item_id, judge_or_matcher)` (ADR-0006:70, the column name kept, so a
  matcher row fits the same key). `item_id` is `<metric_id>#<n>`. `judge_or_matcher` is the judge's model id.
- **Attributes:**
  - `outcome`, a closed enum with 5 values:
    - `hit`: read from the store, no call;
    - `stored`: called now, the entry written now;
    - `race_lost`: called now; another writer's entry was used;
    - `not_allowed`: a miss without `--allow-model-calls`;
    - `failed`: NOT_RECORDED.
  - `code`: the HB code of a `failed` row (§17), null otherwise. Precedence when several apply is the order of the
    §8 pipeline: the first failing step is the one recorded. Every NOT_RECORDED path in §6–§9 maps to exactly one
    `(outcome, code)` (T-GW-30).
  - `cache_key` and `entry_sha256`: set for `hit`, `stored` and `race_lost`; null otherwise.
  - `cache_hit` of ADR-0006:70 is derived: `outcome == "hit"`. It is not a column (DM7).
- **Additivity and the call grain:** rows are items. One judge call yields 7 rows (C1). A call-level quantity (calls,
  misses, failures) is counted over distinct `(cell_id, metric_id, judge_or_matcher)` within a pass, by one compute
  reader, `views.judge_calls`. A guard test asserts that no view counts `verdict_uses` rows as calls. This is the same
  rule as Amendment 1's "a row count is not a call count" (ADR-0006:84).
- **History rule:** append-only. A re-grade is a new pass with new rows.
- **Writer:** the grading pass (`bench grade --allow-model-calls`, or a cache-only `bench grade`), through
  `grade/judge.py`, into its own sealed `verdict_uses` segment. The in-run pass writes none (§6).
  **Compute readers:** synthesis (§10), the κ/agreement/vendor-split projections (§11, §12), `views.judge_calls`, and
  `bench verify` (store entries still present and unchanged).
- **Migration:** additive. No ledger has `verdict_uses` today; `grep` of `src/` finds no `verdict_uses` on `main` at
  `490c047`. A pass without the segment reads as "judged metrics not graded". No backfill, no rewrite, no rollback
  needed.
- **Code lists that must name the fact:** `views.FACTS` and `views.KEYS` (`views.py:49-56`), and
  `runner.PASS_FACTS` (`runner.py:33`). All three are seams with W3-GRADE-CORE.

### 4.2 `model_calls`, principal `gateway` (R-58 c1; ADR-0006:66 Amendment 1 grain unchanged)

- **Grain:** one row is one model's usage in one native usage report of a judge CLI, read by one extraction.
  `principal` is `gateway`. `cell_id` is null, because judge spend is overhead (US-17).
- **Source:** the judge call's own native record, archived into the pass (§8.2), read by the cells' own readers.
- **Usage source: the native record for both judges** (Verified, spike GW-H). Claude's print-mode record equals its
  stdout `usage` on all three turns. Codex's two calls sum to stdout's `turn.completed`.
- `stored` and `race_lost` rows come from a call, so that call's `model_calls` rows are written. `hit`,
  `not_allowed` and pre-spawn `failed` rows made no call and write no `model_calls` row. A warm second pass writes
  none (R-58 c6; T-GW-28).
- **Writer:** the grading pass. **Readers:** the header's judge spend, `coordinator_overhead`.

### 4.3 The verdict store (request-keyed memo store, Type-2 by identity)

- **Grain:** one file is exactly one verdict set: one judge's validated answer to one judge request, served by the
  pinned model on one invocation.
- **Path:** `cache/verdicts/<key>.json` (ADR-0006:102). `cache/` joins `.gitignore`. An entry is made read-only after
  it is written.
- **Content:**
  - `format: "verdict-set/1"`;
  - `key_inputs`: exactly the four inputs of the key (§9.1), so the key can be recomputed from the entry (T-GW-31);
  - `components`: the component hashes and versions, for inspection:
    - `artifact_sha256`: of the raw archived bytes, before the scrub;
    - `rubric_sha256`, `template_version`, `scrub_version`, `schema_sha256`;
  - `served_models`;
  - `stored_by`: `{ledger: "run" | "calibration", ledger_id, grading_or_calibration_id}`;
  - `native_session_id`, `created_utc`;
  - `verdicts: [{item, score, rationale}]`.
- **Never stored:** any outcome other than a validated verdict set from the pinned served model with 0 tool events.
- **Retention:** kept while any ledger references it (ADR-0006). Pruning makes those re-grades miss, and the pass
  says so.

### 4.4 Calibration data (§11)

- `bench/calibration/C1/items/<id>.md` and `manifest.yaml` (W3-CAL). **Grain:** one manifest row is one calibration
  item: `{id, rubric_item, sha256, author_model, authored_utc}`.
- `bench/calibration/C1/labels.yaml` (the operator). **Grain:** one row is one human label of one item:
  `{id, score, labelled_utc}`. Git history keeps every version.
- **The calibration ledger:** `runs/calibration-C1-<rubric_sha256[:8]>/`, written with `ledger.SegmentWriter`. It
  holds:
  - `events` `calibration.started` (with `labels_sha256`, `manifest_sha256`, the judge entries and the key inputs'
    versions) and `calibration.completed`;
  - `model_calls` (principal `gateway`);
  - `calibration_uses`: **grain:** one row is one lookup of one judge's verdict set for one calibration item, by one
    calibration pass. **Key:** `(calibration_id, item_id, judge_or_matcher)`. It has the same `outcome` and `code`
    enum as `verdict_uses`, plus `cache_key` and `entry_sha256`. It stays a separate fact because its subject is a
    calibration item, not a cell of a run (the Simplifier noted a merge; D&P holds the choice).

  It has no `plan.json`, so `status.require_known` (`status.py:85-89`) treats it as "not a run". Every run scan
  filters with that one predicate (T-GW-19c).
- **κ and agreement are derived from the calibration ledger's recorded rows plus the labels file whose sha256
  `calibration.started` names.** A relabel after a calibration is visible as a sha mismatch, shown as `labels changed
  since calibration` (T-GW-16b).

## 5. The judge stipulation (R-58 DR-1, R-33)

`bench/gateway.yaml` (new, W3-GW-I):

```yaml
schema: bench-gateway/1
call_timeout_seconds: 180    # about 13 x the slowest measured call (13.3 s, Codex); not part of any key
judges:
  - { vendor: anthropic, harness: claude-code, model: claude-fable-5-1, output: text,
      build: { version: "2.1.282", exe_sha256: "fc0e3af0…" }, qualified: true }    # spike GW-H: served, 0 tool events
  - { vendor: openai, harness: codex, model: gpt-6-sol, output: native,
      build: { version: "0.156.0", exe_sha256: "<pinned>" }, qualified: false }   # DR-GW-1
```

- **The Anthropic judge is `claude-fable-5-1`** (Verified). Claude Code 2.1.282 serves it in print mode. Text mode
  gives 0 tool events and a valid answer. `claude-opus-5-5` was also served with 0 tool events, and it stays the
  named fallback. Using it is a catalog change.
- **Output mode per judge** (Verified):
  - **Claude: text.** The answer shape is in the prompt, and the gateway validates the answer. `--json-schema` adds a
    `StructuredOutput` tool call and a second turn, which fails R-58 c4.
  - **Codex: native `--output-schema`.** It added no tool event over text mode, and it constrains decoding.
- **`qualified`** is set by the Leader from a probe of the exact invocation (§8.4). The gateway never spawns a judge
  with `qualified: false` (T-GW-32).
- **Fixed before any verdict is stored:**
  - Each judge entry (everything but `call_timeout_seconds`) joins the `catalog_hash` recipe (R-59 c1). This is a
    seam request to W3-GRADE-CORE.
  - The control that fires on a change without a version bump is check (b) of the US-4 test in
    `docs/design/phase3-graders.md` §4: "the current `catalog_hash` differs from the one pinned".
  - Independently, the key (§9.1) carries the model and the invocation, so an old entry is never reused.
- **Never passed:** `--fallback-model`. It would switch the judge silently (ADR-0009:60).
- **Header:** names the stipulated and served ids of each judge, and says "not qualified" for an unqualified judge
  (§12).

## 6. When judges run (R-58 DR-2, c3; US-26 c2)

- **In-run pass** (`cli.py:163`): no lookup, no call, no `verdict_uses` rows. Every judged metric is NOT_RECORDED
  `judge calls not allowed in this pass`. This is R-58 DR-2 read literally.
- **`bench grade` without the flag:** it reads the store. A miss is `not_allowed`, and the pass prints
  `judge misses: <n calls>` (US-26 c2).
- **`bench grade --allow-model-calls`** (spec `:438`) and **`tools/calibrate.py`**: the only callers that spawn a
  judge. The live-run refusal lives inside the gateway, so both get it. Before its first spawn, the gateway refuses
  with `HB-GRD-005` when any run is live (review w3-gwi-1 A1: `HB-GRD-003` already means a grader failure, so
  slice 4 took a new code; `errors.RUN_CODES`):
  - **Which runs:** every run folder under the `runs/` of every worktree of this repository (`git worktree list`),
    plus `--runs`, filtered by `status.require_known`. The cells root is shared across worktrees, but each worktree
    keeps its own `runs/`, so scanning only `--runs` would miss the primary checkout's live run.
  - **Live** is `status.build(...).liveness` in {`alive`, `stalled`}: the run lock is held (`status.py:3-5`, `:107`).
    See DR-GW-4.
  - **Residual:** a `--runs` folder outside every worktree is not seen. It is recorded as a limit in DR-GW-4.
- **Day hours** (R-58 DR-2) stay an operator rule.
- **DR-GW-5 gate:** the Leader runs no live judge pass before DR-GW-5 is ruled in writing (Security condition).

## 7. The judge request

### 7.1 Inputs (US-35 c1)

- **Rubric:** `bench/rubrics/<metric>.md` (§13), verbatim.
- **Artifact:** the files the catalog entry's `artifact:` list names, read from the cell's archived working copy.
  For C1 these are `docs/architecture.md` and `priority_queue.py`.
- **Oracle:** DR-GW-2. The proposal is the rubric itself; no reference file is sent.
- **Bounds:** each file must be valid UTF-8 and ≤ 65,536 bytes. Otherwise the row is `failed` with `HB-GW-008`
  (`artifact over the judge bound or not UTF-8`). T-GW-06 tests 65,536 and 65,537 bytes and invalid UTF-8.
  `simplify:` no excerpting. Upgrade trigger: a judged artifact over the bound.

### 7.2 Rendering and delimiting (US-46 c1)

- **Pattern:** spotlighting by delimiting (a boundary nonce, as in MIME multipart). One template,
  `template_version` `judge-request/1`. Its expected output is pinned by a golden file (T-GW-33, directive A1).
- **Order:**
  1. hash the raw bytes (`artifact_sha256`);
  2. nonce = its first 12 hex digits;
  3. scrub (§7.3);
  4. escape any `<<<END DATA` in the scrubbed text as `<<<END\u2060DATA`;
  5. render.

  An agent cannot write a matching closing fence into content whose hash it does not know. The order is pinned by
  T-GW-01 and T-GW-02.
- Fences: `<<<DATA <nonce> <path>>>` … `<<<END DATA <nonce>>>`.

### 7.3 Blinding scrub and scan (US-35 c1)

- **Denylist** (`scrub_version`):
  - the pack markers, loaded with the existing `config.pack_marker_bytes` (`config.py:151`);
  - harness ids and names;
  - every model id in `bench/prices.yaml` and the plan's combos;
  - the plan's combo ids;
  - model family words as whole words, case-insensitive: Claude, GPT, Gemini, Grok, Fable, Opus, Sonnet.
- **Scrub:** each hit becomes `[redacted]`. The rubric and template are operator text; `bench validate` fails if they
  contain an entry.
- **Scan (an independent check):** after rendering, the whole request is scanned for every entry. A hit is `failed`
  with `HB-GW-004`, and nothing is sent. The property tested is "the scan of scrub(x) finds nothing", including
  word-boundary near-misses and zero-width characters (T-GW-03).
- **What the CLI adds after the gateway** (spike GW-H result 6):
  - neither CLI added a pack marker;
  - both add their own identity. Claude: "Fable 5.1 … `claude-fable-5-1`" and "a Claude agent, built on Anthropic's
    Claude Agent SDK". Codex: "Codex" and `gpt-6-sol`;
  - both add the working-folder path.

  These strings name the judge, not the cell, but a scan of the wire request would find denylist words in them. So
  US-35 c1's "captured request" is read as the gateway-rendered request. That request carries the cell, and it is the
  only one the gateway can capture (TLS is not intercepted, ADR-0005:56). The reading is the Owner's to confirm
  (DR-GW-5).

### 7.4 Egress (US-47, ADR-0005:36-41, ADR-0012:71,:85)

- The rendered request passes W3-EGRESS's `egress.check(request, destination=<judge model id>,
  operator=Operator(email, username, home), secrets=<host credential values>, canaries=<US-13/US-48 canaries>)`
  (branch `w3-egress` at `3517324`, `egress.py:86`).
  - The backend is reached only through `Verdict.release(backend)`, which returns `None` for a withheld payload.
  - A hit is `failed` with `HB-GW-009 withheld: sensitive content`, and nothing is sent.
  - The `egress_events` row holds the payload hash, destination and classes. The secret values are read at run time
    and never logged or written (`egress.py:79`, `:90`).
- **Identifiers the CLI adds after `release`** (Verified, spike GW-H results 4 and 5):
  - **Claude:** a `session_context` attachment with the account e-mail, and a `credential_org` attachment. Both were
    present on both measured text-mode turns (the gateway's mode) and empty on the one native-mode turn. Inferred:
    every text-mode call carries it, n = 2.
  - **Codex:** the `<skills_instructions>` roots table with the operator's real `~/.agents/skills` path (user name,
    home path) and 6 operator skills. The decoy USERPROFILE does not redirect it (N5).
- **Detection is derived, not stored:** a report-time function, `views.cli_context_classes(record,
  request, answer)`, runs over each archived judge record.
  - It works by subtraction: every string in the record except the gateway's own request and answer spans.
  - It reports `Verdict.classes` only. It is never written to `egress_events`: that fact holds send decisions, and
    this text was already sent.
  - A record that cannot be parsed reads `not recorded`, never "none" (IO).
  - The header discloses the classes per judge. The race-loser's record is archived too, so no call is missed.
  - What to do about a hit is DR-GW-5.

## 8. The call: the headless backend (ADR-0009:42, as amended by ADR-0013)

### 8.1 Launch shape (one definition)

- The argv builders live once, in `gateway/backend.py`. The probe imports them from there once s2 lands, so a
  re-qualification tests the exact production invocation. Until then, `tests/fixtures/gateway/probe_judge.py` is the
  qualified definition, and s2 moves it unchanged.
- The request goes on **stdin**, not in argv:
  - Claude: `-p` with the request piped;
  - Codex: `exec` with `-` as the prompt.

  This removes the Windows command-line limit (32,767 characters, below the 64 KiB bound) and any quote or backslash
  argv parsing of hostile text. `procs.run` gains an `input` parameter in s2 (a seam with its owner). The probe
  measured argv delivery, so this shape change is re-probed before the first live pass (§8.4).
- **Claude Code 2.1.282, qualified:** `-p --model claude-fable-5-1 --tools "" --strict-mcp-config --safe-mode
  --disable-slash-commands --permission-mode dontAsk --permission-prompts none --settings
  {"disableClaudeAiConnectors": true} --system-prompt <judge system prompt> --output-format json
  --session-id <uuid>`. There is no `--json-schema`. Measured: advertised tools `[]`, 0 tool events, account
  connectors 0, prompt intact, the recorded system prompt is the judge's own.
- **Codex 0.156.0, not qualified (DR-GW-1):** `exec -c model=gpt-6-sol -c approval_policy="never"
  -c web_search="disabled" -c project_doc_max_bytes=0 --disable <20 tool features> --ignore-user-config
  --ignore-rules --skip-git-repo-check -s read-only -C <work> --json -o <last message> --output-schema <file> -`.
  - `include_apply_patch_tool` is dropped: 0.156.0 reports it unrecognized.
  - `exec` (code mode) stays advertised. The model called it once per turn, and it failed closed.
  - Whether any other tool is advertised is not recorded: the rollout does not list tools.
- Neither CLI has a temperature flag (both `--help` outputs, Verified). `judge.py`'s docstring "temperature 0" is
  false for this backend, and s3 corrects it. Determinism comes from the store (US-26).

### 8.2 Process, folders and the credential

- **Call folders live under the cells root, never under the repository:**
  `<cells root>/gateway/<grading_id>/<call_id>/{home,work,profile}`. `call_id` is the first 16 hex digits of the key.
  - Before the first spawn of a pass, the gateway runs `workspace.check_cells_root` (`workspace.py:32`). It refuses an
    instruction file above the folder, as the probe did. The repository root holds AGENTS.md, CLAUDE.md,
    `.agents/skills` and command hooks, so a folder under `runs/` would sit below them.
  - Nothing in the folder path names a harness, model or combo. Both CLIs send the path to the model.
  - `plan.py:237`'s default cells root has no user name. The path goes through `egress.check` once per pass (T-GW-26).
- **Credential:**
  - It is copied inside the `try` whose `finally` deletes it (`profile.clean_home`).
  - At the start and end of every pass, the gateway also removes any leftover credential copy under
    `<cells root>/gateway/`, covering a hard kill of an earlier pass. It sweeps only a pass folder whose
    `<grading_id>/.lock` (an `oslock` lock each pass holds while it runs) is free. The cells root is shared across
    worktrees, so a concurrent pass's copy is never touched.
  - `bench verify` errors on any leftover copy (`HB-GW-010`).
  - The CLI may rotate the copied refresh token. That can affect the operator's own login (an availability risk,
    §18). The copy never returns to the source.
- **After the call:** the native record is copied into
  `runs/<run>/grading/<grading_id>/gateway/<call_id>/record.jsonl` (or the calibration ledger's folder). This is the
  same archive rule as a cell's record. The cells-root call folder is then deleted.
  - The archive holds the account e-mail and the Codex skill root, as cell archives already do. `runs/` is local and
    never published with a report (spec `:572`); T-GW-34 asserts that no report or export embeds a judge record.
- **Environment:** `profile.cell_env(...)` (`profiles.py:28-31`), with USERPROFILE and HOME at the empty decoy
  `profile/` folder, as qualified. `simplify:` it is kept because it is the qualified configuration; removing it needs
  a re-probe. It does not stop Codex's skill root.
- **Process:** spawned through `procs.run` in its own Job Object (ADR-0013; `procs.py:264`) with
  `call_timeout_seconds`.
- **Build:** the executable is re-hashed against the judge entry's `build` before the first spawn of a pass
  (`tools.check_build`). A mismatch refuses the pass for that judge (`HB-GW-011`).

### 8.3 Reading the answer

1. **Tool events:** the record must show 0. Otherwise the row is `failed` with `HB-GW-006`, and nothing is stored.
   Under DR-GW-1 (a) only, an `exec` whose *output* is exactly `code-mode host is disabled` would be admitted. The
   rule matches the output, never the call row's `status: "completed"`. That rule and T-GW-25 are built only if the
   Owner rules (a).
2. **Served model:** every call in the record is the pin or a declared auxiliary (`profiles.model_allowed`, US-11).
   Otherwise `failed` with `HB-GW-003`.
3. **Final text:** Claude's stdout JSON `result`; Codex's `-o` file. A fenced JSON answer is unwrapped once and
   recorded as fenced (T-GW-35).
4. **Validation:** one definition of the shape, `gateway/schemas/verdict-set.v1.json`. The stdlib validator reads the
   closed subset it needs from that file. A test asserts that the validator and the file agree on every
   accept/reject case (T-GW-05b). A failure is `failed` with `HB-GW-002`.
5. **Circuit breaker:** the first `HB-GW-001` of a judge in a pass whose provider error is a rate or quota limit
   (status 429, or an error type containing `rate_limit` or `quota`) opens that judge's breaker. Its remaining calls
   in the pass are `failed` with `HB-GW-001` and are not spawned. The spike measured the OpenAI account at 99 % of
   its weekly limit.

### 8.4 Qualification (R-58 c4) and re-qualification

- **Claude `claude-fable-5-1`: qualified** (spike GW-H, argv delivery). The stdin and cells-root shape (§8.1, §8.2)
  is re-probed with one turn before the first live pass. The Leader runs it from the s2 builders. The probe records
  `invocation_sha256`, which ties the qualification to one key input (§9.1).
- **Codex `gpt-6-sol`: not qualified.** It had 1 tool event per turn. `qualified: false`, and it is never spawned
  (T-GW-32).
  - "Nothing executed" is Verified as the CLI's own report only: the tool output `code-mode host is disabled`, the
    stderr line, and the answer. Nothing outside the CLI confirms it.
  - If DR-GW-1 (a) is chosen, the fail-closed property becomes a precondition. It is re-probed on every build, with a
    hostile payload that tries to read `auth.json` and open a network connection, and it requires 0 side effects.
- **Negative results the spike cannot prove:** "no canary reached the model" is **Inferred** for the user-level
  classes. Codex did not look at the decoy at all, and Claude's user level is `CLAUDE_CONFIG_DIR`, not USERPROFILE.
  The defence does not rest on it: `check_cells_root` refuses instruction files above the call folder.
- **Re-qualification:** any build change, argv change or system-prompt change is a new `invocation_sha256`, a new
  probe and a new catalog version.
- **Injection fixture:** the US-46 c2 fixture runs only through a qualified judge (R-60 c2).

## 9. The store

### 9.1 Key (ADR-0006:102; R-58 c6)

`key = sha256(canonical({"request_sha256", "schema_sha256", "model", "invocation_sha256"}))`, canonical as
ADR-0006:49.
- `invocation_sha256` hashes:
  - the argv template, with the volatile slots (`<session-id>`, `<work>`, `<last message>`) as placeholders;
  - the judge system prompt;
  - the output mode;
  - the harness, build version and exe sha256.
- `gateway.yaml`'s other fields (the timeout) are in no key.
- **Coverage:** ADR-0006:102's list (artifact, rubric, prompt template, output schema, model, backend) is covered.
  The request hash contains the rubric, the scrubbed artifact and the template. The scrub version and the oracle are
  covered too. The recipe is written into the ADR-0006 amendment itself (§4.1).
- **T-GW-12b** changes each of the four inputs in turn and expects a new key and a miss. The mutants are named in
  `tests/mutations/gateway.json`.

### 9.2 Write-once

- The entry is written to `cache/verdicts/.<key>.<rand>.tmp`, flushed and `os.fsync`ed.
- Then `os.link(tmp, <key>.json)` and `os.unlink(tmp)`. `link` refuses an existing target on every OS, so the first
  writer wins without relying on Windows-only `rename` semantics. The entry is then set read-only.
- Only `FileExistsError` means the race was lost: the row is `race_lost`, and the winner's entry is read. Any other
  error (for example a `PermissionError` from antivirus) is `failed` with `HB-GW-001`.
- A `.tmp` older than 24 h is removed at pass start. T-GW-11 asserts that the first writer's bytes survive, and that
  the loser's row is `race_lost` with its `model_calls` rows written.

### 9.3 Hit acceptance (one check; the Security finding on planted entries)

The adversary may write anywhere it can reach (ADR-0012:39), including the store and a forged ledger. So a hit is
accepted only when all of these hold:
- the entry parses;
- its `key_inputs` recompute its file name;
- its served models are allowed;
- **provenance:**
  - `stored_by` resolves **only inside the known roots**: the `runs/` of each worktree (§6), where calibration
    ledgers also live. Any other path is not followed.
  - The named ledger verifies from its genesis row (`bench verify`'s chain check).
  - Its **sealed** segments hold a `verdict_uses` or `calibration_uses` row with outcome `stored`, the same key and
    the same `entry_sha256`.
  - The same pass holds a `model_calls` row with principal `gateway` and the entry's `native_session_id`.
  - Its archived `record.jsonl` exists.

  Acceptance reads sealed segments only.

Outcomes:
- **Provenance fails while the named ledger exists and verifies,** or it names a path outside the known roots, or the
  chain is forged: the row is `failed` with `HB-GW-005`. The entry is kept for inspection, and nothing is
  overwritten (T-GW-13b, T-GW-13c).
- **The named ledger no longer exists** (pruned; retention is P1's choice): the entry is orphaned, not forged.
  - It is still accepted as a `hit` when **this run's own** sealed ledger holds an earlier row with the same key and
    `entry_sha256`.
  - Otherwise the lookup is an honest miss (`not_allowed` without the flag).
  - With `--allow-model-calls`, the gateway moves the orphan to `cache/verdicts/orphaned/<key>.<utc>.json` (logged in
    the pass's `events`). It then calls and stores afresh (T-GW-13d).
  - **Retention rule:** pruning a ledger orphans its entries. It never poisons their keys.
- **A `race_lost` row** accepts the winner's entry on `key_inputs` and served models only. The winner's storing row is
  not sealed yet. The provenance check is deferred to later passes and to `verify` (T-GW-11).

This one check replaces revision 1's in-pass comparison, and it covers an edit made before a run's first read.
`bench verify` warns about each referenced entry that is missing or changed (T-GW-13).

## 10. Synthesis and scores

### 10.1 Per item (spec `:209`, US-35 c2)

| Verdicts | Item result |
| --- | --- |
| both recorded, `abs(a − b) ≤ 1` | synthesized value `(a + b) / 2`, a decimal string at scale 1 |
| both recorded, `abs(a − b) = 2` | NOT_RECORDED `judges disagree by 2 steps`; flagged; both verdicts shown |
| either not recorded (including a judge that is not qualified) | NOT_RECORDED, with that judge's outcome and code as the reason |

While DR-GW-1 is open, every C1 item is NOT_RECORDED `judge not qualified: gpt-6-sol`. That is the honest state of a
one-vendor jury under spec `:209`. DR-GW-1 (b) would change it.

### 10.2 Per metric (seam: W3-GRADE-D)

The proposal for C1's rubric metric: the value is the sum of the synthesized item values (0–14, scale 1) when all 7
items are synthesized. Otherwise it is NOT_RECORDED, naming the items (US-27). Every other judged metric is
NOT_RECORDED `no rubric for this task` (R-59 c2).

### 10.3 Injection flag (US-46 c2)

A pure function over the archived artifact, `views.injection_patterns(text, patterns_version)`, derives the flag at
report time. It is not stored (DM7). The flag never changes a score. The ≤ 1 step criterion is measured by W3-EGRESS
s2's live fixture, only through a qualified judge.

## 11. Calibration and κ (R-58 DR-3, c5; US-35 c3)

- **Unit:** one calibration item = one (artifact, rubric item) pair = one human label (spec `:208`). 30 items give 30
  labels, covering all 7 rubric items (≥ 4 each) and the 0/1/2 range (R-58 c5).
- **Request shape:** the production template and the full rubric. The verdict on the labelled item is the one
  compared. The join test (T-GW-17b) asserts that only that item is used.
- **Label before verdict (the invariant):** `tools/calibrate.py` refuses with `HB-CAL-001` before any spawn unless
  all of these hold:
  - the set of label ids equals the set of manifest ids;
  - no id is duplicated;
  - no id is unknown;
  - every score is in {0, 1, 2}.

  T-GW-16 feeds 30 labels that include a duplicate, 29 labels, an unknown id and a score of 3, and asserts 0 spawns.
- **Recorded:** `calibration.started` carries the `labels_sha256`. `calibration_uses` rows carry each key and
  `entry_sha256`. κ is computed from these rows.
- **Stale calibration (directive A6):** each calibration binds the template, schema, rubric and invocation hashes. If
  the current values differ, the header shows `not recorded: calibration stale`. If the labels' sha256 differs from
  the recorded one, it shows `labels changed since calibration`.
- **κ:** Cohen's κ, unweighted, over {0, 1, 2}: `κ = (p_o − p_e) / (1 − p_e)`, with `p_e = Σ_k p1(k) · p2(k)`.
  - Rounded half-even to a decimal string at scale 3. Non-additive.
  - `p_e = 1` gives NOT_RECORDED `kappa undefined: one category`.
  - Reported with n and exact agreement. No threshold (spec `:1173`).
  - T-GW-17 uses a table with asymmetric marginals and an exact expected value.
- **Human half:** each judge vs the labels. With no labels file it reads `not recorded: no human labels (operator
  declined 2026-09-25)` (R-72 condition 1: a terminal reason, never a waiting one). The set check above applies only
  when `labels.yaml` exists, all or none (R-72 item 4); an absent file runs the inter-judge calibration with
  `labels_sha256: null`. US-35 c3 stays a named wave-4 row until a human labeller exists.
- **Inter-judge half:** `not recorded: second judge not qualified` while DR-GW-1 is open.
- **Disclosure (R-62 a3):** "Calibration items were written by `claude-opus-5-5`; the Anthropic judge is a Claude
  model."

## 12. The header's judge block (report `header` section; W3-GW-I owns the hunk)

| Row | Content | Source |
| --- | --- | --- |
| Judges | per judge: stipulated id, served ids, harness build, `qualified` | `gateway.yaml`, entries of the pass (T-GW-29) |
| CLI-added context | per judge: the classes the CLI added (e.g. `email`; `username`, `home_path`), or `not recorded` | `views.cli_context_classes` (§7.4) |
| Calibration | n; inter-judge κ; each judge's κ and exact agreement vs labels; or the `not recorded` reason | calibration ledger + labels |
| Agreement on this run | items judged; exact; within one step; disagreements | `verdict_uses` + entries |
| Verdict split by cell vendor (R-58 c2) | mean (Claude verdict − GPT verdict) per cell vendor, with n; "disclosed, not a gate" | as above, joined to the plan's combos (T-GW-27) |
| Judge spend | tokens and calls by judge | `model_calls` principal `gateway`; `views.judge_calls` |
| Probe versions | a `.dev` catalog is a `probe pass` (R-59 DR-4) | `grading.started` |

- Cell vendor comes from the cell harness profile's `vendor:` field, never from a model-id prefix (R-73 item 1;
  `report/judges.py` `cell_vendors`). C1 has 2 Anthropic cells and 4 OpenAI cells, so n is 14 and 28 items.
- Judge rationales are untrusted text and are rendered only through `html._e` (`html.py:53`). T-GW-36 renders a
  `<script>` rationale as inert text.

## 13. C1's rubric in the catalog (R-59 DR-5, c2)

- `bench/rubrics/<metric>.md` is the authoritative rubric. `<metric>` is the id W3-GRADE-D names (seam).
- The catalog entry gains three fields (built in slice 5 in the graders design's form, where one map names both the
  rubric file and its tasks):
  - `rubrics: {C1: adr_quality.md}` (the rubric and the tasks it applies to);
  - `artifact: [docs/architecture.md, priority_queue.py]`;
  - `scale: 1` (the synthesized half-steps) and the R-64 `note:`.

  Other tasks' judged metrics are NOT_RECORDED `no rubric for this task`.
- `bench validate` asserts that `tasks/C1/oracle/rubric.md` is byte-equal to the catalog copy (spec `:255` pattern).
  C1's file becomes a pointer only at C1's next task version (R-59 c5).
- **The conflict:** R-59 c2 asks for a preamble stating why no mechanical oracle applies, but DR-5 and c5 freeze the
  file. This is DR-GW-3.

## 14. The matcher's model rung

The backend, store and egress path are reusable. W3-GR-CLAR designs the matcher's model rung. Its key is the existing
recipe, `scripted_user/matcher.py:86` `cache_key` (R-53), wrapped as `request_sha256`'s input, so one concept keeps
one recipe. Its rows use the same `judge_or_matcher` key column.

## 15. Change-surface list (E7)

| Surface | Change | Owner |
| --- | --- | --- |
| store | `cache/verdicts/`; `.gitignore` gains `cache/` | GW-I |
| store | `verdict_uses` segment per pass; `model_calls` rows principal `gateway`; archived judge records | GW-I via GRADE-CORE's runner (seam) |
| store | `runs/calibration-C1-<hash>/` ledger with `calibration_uses` | GW-I |
| ADR | the ADR-0006 amendment text (§4.1, §9.1) | GW-I, number from the Leader (W3-COST takes Amendment 2) |
| code lists | `views.FACTS`, `views.KEYS` (`views.py:49-56`); `runner.PASS_FACTS` (`runner.py:33`) | GRADE-CORE (seam) |
| config | `bench/gateway.yaml`; `bench/rubrics/<metric>.md`; catalog entry fields | GW-I; id from GRADE-D |
| model | `VerdictSet`, `VerdictUse`, `JudgeRequest`, `Judge` dataclasses | GW-I |
| service | `gateway/` (request, scrub, backend, store, breaker), `grade/judge.py` | GW-I |
| process | `procs.run(..., input=)` | seam with the `procs.py` owner |
| hash | `catalog_hash` covers each judge entry | GRADE-CORE (seam) |
| CLI | `bench grade --allow-model-calls`, `HB-GRD-005` | GW-I after STOP-I joins |
| validate | rubric byte-equality; rubric and template contain no denylist entry | GW-I |
| projection | κ, agreement, vendor split, judge spend, `judge_calls`, `cli_context_classes`, `injection_patterns` | GW-I (`views`) |
| UI | the header's judge block; the item view with both verdicts | GW-I (`report/html.py` hunk) |
| compute reader | C1 metric aggregation (§10.2) | GRADE-D / GRADE-CORE |
| verify | entries missing or changed; leftover credential copies | GW-I |
| probe | `probe_judge.py` imports the s2 builders; records `invocation_sha256` | GW-I s2 |

## 16. Slice plan for W3-GW-I (Codex `gpt-6-sol`, ≤ 6 slices, red first)

| Slice | Content | Proof |
| --- | --- | --- |
| s1 | Request rendering (order §7.2), scrub + scan, the schema-file validator, the key, the write-once store, hit acceptance (§9.3), behind a `Backend` protocol | unit and property tests; T-GW-01..06, 11, 12b, 13, 30, 31, 33 |
| s2 | Headless backend: the builders (moved from the probe), stdin via `procs.run(input=)`, cells-root folders + `check_cells_root`, credential handling and sweep, `qualified` gate, served-model, tool-event and schema checks, breaker, record archive, `model_calls` principal `gateway` | contract tests on the spike's records, copied into `tests/fixtures/gateway/records/` with identifiers replaced by fixed placeholders (the copy script fails if a real value remains); T-GW-07..10, 26, 28, 32, 35 |
| s3 | `grade/judge.py`: lookups, `verdict_uses` rows, synthesis, NA reasons; wired through GRADE-CORE's dispatch | the replay fake backend (below); T-GW-12, 20, 21, 22 |
| s4 | `--allow-model-calls`, the gateway's live-run refusal across worktrees (after STOP-I joins); in-run NA | T-GW-19, 19b, 19c |
| s5 | `tools/calibrate.py`, the calibration ledger, κ, the header block, the rubric in the catalog, `bench validate` checks, report-time detectors | T-GW-16, 16b, 17, 17b, 24, 27, 29, 34, 36 |
| s6 | reserved for GR-CLAR's matcher-rung design (§14) | GR-CLAR's fixtures |

**The fake backend replays native records.** It writes the spike's placeholder-scrubbed record files into the call
folder, and the real readers decide the outcome. It never returns parsed facts (directive D7, no mock fiction). Live
turns stay the Leader's:
- the stdin re-probe;
- the calibration run;
- the judge pass;
- a second pass whose `model_calls` principal `gateway` count is 0. This is a Proof Pack item for R-58 c6.

## 17. Error and concurrency model

- **Codes (new):**

  | Code | Meaning |
  | --- | --- |
  | `HB-GRD-005` | a run is live (lock liveness alive or stalled); judge model calls refused before any spawn |
  | `HB-GW-001` | judge unavailable: CLI error, timeout, provider error, breaker open, or a store write error other than a lost race |
  | `HB-GW-002` | invalid output |
  | `HB-GW-003` | served model not the pin |
  | `HB-GW-004` | blinding scan hit |
  | `HB-GW-005` | store entry invalid, or not matched by its storing row |
  | `HB-GW-006` | tool event in a judge call |
  | `HB-GW-007` | judge not qualified |
  | `HB-GW-008` | artifact over the bound or not UTF-8 |
  | `HB-GW-009` | withheld: sensitive content |
  | `HB-GW-010` | leftover credential copy (a `verify` error) |
  | `HB-GW-011` | judge build changed |
  | `HB-CAL-001` | labels do not match the manifest |

- **No retry.** A later re-grade fills a failure. `simplify:` upgrade trigger: over 5 % of a pass's calls `failed`
  with `HB-GW-001` for reasons other than the breaker.
- **Serial calls.** `simplify:` parallelism 1. The ceiling is 12 calls per pass and 60 for calibration. Upgrade
  trigger: a pass's judge wall time over 30 minutes.
- **Across passes:** `grade.lock` is per run. Two runs racing on one key are resolved by §9.2.

## 18. Failure-mode analysis

| Failure mode | From which choice | Disposition | How | Detection | Test |
| --- | --- | --- | --- | --- | --- |
| CLI serves another model | headless CLI, subscription | detect; no store | §8.3 step 2 | `HB-GW-003` rows | T-GW-07 |
| Judge advertises or calls a tool | coding CLI | prevent (unqualified never spawned) + detect | `qualified` gate; §8.3 step 1 | `HB-GW-006`, `HB-GW-007` | T-GW-08, T-GW-32 |
| Answer not JSON / wrong shape | free-text output | detect | one schema, validator from it | `HB-GW-002` | T-GW-05, 05b, 35 |
| Judge down, slow, rate-limited | vendor dependency | degrade; breaker | NOT_RECORDED; re-grade fills | `HB-GW-001` | T-GW-09 |
| Call hangs | subprocess | mitigate | `procs.run` timeout, Job Object | `HB-GW-001` | T-GW-09 |
| Credential copy left behind | per-call home | prevent + detect | copy inside `try`; sweep at pass start and end; `verify` | `HB-GW-010` | T-GW-10 (exception after copy; simulated kill and restart) |
| Refresh token rotated in the copy | subscription login | accept | the copy never returns to the source. Residual: the operator may need to log in again, visible as a CLI auth error | provider error rows | — |
| Two passes write one key | shared store | prevent | `os.link` write-once | `race_lost` rows | T-GW-11 |
| Crash mid-write | shared store | prevent | tmp + fsync + link; stale tmp removed | — | T-GW-11 |
| Planted or edited entry | store writable by cells (ADR-0012:39) | prevent | hit accepted only with a matching storing row | `HB-GW-005`; `verify` warning | T-GW-13, 13b |
| Judge switched after verdicts stored | stipulation | prevent | judge entry in `catalog_hash`; model and invocation in key | graders design §4 check (b) | T-GW-14, 12b |
| Build or argv change | pinned CLI | prevent | build check; `invocation_sha256` | `HB-GW-011` | T-GW-15, 12b |
| A run starts during a judge pass | operator timing | accept | checked before the first spawn. Residual: a run started mid-pass shares the account for up to the pass's length | pass and run events | — |
| Live run in another worktree | per-worktree `runs/` | prevent | scan every worktree's `runs/` | `HB-GRD-005` | T-GW-19b |
| Blinding leak via artifact | scrub | prevent + detect | scrub, then independent scan | `HB-GW-004` | T-GW-03, 04 |
| CLI adds identity, e-mail or skill root | harness context after `release` | detect; DR-GW-5 | report-time subtraction detector | header line | T-GW-24 |
| Instruction files above the call folder | CLI discovery | prevent | cells-root folders; `check_cells_root` | refusal | T-GW-26b |
| Hostile text breaks argv | argv delivery | prevent | stdin | — | T-GW-37 (quotes, backslashes, `--flag`, newlines, 64 KiB) |
| Scores differ across re-grades | model non-determinism | prevent | a re-grade reads, never calls | pinned export equal | T-GW-12 |
| Labels made after verdicts, or mismatched | order | prevent | set check before any spawn | `HB-CAL-001` | T-GW-16 |
| Relabel after calibration | Type-1 working file | detect | recorded `labels_sha256` | header text | T-GW-16b |
| κ undefined | one category | degrade | NOT_RECORDED with reason | header | T-GW-17 |
| Artifact too large or not text | bound | degrade | `HB-GW-008` | row | T-GW-06 |

## Adversarial analysis (STRIDE-lite)

*Section 19. Its heading is unnumbered so `docs-graph.py rollup` finds it.*

| Trust boundary | STRIDE threat | Disposition | Control / rationale | Negative test |
| --- | --- | --- | --- | --- |
| Cell artifact → judge request | T/E: prompt injection steers the verdict or a tool | mitigate | no tools (qualified judges only; per-call check); spotlighting fences; schema; ±1 jury check; injection flag | T-GW-02, T-GW-08, T-GW-32; EGRESS s2 live fixture |
| Cell artifact → judge request | I: a secret or the operator's identifiers in the artifact | mitigate | `egress.check` before `release` | T-GW-18 (canary → `HB-GW-009`; the fake backend receives nothing) |
| Cell artifact → judge request | I: harness/model/pack identity leaks (bias) | mitigate | scrub + independent scan | T-GW-03, T-GW-04 |
| Cell artifact → CLI argv | T/E: argv injection by quotes or flags | mitigate | the request on stdin | T-GW-37 |
| Filesystem around the call | E/I: repo instruction files, skills or hooks load into the judge | mitigate | cells-root call folders; `check_cells_root` before the first spawn | T-GW-26b |
| Gateway → CLI process | I: credential exposure | mitigate | per-call copy inside `try`, deleted in `finally`, swept at pass start and end, `verify` error; env scrubbed; never an API key; secret values never logged | T-GW-10 |
| Gateway → CLI process | S: a different binary | mitigate | exe re-hash against the judge entry's build | T-GW-15 |
| Gateway → unqualified judge | E: a tool-bearing CLI receives hostile text | mitigate | `qualified: false` is never spawned | T-GW-32 |
| CLI → vendor | I: account e-mail (Claude), skill root with user name and home path (Codex), self-identity (both) | detect; disposition DR-GW-5; no live pass before the ruling | report-time detector; header disclosure | T-GW-24 |
| Vendor → verdict | T: malformed or oversized answer | mitigate | schema validator | T-GW-05 |
| Store | T: an entry planted or edited by a cell agent | mitigate | hit accepted only with a matching hash-chained storing row | T-GW-13b |
| Store | R: which call produced a verdict | mitigate | `stored_by`, `native_session_id`, the archived record | T-GW-31 |
| `bench grade --allow-model-calls`, `calibrate.py` | E/D: model calls during a live run (R-9 confound) | mitigate | the refusal inside the gateway, across worktrees | T-GW-19, 19b |
| Report | I/T: a rationale carries script | mitigate | `html._e` | T-GW-36 |
| Archive | I: judge records hold identifiers | mitigate | `runs/` never published; no export embeds a record | T-GW-34 |
| Calibration | T: labels shaped by verdicts | mitigate | set check before any spawn | T-GW-16 |

## Privacy analysis (LINDDUN-lite)

*Section 20. Its heading is unnumbered for the same reason.*

| Data flow / category | LINDDUN finding | Disposition | Control / rationale | Retention & rights path |
| --- | --- | --- | --- | --- |
| Artifact text → vendor | D: an agent wrote the operator's e-mail, user name or home path into an artifact | mitigate | `egress.check`; `HB-GW-009` | nothing sent; archive per `runs/` retention (P1 deletes) |
| CLI context → vendor | D/I: Claude adds the account e-mail and org UUID (both measured text-mode turns; Inferred: every call); Codex adds `C:/Users/<user>/.agents/skills` and 6 skill descriptions | detect; disposition DR-GW-5 | report-time detector and header disclosure. The same context reaches each vendor in every cell of that harness today | vendor retention per the operator's plan |
| Judge records → local archive | I: records hold the e-mail, user name and home path | mitigate | local `runs/`, never published (spec `:572`); T-GW-34 | P1 deletes `runs/` |
| Judge calls → vendor account | L: calls linked to the operator's subscription | accept | ADR-0009 accepted it (subscriptions only) | vendor retention |
| Calibration labels | I: the operator's judgements, committed | accept | scores only | git history; the operator can remove the file |

## 21. Telemetry

The bench's telemetry is its ledger (ADR-0006; ADR-0008).

| Question | Source |
| --- | --- |
| How many judge calls, and how did each end? | `views.judge_calls` over `verdict_uses` (`outcome`, `code`) |
| Tokens and time per call | `model_calls` principal `gateway` |
| Which model answered? | entry `served_models`; `model_calls.model` |
| What was sent, and was it withheld? | `egress_events` (hash, destination, classes) |
| What did each CLI add? | `views.cli_context_classes` over the archived records |
| Was the request blinded? | `HB-GW-004` rows; entry `components.scrub_version` |
| Why is a judged score missing? | the `scores` reason; the item's `(outcome, code)` |
| Calibration state | the set check; κ or the `not recorded` reason; stale or relabelled flags |

`bench grade` prints one line per `(outcome, code)` with its call count. A measurement gap reads `not recorded`,
never a plausible number.

## 22. Test plan (Testing Strategy: D0 plus the triggered directives)

**Triggered directives:**
- pure functions (scrub, render, key, synthesis, κ): unit and property tests;
- parsers of untrusted input (CLI output, native records, entries, labels): boundary and negative tests;
- a process boundary: contract tests on recorded native files, replayed by the fake backend (D7);
- a rendered prompt: a golden snapshot (A1);
- calibration binding (A6);
- concurrency: a race test;
- security controls: negative security tests;
- a new fact: append-only and golden-ledger tests;
- mutation testing: `tests/mutations/gateway.json`. The threshold is the repo's mutation gate; the named mutants
  include each key input (T-GW-12b) and the set check (T-GW-16).

| Id | Promise | Test |
| --- | --- | --- |
| T-GW-01 | render is deterministic in the §7.2 order | same inputs → same bytes; the nonce comes from the raw bytes |
| T-GW-02 | data cannot close its fence | an artifact with `<<<END DATA` is escaped and flagged |
| T-GW-03 | the scan of scrub(x) finds nothing | property; word-boundary near-misses; zero-width characters |
| T-GW-04 | the scan is independent | a scrub stub that leaves one entry → `HB-GW-004`, 0 spawns |
| T-GW-05 | output validation | missing item, extra key, score 3, bool score, duplicate item, over-long rationale fail |
| T-GW-05b | one shape definition | the validator and the schema file agree on every case |
| T-GW-06 | bound | 65,536 bytes pass; 65,537 and invalid UTF-8 → `HB-GW-008` |
| T-GW-07 | served-model check | a replayed record serving another model → `HB-GW-003`, no entry |
| T-GW-08 | tool events fail a call | the spike's Claude native record (`StructuredOutput`) → `HB-GW-006` |
| T-GW-09 | unavailable and breaker | a timeout and a 429 record → `HB-GW-001`; after the 429 the rest are unspawned |
| T-GW-10 | credential gone on every path | success, exception after copy, timeout, simulated kill then restart sweep; a pass folder with a held `.lock` is not swept |
| T-GW-11 | write-once | the first writer's bytes survive; the loser gets `race_lost` with `model_calls` and accepts before the winner seals; `PermissionError` → `HB-GW-001` |
| T-GW-12 | warm re-grade: 0 spawns | a counting replay backend: pass 2 spawns 0; the `scores` export (values, reasons) is byte-equal across passes |
| T-GW-12b | each key input matters | change request, schema, model or invocation → new key, miss |
| T-GW-13 | `verify` sees a changed entry | edit after storing → `verify` warning |
| T-GW-13b | planted entry refused | an entry with no matching storing row → `HB-GW-005` |
| T-GW-13c | forged provenance refused | `stored_by` outside the known roots, a forged chain, or no matching `gateway` `model_calls` row → `HB-GW-005` |
| T-GW-13d | pruned ledger is not poison | delete the storing run, re-grade another run: an honest miss; with the flag, the orphan is moved and a fresh entry stored |
| T-GW-14 | judge switch is a catalog change | edit a judge entry → `catalog_hash` changes; graders §4 check (b) fails without a bump |
| T-GW-15 | build change | another exe hash → `HB-GW-011` before any spawn |
| T-GW-16 | label set check | 30 with a duplicate, 29, an unknown id, a score of 3 → `HB-CAL-001`, 0 spawns |
| T-GW-16b | relabel visible | labels sha differs from `calibration.started` → header `labels changed since calibration` |
| T-GW-17 | κ exact | a hand table with asymmetric marginals → the exact scale-3 value; one category → NOT_RECORDED |
| T-GW-17b | calibration join | only the labelled item of the 7-item verdict set is compared |
| T-GW-17c | stale calibration (A6) | change each of the template, schema, rubric and invocation hashes in turn → header `not recorded: calibration stale` |
| T-GW-18 | egress | a planted canary → `HB-GW-009`, 0 spawns |
| T-GW-19 | live-run refusal | a held lock in this worktree's `runs/` → `HB-GRD-005`, 0 spawns |
| T-GW-19b | across worktrees | a real sibling worktree (`git worktree add` in a temp repo, not a stub) with a held lock in its `runs/` → `HB-GRD-005` |
| T-GW-19c | known-run filter | `runs/calibration-*` (no `plan.json`) is skipped, not an error |
| T-GW-20 | synthesis table | every (a, b) in {0,1,2}²: the mean, or NOT_RECORDED at distance 2 |
| T-GW-21 | append-only `verdict_uses` | an attempted rewrite fails `bench verify` |
| T-GW-22 | NA reasons | in-run: `judge calls not allowed in this pass` and no rows; other tasks: `no rubric for this task`; unqualified judge: `judge not qualified` |
| T-GW-23 | rubric equality | a one-byte change in either copy fails `bench validate` |
| T-GW-24 | CLI-added context detector | placeholder records: Claude text → `email`; Claude native → none; Codex → `username`, `home_path`; an e-mail in a new row kind is found; unparseable → `not recorded` |
| T-GW-25 | DR-GW-1 (a) rule (built only if ruled) | the spike's Codex record accepted only by output match; any other output rejected |
| T-GW-26 | folder path | a cells root containing the user name → `HB-GW-009` before any spawn |
| T-GW-26b | instruction file above the folder | a CLAUDE.md or AGENTS.md above → refused before spawn |
| T-GW-27 | vendor split | an asymmetric hand table: sign is Claude − GPT; n = 14 and 28 |
| T-GW-28 | `model_calls` principal `gateway` | the Claude text record → rows with principal `gateway`, `cell_id` null, tokens = stdout `usage`; a warm pass writes 0 rows |
| T-GW-29 | header names judges | both stipulated ids and served ids render; an unqualified judge says so |
| T-GW-30 | every NOT_RECORDED path maps to one `(outcome, code)` | table-driven over §6–§9 |
| T-GW-31 | key recomputes | `key_inputs` → the file name |
| T-GW-32 | unqualified judge | `qualified: false` → 0 spawns, `HB-GW-007` |
| T-GW-33 | golden request | `judge-request/1` render matches the committed golden file |
| T-GW-34 | no record in a report | `report.html` and exports contain no judge-record text |
| T-GW-35 | fenced answer | a fenced JSON answer is unwrapped once and recorded as fenced |
| T-GW-36 | rationale escaped | a `<script>` rationale renders inert |
| T-GW-37 | stdin delivery | hostile quotes, backslashes, `--flag`, newlines and 64 KiB reach the record intact (replay) and in the Leader's re-probe |

The golden-ledger regression for `verdict_uses` is T-GW-21's fixture ledger.

## 23. Conformance notes

- LOA: AI Gateway, Read-Through memo store on exact keys, Guardrail Filter (LOA 6.2).
- The two-vendor jury is a **Panel of LLM evaluators (PoLL)**, not Self-Consistency. Self-Consistency means sampling
  one model several times. ADR-0009:47 uses the older name, so a follow-up for the ADR owner is to rename it there.
  The LOA 3.5 cross-reference is not verified (Inferred).
- Reuse (Solution-Selection Ladder): the cell profiles and readers, `procs.run`, `ledger.SegmentWriter`,
  `status.build` / `require_known`, `workspace.check_cells_root`, `config.pack_marker_bytes`, `matcher.cache_key`,
  `html._e`, W3-EGRESS's `check`. No new dependency.

## 24. Decision requests and seam requests

All five decision requests are for the Owner. W3-GW-D proposes and does not decide.

- **DR-GW-1: the Codex judge is not tool-free on 0.156.0** (spike GW-H result 2).
  - **Facts:**
    - The code-mode `exec` tool stays advertised with every tool feature the probe disabled.
    - The model called it once per turn. It failed closed ("code-mode host is disabled"), per the CLI's own report.
    - It costs a second model call (about 9.3k input tokens) per judge call.
    - No measured flag removes it. R-58 c4 requires 0 tool calls.
    - The OpenAI subscription is at 99 % of its 7-day limit until `2026-09-29T20:03:15Z`, so any OpenAI option also
      waits for the reset.
  - **Options:**
    - **(a) Admit only a fail-closed `exec`,** matched on its output. Precondition: a hostile-payload re-probe on
      every build, requiring 0 side effects (§8.4). Residual risk: a build that enables the host; the pin and the
      re-probe gate that.
    - **(b) One judge for wave 3,** Claude Fable only. US-35's two vendors are unmet. Inter-judge κ and the vendor
      split are `not recorded`. Spec `:209` makes every judged score NOT_RECORDED unless the Owner also rules that a
      single verdict counts in wave 3.
    - **(c) A different second judge, spiked first.** Copilot CLI 1.0.89-1 serves `gpt-6-sol` and has
      `--available-tools`; an empty allowlist in print mode is unspiked (2 probe turns). xAI or Google CLIs are
      unspiked, and not the most capable per R-58 DR-1.
    - **(d) A time-boxed search** for a 0.156 switch or a newer pinned Codex build that drops `exec`. It touches the
      cells' pin (US-12), and no candidate is known.
  - W3-GW-D's reading: (c) Copilot is the cleanest if its allowlist works; (a) keeps two vendors with no execution
    as measured. The Owner decides.
- **DR-GW-2: "the oracle" in C1's judge input** (US-35 c1). Proposal: the rubric (C1's `task.yaml` names it the
  judge's oracle). No reference file is sent.
- **DR-GW-3: the rubric preamble and the freeze.** R-59 c2 wants the preamble; DR-5 and c5 freeze the file. Proposal:
  in wave 3 the catalog entry's `note:` carries the sentence; the rubric file gains it at C1's next task version.
- **DR-GW-4: the scope and meaning of "live"** (R-58 c3 says "phase `running`" and "under the cells root").
  - Proposal: refuse when any run is `alive` or `stalled`, where "any run" means every worktree's `runs/` plus
    `--runs` (§6).
  - A crashed run keeps its phase, so a phase-only check would refuse forever.
  - The cells root holds cell folders, not run ledgers.
  - Residual: a custom `--runs` folder outside every worktree.
- **DR-GW-5: the context each CLI adds after the gateway** (spike GW-H results 4–6). No flag the probe used removes
  it.
  - **Facts:**
    - Both CLIs add their own identity.
    - Claude adds the account e-mail and org UUID, on both measured text-mode turns (Inferred: every call).
    - Codex adds the operator's `~/.agents/skills` root (user name, home path) and 6 skills.
    - The same context already reaches the same vendor in every cell of that harness.
  - **Options:**
    - **(a) Read US-35 c1's "captured request" as the gateway-rendered request** (scanned before send). Detect and
      disclose the CLI-added classes. Accept in writing the e-mail to its own vendor and the skill root to OpenAI.
    - **(b) Treat any CLI-added identifier class as withheld.** Every Claude call and every Codex call becomes
      NOT_RECORDED: no jury at all.
    - **(c) A separate Windows user profile for the judges,** with new credentials. Emptying the operator's
      `~/.agents/skills` is rejected: it changes the real home and is lost on a crash (Security).
    - **(d) Spike a Claude setting that suppresses `session_context`.** None is known.
  - Proposal: (a); (c) if the Owner wants the Codex skill root gone.
  - **Until the ruling, no live judge pass runs.**
- **Seam requests:**
  - W3-GRADE-CORE: each judge entry in `catalog_hash`; `verdict_uses` in `PASS_FACTS`, `views.FACTS` and `KEYS`.
  - W3-GRADE-D: the C1 metric id and its aggregation.
  - W3-COST: the amendment number.
  - W2-STOP-I: `cmd_grade`'s flag.
  - W3-EGRESS: `check` is called on the request before `release`. Its `Verdict.classes` are reused, read-only, by the
    report-time detector.
  - The `procs.py` owner: `run(..., input=)`.
- **For the Leader (operational):** the OpenAI rate-limit state above bears on every Codex track.

## 25. Flagged risks and residual unknowns

- **OpenAI account at 99 % of its weekly limit until 2026-09-29T20:03Z** (spike GW-H). This matters for the OpenAI
  judge and every Codex track.
- **Not recorded:**
  - whether Codex advertises tools other than `exec`;
  - whether a Claude setting suppresses `session_context`;
  - host-side confirmation that Codex's `exec` executed nothing.
- **One probe turn per configuration.** The per-call checks (tools, served model) and the report-time detector are the
  standing controls.
- **The stdin and cells-root shape is not yet probed** (§8.4). It is the precondition of the first live pass.
- **ADR-0009:23 says ADR-0013 amends it,** but ADR-0013 has no gateway text (a one-sided link). This design follows
  the native process + Job Object model (Inferred).
- **Small samples:** 42 items per pass and 30 calibration items. κ and the vendor split are disclosed with n, never
  gated. US-46 c2 rests on one stored sample.
- **Self-preference** is measured, not removed (R-58 DR-1): 4 of 6 C1 cells are `gpt-6-sol`.

## 26. Status

| | |
| --- | --- |
| **Completed** | Probe and self-test; spike GW-H (five Leader turns; results committed without paths); this design, revision 3, through a two-round five-persona gate with every veto cleared by its holder (§27) |
| **Remaining** | Owner rulings DR-GW-1..5; the seams; the stdin/cells-root re-probe; W3-GW-I's slices and its Proof Pack; W3-CAL's items; the operator's 30 labels |
| **Best next action** | The Owner rules DR-GW-1 and DR-GW-5. W3-GW-I s1 needs neither ruling and can start on this design |

## 27. Gate record

`GATE design · 2026-09-25 · Patterns Expert, Simplifier, Test Architect (hard), Security & Identity (hard), Data &
Persistence (hard); all Adversary mode, model opus; author W3-GW-D did not self-clear · round 1 on revision 1:
Patterns CLEAR WITH CONDITIONS; Simplifier BLOCK (soft); Test Architect VETO; Security VETO; D&P VETO · revision 2
applies every finding below · re-check owed.`

| Reviewer · finding | Disposition in revision 2 |
| --- | --- |
| TA 1 (veto): R-58 c1, c2 untested | accepted: T-GW-27, 28, 29 |
| TA 2 (veto): live-run scope misses other worktrees | accepted: every worktree's `runs/` (§6); T-GW-19b; scope residual in DR-GW-4 |
| TA 3 (veto): key parts untested | accepted: T-GW-12b and named mutants |
| TA 4: mock fiction; export unpinned | accepted: the replay fake backend (§16); the `scores` export pinned; live 0-row proof |
| TA 5: label check was a count | accepted: set check (§11), T-GW-16, 16b |
| TA 6: weak κ tests; A6 | accepted: T-GW-17, 17b; stale binding |
| TA 7: detector by fixed row kinds | accepted: subtraction, `not recorded` on unparseable (§7.4); T-GW-24 |
| TA 8: A1 golden snapshot | accepted: T-GW-33 |
| TA 9a: "no canary" vacuous | accepted: marked Inferred (§8.4); the defence is `check_cells_root` |
| TA 9b: e-mail confounded with mode | accepted: reworded to "every text-mode call" (§7.4, §20, DR-GW-5) |
| TA 9c: "nothing executed" is the CLI's own report | accepted: labelled so (§8.4); the (a) rule matches output, not status |
| TA 10–14 | accepted: T-GW-11 bytes survive; T-GW-06 bytes and UTF-8; T-GW-03 property; T-GW-35; ids named |
| SEC 1 (veto): call folders under the repo's instruction files | accepted: cells-root folders + `check_cells_root` (§8.2); T-GW-26b; re-probe (§8.4) |
| SEC 2 (veto): unqualified tool-bearing judge still spawned | accepted: `qualified` gate, never spawned (§5, §8.4); T-GW-32; hostile re-probe precondition for DR-GW-1 (a) |
| SEC 3: credential gaps | accepted: copy inside `try`, sweep, `verify` error; T-GW-10 extended |
| SEC 4: records hold identifiers | accepted: `runs/` never published (spec `:572`); T-GW-34 |
| SEC 5: detector false "none" | accepted: subtraction; `not recorded` |
| SEC 6: planted entry | accepted: hit needs a matching storing row (§9.3); T-GW-13b |
| SEC 7: hostile argv | accepted: stdin (§8.1); T-GW-37; re-probe |
| SEC 8: accept by default before DR-GW-5; reject emptying skills | accepted: no live pass before the ruling; sub-option removed |
| SEC 9–11 | accepted: T-GW-36; token rotation in §18; secrets never logged (§7.4) |
| D&P 1 (veto): count, not set | accepted: set check (§11); T-GW-16 |
| D&P 2: enum misses paths | accepted, merged with Simplifier 1: `outcome` (5 values) + `code`; T-GW-30 |
| D&P 3: race loser | accepted: `race_lost`; `FileExistsError` only |
| D&P 4: item rows vs calls | accepted: `views.judge_calls`, guard test (§4.1) |
| D&P 5: entry cannot re-derive its key | accepted: `key_inputs`, `scrub_version`, pre-scrub hash; recipe in the ADR amendment; T-GW-31 |
| D&P 6: κ history; calibration store; live check for calibrate | accepted: `labels_sha256`, `calibration_uses`, refusal inside the gateway, `require_known` filter |
| D&P 7: `gateway.yaml` hashed twice | accepted: per-judge entry only; timeout in no key; check (b) cited; build pin in the YAML |
| D&P 8: Windows rename | accepted: `os.link`; read-only entries; stale tmp removal |
| D&P 9: key column renamed | accepted: `judge_or_matcher` kept |
| D&P 10: flags stored | accepted: derived (§10.3) |
| D&P 11: surface list gaps | accepted: §15 |
| Simplifier 1: enum and codes duplicate | accepted (with D&P 2) |
| Simplifier 2: `cli_context_classes` stored twice; nothing changes before DR-GW-5 | accepted: derived at report time; no column |
| Simplifier 3: in-run pass reads the store | accepted: R-58 DR-2 literal; no lookup, no rows |
| Simplifier 4: whole `gateway.yaml` in the key | accepted: `invocation_sha256` per judge |
| Simplifier 5: tamper check twice | partly: the in-pass comparison is removed; the storing-row check stays, because Security 6 (ADR-0012:39) needs it; the `verify` warning stays |
| Simplifier 6: injection flag stored | accepted: derived |
| Simplifier 7: §14 unsized | accepted: one paragraph; s6 reserved for GR-CLAR |
| Simplifier 8: `tool_events` and T-GW-25 before the ruling | accepted: built only if DR-GW-1 (a) |
| Simplifier 9: path scan because of `runs/` | accepted: cells root; one `egress.check` of the path stays (a custom cells root could hold a user name) |
| Simplifier 10: calibration ledger under `runs/` | defended: `require_known` skips it (T-GW-19c) |
| Simplifier 11: `backend:` key | accepted: removed |
| Patterns 1: key misses the system prompt and argv | accepted: `invocation_sha256` |
| Patterns 2: probe and production drift | accepted: one builder definition; the probe imports it at s2 |
| Patterns 3: Windows-only rename | accepted: `os.link` |
| Patterns 4: `egress.check` used as a detector | accepted: classes only; never an `egress_events` row |
| Patterns 5: circuit breaker | accepted: per judge per pass on rate or quota errors (§8.3); justified by the measured 99 % limit |
| Patterns 6: Self-Consistency misnamed | accepted: PoLL (§23); ADR-0009 follow-up |
| Patterns 7: "content-addressed" misnamed | accepted: request-keyed memo store |
| Patterns 8: shape defined twice | accepted: validator reads the schema file; T-GW-05b |
| Patterns 9: race loser recorded as `hit` | accepted: `race_lost` |
| Patterns 10: matcher key recipe | accepted: `matcher.cache_key` reused (§14) |
| Patterns 11: name the fence; pack-marker loader | accepted: spotlighting; order stated; `config.pack_marker_bytes` |

**Round 2 (the same reviewers, re-check of revision 2):**

`GATE design · 2026-09-25 · round 2 · Test Architect CLEARS WITH CONDITIONS · Security & Identity CLEARS WITH
CONDITIONS · Data & Persistence CLEARS WITH CONDITIONS · Simplifier CLEARS · Patterns CLEAR WITH CONDITIONS (round
1, all applied) · vetoes → resolution: all three hard vetoes cleared by their holders; the author did not
self-clear.`

| Round-2 condition | Applied in revision 3 (this text) |
| --- | --- |
| TA c1: A6 stale binding untested | T-GW-17c |
| TA c2: "every text-mode call" overstates n = 2 | reworded in §7.4, §20, DR-GW-5: "both measured text-mode turns (Inferred: every call)" |
| TA c3: T-GW-19b must use a real worktree | T-GW-19b builds one with `git worktree add` |
| TA c4: the Proof Pack at `/implement` | carried to W3-GW-I: red before green for every T-GW id; the mutation report for `gateway.json`; the live second pass with 0 `gateway` rows; the stdin re-probe record. The Test Architect's implementation veto stays open until it exists |
| SEC c1: a forged ledger vouches for a planted entry | §9.3: known roots only; the chain from genesis; a matching `gateway` `model_calls` row and archived record; T-GW-13c |
| SEC c2: the credential sweep hits a concurrent pass | §8.2: sweep only folders whose pass `.lock` is free; T-GW-10 extended |
| SEC c3: live preconditions | kept as absolute: the stdin/cells-root re-probe (§8.4) and a written DR-GW-5 ruling (§6) before the first live judge pass |
| D&P c1: a pruned storing ledger poisons the key | §9.3: orphaned, not forged; accepted from the run's own earlier row or an honest miss; moved to `orphaned/` under the flag; T-GW-13d |
| D&P c2: `race_lost` versus acceptance | §9.3: acceptance reads sealed segments only; `race_lost` accepts on `key_inputs` and served models; T-GW-11 |
| D&P c3: `calibration_uses` key and outcome | §4.4 |
| Simplifier advisory: merge `calibration_uses`; the breaker is one boolean inside `judge.py` | noted; D&P holds the merge choice; the breaker's shape is left to W3-GW-I, and one boolean per judge per pass is enough |

The round-2 conditions are design text and tests, applied above without a third review round. The Leader may ask for
one.

---
**Handoff:** → `/implement` (W3-GW-I). Slice s1 can start now. The live passes wait for the Owner's rulings on
DR-GW-1 and DR-GW-5 and for the re-probe.
