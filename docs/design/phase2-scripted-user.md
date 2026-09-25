---
id: "design-phase2-scripted-user"
title: "Design: the scripted user for scenario 1 (phase 2, row 8)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses (wave 2: row 8, the scripted user)"
tags: [benchmark, scenario-1, scripted-user, mcp, acp, matcher, clarification]
links:
  - { to: spec-harness-bench, rel: implements }
  - { to: arch-harness-bench, rel: implements }
  - { to: adr-0002-cell-driver, rel: refines }
  - { to: adr-0004-static-permissions, rel: depends-on }
  - { to: adr-0009-model-gateway, rel: depends-on }
  - { to: design-phase1-walking-skeleton, rel: refines }
  - { to: rulings-register, rel: depends-on }
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2027-03-25"
summary: >-
  The scenario-1 scripted user per R-37 and R-39: a bench-owned stdio MCP server exposing one tool,
  ask_user(question) -> reply, passed in ACP session/new mcpServers, one prompt per cell; a deterministic matcher
  (exact, then normalised; a miss gets exactly "Decide and state your assumption."); a per-call log with
  "no question asked" for zero calls; the "scripted user" allowlist class; the S-04 threshold from the held-out set.
  Draft revision 1 (phase A): every measured fact is marked "pending S-04" until the Leader's probe turns return.
review-suggested: []
---

# Design: the scripted user for scenario 1 (phase 2, row 8)

**Track:** W2-USER-D (plan v4, `docs/coordination/coordination-finish-harness-bench.md:160`). **Implemented by:** W2-USER-M (matcher and responder, `src/harness_bench/scripted_user/**`) and W2-USER-W (wiring into `driver.py`, `engine.py`, `profiles.py`, `bench/profiles/*.yaml`). **Rulings:** R-37 (mechanism), R-39 (matcher), R-33 (models stipulated), R-34 (class rule). **History:** revision 1, phase A: the draft. Phase B fills every `pending S-04` marker from the probe's results, adds the reviewer's verdict and the spike note.

**Confidence labels.** *Verified*: observed in this repo, the pinned builds or a run. *Inferred*: reasoned, with what would confirm it. *Pending S-04*: to be measured by the probe (section 11), never filled from memory.

## 1. Goal and scope

A scenario-1 cell (`scenario: 1`, `scripted_user: true`; A1 today, `tasks/A1/task.yaml:24`) may ask the user questions. The bench answers each one in the same prompt turn, from the task's annotated clarifications only, and logs every call. Grading (US-31) reads the log.

- **In scope:** the mechanism per harness, the matcher tiers and normalisation, the S-04 threshold, `matcher_version` and the cache key, the log format, the allowlist class, and the seams W2-USER-W needs.
- **Not in scope:** a model rung (R-39: none before the ADR-0009 gateway, wave 3); multi-turn (R-37: rejected for wave 2); the `clarify` grader (S-08d); tasks other than A1.

## 2. Rulings and promises bound here

| Source | Clause | Where this design meets it |
| --- | --- | --- |
| R-37 | one `session/prompt`; a bench-owned stdio MCP server in `session/new` `mcpServers`; one tool `ask_user(question) → reply` | §4 |
| R-37 | the reply is a matched clarification's text or exactly `Decide and state your assumption.` | §6 |
| R-37 c1 | per harness, on the pinned builds: the accepted `mcpServers` shape, the tool in the native record, whether one A1 turn calls it; a harness the tool never reaches returns as a decision request | §4.3, §11 |
| R-37 c2 | the tool id joins each allowlist as the class "scripted user" under R-34's class rule; Copilot's `--disable-builtin-mcps` does not drop a session-supplied server | §5 |
| R-37 c3 | the server only when the task has `scripted_user: true`; every other cell keeps `mcpServers: []` | §9, test T-37-3 |
| R-37 c4 | the log records question, decision and reply per call; zero calls record "no question asked", never an empty file | §8 |
| R-37 c5 | `prompt.md` may name the tool; the text is identical across combos | §9 (Verified for A1: `tasks/A1/prompt.md:3`) |
| R-39 | exact and normalised match only; a miss sends the default reply and is recorded | §6, §7 |
| R-39 c1 | the S-04 threshold from the held-out measurement, numbers in the spike note; spec R10 closes by citation | §10 |
| R-39 c2 | the held-out and near-miss sets are authored by TASKS-a, not by the matcher's author | §10 (Verified: `tasks/A1/oracle/heldout_questions.yaml:2`) |
| R-39 c3 | `matcher_version` on every match; cache key (question hash, matcher version); a re-grade makes no new match | §7.3 |
| R-39 c4 | normalisation is one function with a test per rule; nothing fuzzy | §7.2 |
| US-10 (`harness-bench.md:354`) | each reply is an annotated clarification's text or exactly the default; the log records question, match decision, reply | §6, §8 |
| US-31 (`harness-bench.md:456-458`) | recall, precision, ask-versus-assume from the log; matcher qualified on a labelled set; below the S-04 threshold, `low-confidence matcher`; a re-grade reuses the cached match | §7.3, §10 |
| US-46 (`harness-bench.md:487-490`) | a matcher that calls a model is tool-less, schema-bound, and sees agent text only as data | N/A in wave 2: the matcher calls no model (R-39) |

## 3. Domain model

Bounded context: **clarification** (part of cell execution; read by grading). Ubiquitous language: *question* (the `question` argument of one `ask_user` call, verbatim), *clarification* (an annotated entry in `oracle/clarifications.yaml`, `bench-clarifications/1`), *match decision*, *reply*, *default reply*.

- **Clarification set** (value object, per task version): `default_reply` plus `clarifications[]` (`id`, `question`, `reply`, …). Identity is its file hash. It never changes inside a run.
- **Clarification match** (aggregate, spec `:210`, invariant `:245`): key = (question hash, matcher version); value = the decision. **Invariant:** the same key always yields the same stored decision. With a deterministic matcher the invariant also holds by construction; the store makes it hold for any later matcher version too.
- **Match decision** (value object): `{clarification: <id> | null, rung: "exact" | "normalised" | "none"}`. `null` with rung `none` means the default reply.
- **Scripted-user call** (fact, append-only). **Grain: one row is exactly one `ask_user` call in one cell.** Columns: sequence number, time, question, question hash, decision, reply, matcher version. Measures: none additive per row; the grader counts rows (asked), distinct matched ids (recall numerator) and matched rows (precision numerator).
- **History rule:** nothing is updated. A re-grade reads the stored decisions; it never re-matches (US-31 `:458`).
- **Derived, never stored:** recall, precision, ask-versus-assume (the grader computes them from the rows).

## 4. Mechanism (R-37)

### 4.1 Shape

One stdio MCP server per scenario-1 cell, started by the harness from the entry the driver puts in `session/new` `mcpServers` (today `[]`, `src/harness_bench/driver.py:236`). The entry is the ACP `McpServerStdio` shape: `{name, command, args, env: [{name, value}]}`, with **no `type` field**.

- *Verified*, ACP schema in the pinned SDK (`@agentclientprotocol/sdk/schema/schema.json`, `McpServerStdio`): `name`, `command` (absolute path), `args`, `env` are all required. The schema marks `mcpServers` items `x-deserialize-skip-invalid-items`.
- *Verified*, `claude-agent-acp` 0.81.2 `dist/acp-agent.js:6214-6239`: an entry with no `type` becomes an SDK stdio server keyed by `name`; `http` and `sse` are the only typed entries it maps. An entry with `type: "stdio"` is **silently dropped**.
- *Verified*, `codex-acp` 1.12.0 `dist/index.js:19535-19557`: `mcpServers` is parsed with `vecSkipError`, so an entry that fails the schema is **skipped without an error**. `:28710-28728` writes the accepted entries into the thread config's `mcp_servers`, and `:32660-32665` publishes an MCP startup status per requested server as session updates.
- *Pending S-04*: Copilot 1.0.89-1 is native ACP (no adapter source to read). Whether it accepts the entry, starts the server, and lists the tool.

**Consequence (Verified from the two adapters' code):** a malformed entry does not fail `session/new`; it vanishes. So "the adapter accepted the shape" is proven only by the server's own log (a `start` record, then `initialize` and `tools/list`), never by `session/new` returning a session. The probe measures exactly that, and T-37-1b below makes it a standing check.

- **Server name:** `scripted_user` (an underscore: the name becomes part of each harness's tool id).
- **Command:** the bench's own Python interpreter, by absolute path; **args:** the server module plus the cell's inputs (clarifications path, log path). *Inferred:* passing the log path as an argument as well as by `env` is safe whether or not an adapter forwards the ACP `env` list; the probe records which one arrived (`log_source`). *Pending S-04* per harness.
- **Lifetime:** the harness starts the server as its own child, so it runs inside the cell's Job Object, which is kill-on-close with breakaway never allowed (`src/harness_bench/procs.py:8`). *Inferred:* the server dies with the cell and needs no cleanup of its own. Confirm: after a probe turn no `probe_server.py` process survives.

### 4.2 Why this does not touch the lifecycle

The tool call is answered inside the one prompt, so `AT_MOST_ONCE` (`lifecycle.py:21`, R-37), the end-of-turn kill and R-21's grace are unchanged. The MCP traffic runs harness ↔ server and never crosses the ACP channel. So the driver's refusal of client requests (`driver.py:174-179`) and its discarding of agent text (`driver.py:180-184`) need no change. *Inferred* from the transport: the server is a stdio child of the harness, not an ACP-transport MCP server (`McpServerAcp`, which is UNSTABLE in the schema and not used). Confirm: the probe recordings show no `mcp/*` ACP method.

### 4.3 Per harness (R-37 c1)

| Harness · pinned build · model (R-33) | `mcpServers` shape accepted | Server started / listed | Tool in the native record | Model called it (probe prompt) | One A1 turn called it | Reply reached the model |
| --- | --- | --- | --- | --- | --- | --- |
| claude-code · Claude Code 2.1.282 via `claude-agent-acp` 0.81.2 · `claude-opus-5-5` | stdio, no `type` (Verified from source); run: *pending S-04* | *pending S-04* | *pending S-04* | *pending S-04* | *pending S-04* | *pending S-04* |
| codex · Codex 0.156.0 via `codex-acp` 1.12.0 · `gpt-6-sol` | stdio, no `type` (Verified from source); run: *pending S-04* | *pending S-04* | *pending S-04* | *pending S-04* | *pending S-04* | *pending S-04* |
| copilot · Copilot 1.0.89-1, native ACP · `gpt-6-sol` | *pending S-04* | *pending S-04* | *pending S-04* | *pending S-04* | *pending S-04* | *pending S-04* |

A harness the tool never reaches returns as a decision request (R-37 c1). Nobody switches that harness to multi-turn alone.

## 5. The allowlist class "scripted user" (R-37 c2, R-34)

ADR-0004's classes are platform-independent and their ids are per build (R-34). This adds a third class, **scripted user**, with one tool per harness:

| Harness | Mechanism | Id | Status |
| --- | --- | --- | --- |
| claude-code | `permissions.allow` in the seeded `settings.json` (`bench/profiles/claude-code.yaml:14`) | `mcp__scripted_user__ask_user` | *assume:* Claude Code names an MCP tool `mcp__<server>__<tool>` · confirm: the account connectors in this repo's records are `mcp__claude_ai_<Name>__<tool>` (R-36), and the probe's native record lists the id · breaks: the call becomes a permission request, refused by the driver and recorded with its title. *Pending S-04* |
| codex | none: `agent-full-access` (approval `never`) already covers MCP tool calls | — | *Pending S-04*: the probe records any permission request the call raises |
| copilot | `--allow-tool scripted_user` in the profile's `command` (`bench/profiles/copilot.yaml:7`) | `scripted_user` (the server; its one tool) | *Verified* syntax from `copilot --help` on 1.0.89-1: `--allow-tool='MyMCP'` allows a server's tools. *Pending S-04* |

- The class coverage test (R-34 c2, `tests/test_allowlist_classes.py`) lists the id per harness, read from the build's record (the probe's native record), never from memory.
- **Deferred tools (R-35 c3):** if Claude Code defers MCP tools behind `ToolSearch`, the model must call `ToolSearch` first, and `ToolSearch` is not on the allowlist. *Pending S-04:* the probe lists every permission request's title, so a `ToolSearch` gate shows by name.
- **Symmetry (US-14):** the server is identical for every harness and both pack settings; only the id that allows it differs, as for the shell class.

**Copilot `--disable-builtin-mcps` (R-37 c2).** Finding, *Verified*: ADR-0004:58 lists the flag, but the Copilot profile does not carry it (`bench/profiles/copilot.yaml:7` is `--acp --model {model} --allow-tool shell --allow-tool write`). The pinned `--help` says the flag disables "all built-in MCP servers (currently: github-mcp-server)". So a Copilot cell today may have the GitHub MCP server, which ADR-0004:51 bars. That gap is not this track's to fix; it is reported to the Leader. For R-37 c2 the probe runs Copilot **with** the flag appended, so a server that is listed and called under it is the proof that the flag does not drop a session-supplied server. *Pending S-04.*

## 6. The responder

- On `tools/call ask_user {question}`: match (§7), then reply with the matched clarification's `reply` verbatim, or with `default_reply` verbatim (`Decide and state your assumption.`, `tasks/A1/oracle/clarifications.yaml:14`). The reply is the only content item, `type: "text"`, `isError: false`.
- Every call is answered, any number of calls; each is one log row. A question that is not a string, or is empty, gets the default reply and is logged with decision `none` (*Inferred* safest: an error reply would leak nothing but would differ by harness in how it is shown).
- The server exposes no other tool, resource or prompt. `initialize` declares `tools` only.
- Synchronous: the match is a pure function, so no decision request opens mid-turn (R-37 reasoning).

## 7. The matcher (R-39)

### 7.1 Tiers

1. **Exact:** the question equals an annotated `question`, byte for byte after UTF-8 decoding.
2. **Normalised:** `normalise(question) == normalise(annotated)` for one clarification.
3. **None:** the default reply.

No partial, token-overlap or edit-distance rung: "nothing fuzzy" (R-39 c4). If two clarifications normalise to the same text, the task is invalid; `bench validate` rejects it (test T-39-4c).

### 7.2 Normalisation: one function, one test per rule

`normalise(text) -> str` applies these rules in this order. Each rule is a named entry in one table in the module, and each has its own test (a pair that it joins and a near pair that it must keep apart).

| # | Rule | Joins | Keeps apart |
| --- | --- | --- | --- |
| N1 | Unicode NFKC | full-width and compatibility forms | — |
| N2 | curly quotes and apostrophes to straight (`“ ” „ ‟ ‘ ’ ‚ ‛` → `" '`) | `“find the sum”` = `"find the sum"` | — |
| N3 | case fold (`str.casefold`) | `Does` = `does` | — |
| N4 | whitespace: strip both ends, collapse every run of whitespace to one space | `the  sum ` = `the sum` | — |
| N5 | drop trailing sentence punctuation (`? . !` and spaces after them) | `…total value?` = `…total value` | punctuation inside the text stays |

**Provenance of the rule set, disclosed:** the rules are the standard surface normalisations. The author of this design read the held-out file's `kind` legend and its `transform` labels (quotes, case, punctuation, whitespace) but did not use its questions to choose or tune a rule. The matcher's author (W2-USER-M) implements the table as written and must not read the held-out questions (R-39 c2).

### 7.3 `matcher_version` and the cache key

- `matcher_version = "t0-" + sha256(canonical JSON of the rule table and the tier list)[:12]`. A test recomputes it from the table, so a rule change without a new version fails (T-39-3a).
- **Question hash:** `sha256` of the question as received, UTF-8. **Cache key:** (question hash, matcher version) (spec `:210`, `:245`).
- **Store:** in wave 2 the cell's log (§8) is the store. Each call row carries the key and the decision. A re-grade reads the rows and never calls the matcher (T-39-3b). *Inferred:* no cross-cell cache is needed while the matcher is a pure function; the key is recorded now so the wave-3 gateway cache (ADR-0009) can adopt the rows unchanged.

## 8. The log (R-37 c4, US-10)

One file per scenario-1 cell: `<cell_dir>/scripted-user.jsonl`, schema `bench-scripted-user-log/1`. It is archived with the cell (spec `:199`, "scripted-user log").

```
{"kind":"header","schema":"bench-scripted-user-log/1","task":"A1","clarifications_sha256":"…","matcher_version":"t0-…"}
{"kind":"call","seq":1,"t":12.4,"question":"…","question_sha256":"…","decision":{"clarification":"goal-maximum","rung":"normalised"},"reply":"…","matcher_version":"t0-…"}
{"kind":"end","calls":1}
{"kind":"end","calls":0,"note":"no question asked"}      (the zero-call form)
```

- The server writes `header` at start and one `call` row per call, flushed before the reply is sent. So a row is never missing for a reply the agent saw.
- The **engine** writes `end` after the turn, from the rows it finds, because a server that never started writes nothing. With no file, or no `call` row, it writes the header (from the plan) and `{"kind":"end","calls":0,"note":"no question asked"}`. The file is never empty and never absent for a scenario-1 cell (T-37-4a, T-37-4b).
- If the header is missing (the server never started), the `end` row also carries `"server_started": false`. That separates "the agent asked nothing" from "the agent could not ask". *Pending S-04:* whether any harness starts the server lazily, which decides how often that form appears.

## 9. Seams for W2-USER-W

Phase A lists them by file. Phase B states each as `file:line` against the code as merged, after S-04.

- `src/harness_bench/driver.py:236`: `run_turn` gains `mcp_servers: list[dict] | None = None` and sends it (default `[]`). T-37-3 asserts both forms.
- `src/harness_bench/engine.py:415-417`: `_attempt` passes the task's server entry when the plan's task has `scripted_user: true`, and writes the log's `end` row after the turn (§8).
- `src/harness_bench/plan.py:129-132` (`_prompt`) and the plan's task record: carry `scripted_user` and the clarifications hash, so the plan freezes them.
- `src/harness_bench/profiles.py:60-97`: the profile adds the class's id (Claude `settings.json` allow; Copilot argv), from the profile YAML, not from code.
- `bench/profiles/claude-code.yaml:14`, `bench/profiles/copilot.yaml:7`: the ids of §5. `codex.yaml`: none.
- `src/harness_bench/config.py:166-167` already requires `scripted_user: true` for scenario 1 (Verified).

## 10. The S-04 threshold (R-39 c1, US-31, spec R10)

**Held-out set** (*Verified*, `tasks/A1/oracle/heldout_questions.yaml`, authored by W2-TASKS-a): 38 questions. 17 are labelled `goal-maximum` (1 exact, 5 normalised, 10 paraphrase, 1 compound) and 21 are labelled `default` (15 near-miss, 6 off-topic).

**Measurement design.** Run the W2-USER-M matcher, as built, over all 38 once. Report per `kind` and overall:
- precision = correct matches ÷ matches;
- recall = correct matches ÷ 17;
- the near-miss false-match count.

The numbers go in the spike note (`docs/notes/spike-s04-scripted-user.md`, phase B).

**Threshold rule (draft):**
- Precision must be 1.0, with zero near-miss matches. A false match hands a clarification to a question that did not ask it, which inflates correctness. So a matcher below 1.0 fails qualification outright.
- Recall on `exact` + `normalised` must be 1.0, since those are the rungs R-39 defines.
- Overall held-out recall is reported. Below **T = pending S-04**, the clarification metrics show `low-confidence matcher` (US-31 `:457`).

*Inferred, disclosed now:* by construction, a deterministic matcher can match at most the 6 exact and normalised questions of the 17. So overall recall is at most 6/17 ≈ 0.35 unless a paraphrase normalises to the annotation. Every A1 cell may therefore carry `low-confidence matcher` in wave 2. R-39 accepts that label as "a measurement, not a failure". The responder-side consequence is raised to the Leader in §13.

## 11. Spike S-04: the probe

`tests/fixtures/acp/scripted-user/`:
- `probe_server.py`: a stdlib stdio MCP server with one tool `ask_user`. It gives a fixed reply and logs every message it receives and sends, to the file named by `SCRIPTED_USER_PROBE_LOG` (else `--log`).
- `probe_turn.py run`: one turn per harness, built as `tools/acp_record.py turn` builds one (profile, pinned build, working copy, the `record` tee, `driver.run_turn`), with `session/new` carrying the probe server. It writes the recording, the server log and a summary of the R-37 c1 facts. `--handshake-only` stops before the prompt (no model turn). `--prompt a1` sends A1's prompt verbatim.
- `probe_selftest.py`: the offline self-test: the server over real pipes, the analysis on synthetic files, and the channel swap.

The Leader runs the probe (a seam: live model turns). The results fill §4.3, §5 and §10.

## 12. Promise → test table

Tests are named for W2-USER-M (`tests/test_scripted_user.py`) and W2-USER-W (`tests/test_driver.py`, `tests/test_engine.py`, `tests/test_allowlist_classes.py`). Each is red first.

| Promise | Test | Owner |
| --- | --- | --- |
| R-37: one tool, `ask_user(question)`; `initialize` declares tools only | T-37-0 `test_server_lists_exactly_ask_user` | USER-M |
| R-37 / US-10: the reply is the matched `reply` or exactly the default | T-37-R `test_reply_is_clarification_text_or_exact_default` | USER-M |
| R-37 c1: per harness, shape accepted, tool in the native record, A1 turn calls it | S-04 probe summaries, cited in the spike note; T-37-1a `test_mcp_server_entry_is_stdio_without_type` | USER-D (spike), USER-W |
| R-37 c1: a dropped entry is visible, never silent | T-37-1b `test_server_not_started_is_recorded` (engine: no header → `server_started: false`) | USER-W |
| R-37 c2: the id is in each allowlist as the class "scripted user" | T-37-2a `test_allowlist_covers_scripted_user_class` (in `test_allowlist_classes.py`) | USER-W |
| R-37 c2: `--disable-builtin-mcps` does not drop the session server | S-04 Copilot probe with the flag; T-37-2b `test_copilot_profile_disables_builtin_mcps` if the profile gains it | USER-D (spike), USER-W |
| R-37 c3: the server only with `scripted_user: true`; else `mcpServers: []` | T-37-3 `test_mcp_servers_only_for_scripted_user_tasks` (both forms) | USER-W |
| R-37 c4: question, decision, reply per call | T-37-4a `test_log_row_per_call_before_reply` | USER-M |
| R-37 c4: zero calls → "no question asked", never an empty file | T-37-4b `test_zero_calls_writes_no_question_asked` | USER-W |
| R-37 c5: the prompt is identical across combos | existing US-10 hash test (`plan._prompt`), plus T-37-5 `test_a1_prompt_names_ask_user` | USER-W |
| R-39: exact, then normalised, then default; nothing else | T-39-0 `test_tiers_exact_normalised_default_only` | USER-M |
| R-39 c1: the threshold is set from the held-out measurement | T-39-1 `test_matcher_meets_s04_threshold_on_heldout` (reads the numbers, never tunes) | USER-M |
| R-39 c2: the held-out set is not the matcher author's | provenance header check, T-39-2 `test_heldout_authored_by_tasks_track` | USER-M |
| R-39 c3: `matcher_version` on every match | T-39-3a `test_matcher_version_is_hash_of_rule_table` | USER-M |
| R-39 c3: cache key (question hash, matcher version); a re-grade makes no new match | T-39-3b `test_regrade_reads_stored_decisions` | USER-M |
| R-39 c4: one function, a test per rule | T-39-4-N1 … T-39-4-N5 (join and keep-apart per rule) | USER-M |
| R-39 c4: nothing fuzzy; near-misses get the default | T-39-4b `test_near_misses_get_default_reply`; T-39-4c `test_ambiguous_clarifications_rejected` | USER-M |
| US-31: recall, precision, ask-versus-assume from the log | S-08d (`grade/clarify.py`), out of scope here | — |

## 13. Open items and the decision request

- **DR candidate: the responder shares the matcher's recall ceiling (Inferred).** Under R-39, a paraphrased right question gets `Decide and state your assumption.`. So in wave 2 an A1 agent that asks the right question in its own words gets no answer, and A1's hidden tests then measure whether it guessed "maximum", not whether it clarified. R-39 ruled on the *grading* label; this is the *reply*. Options:
  - (a) accept, and disclose it in the report header beside `low-confidence matcher`;
  - (b) hold the A1 cells' correctness as `NOT_RECORDED` for scenario-1 analysis until the wave-3 rung;
  - (c) no change now; S-04 measures how often live questions match, and the Owner rules then.

  This design's default is (c): the probe's A1 turns measure it.
- All `pending S-04` markers in §4.3, §5, §8 and §10.
- The Copilot profile / ADR-0004:58 gap (§5): reported, not fixed here.
