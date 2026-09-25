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
  - { to: note-spike-s04-scripted-user, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2027-03-25"
summary: >-
  The scenario-1 scripted user per R-37 and R-39: a bench-owned MCP server exposing one tool,
  ask_user(question) -> reply, passed in ACP session/new mcpServers, one prompt per cell; a deterministic matcher
  (exact, then five normalisation rules; a miss gets exactly "Decide and state your assumption."); a per-call log
  with "no question asked" for zero calls; the "scripted user" allowlist class; the seams for W2-USER-W. Revision 2
  after spike S-04: stdio works on Claude Code and Codex (Verified); Copilot 1.0.89-1 rejects client stdio servers
  (a decision request, with HTTP and launch-config variants written); the rule table scores precision 1.0 and recall
  6/17 on the held-out set (0/11 on paraphrases); the S-04 threshold is set (regression floor met; confidence
  T = 0.80 on paraphrase recall not met). AI Systems Engineer: CLEAR WITH CONDITIONS, conditions applied.
review-suggested: []
---

# Design: the scripted user for scenario 1 (phase 2, row 8)

**Track:** W2-USER-D (plan v4, `docs/coordination/coordination-finish-harness-bench.md:160`). **Implemented by:**
- W2-USER-M: the matcher and responder, `src/harness_bench/scripted_user/**`;
- W2-USER-W: the wiring into `driver.py`, `engine.py`, `profiles.py` and `bench/profiles/*.yaml`.

**Rulings:** R-37 (mechanism), R-39 (matcher), R-33 (models stipulated), R-34 (class rule). **Evidence:** spike S-04, `docs/notes/spike-s04-scripted-user.md` and `tests/fixtures/acp/scripted-user/s04-results.json`.

**History:**
- revision 1, `dda9f62`: the draft, with the measured facts marked pending;
- revision 2: this one. It records the S-04 measurements and the threshold, the Copilot decision request, and the AI Systems Engineer's review (§14).

**Confidence labels.**
- *Verified*: observed in this repo, in the pinned builds, or in a run.
- *Inferred*: reasoned, with what would confirm it.
- *Pending S-04b*: measured by the further variants (spike note), never filled from memory.

## 1. Goal and scope

A scenario-1 cell (`scenario: 1`, `scripted_user: true`; A1 today, `tasks/A1/task.yaml:24`) may ask the user questions. The bench answers each question in the same prompt turn, from the task's annotated clarifications only, and logs every call. Grading (US-31) reads the log.

- **In scope:** the mechanism per harness, the matcher tiers and normalisation, the S-04 threshold, `matcher_version` and the cache key, the log format, the allowlist class, and the seams W2-USER-W needs.
- **Not in scope:** a model rung (R-39: none before the ADR-0009 gateway, wave 3); multi-turn (R-37: rejected for wave 2); the `clarify` grader (S-08d); tasks other than A1; the Copilot profile's missing `--disable-builtin-mcps` (the Owner is ruling on it separately; cited in §5).

## 2. Rulings and promises bound here

| Source | Clause | Where this design meets it |
| --- | --- | --- |
| R-37 | one `session/prompt`; a bench-owned stdio MCP server in `session/new` `mcpServers`; one tool `ask_user(question) → reply` | §4 |
| R-37 | the reply is a matched clarification's text or exactly `Decide and state your assumption.` | §6 |
| R-37 c1 | per harness, on the pinned builds: the `mcpServers` shape accepted, the tool in the native record, whether one A1 turn calls it; a harness the tool never reaches returns as a decision request | §4.3; DR-S04-1 in §13 |
| R-37 c2 | the tool id joins each allowlist as the class "scripted user" under R-34's class rule; Copilot's `--disable-builtin-mcps` does not drop a session-supplied server | §5 |
| R-37 c3 | the server only when the task has `scripted_user: true`; every other cell keeps `mcpServers: []` | §9, T-37-3 |
| R-37 c4 | the log records question, decision and reply per call; zero calls record "no question asked", never an empty file | §8 |
| R-37 c5 | `prompt.md` may name the tool; the text is identical across combos | §9 (Verified for A1: `tasks/A1/prompt.md:3`) |
| R-39 | exact and normalised match only; a miss sends the default reply and is recorded | §6, §7 |
| R-39 c1 | the S-04 threshold from the held-out measurement, numbers in the spike note; spec R10 closes by citation | §10 |
| R-39 c2 | the held-out and near-miss sets are authored by TASKS-a, not by the matcher's author | §10 (Verified: `tasks/A1/oracle/heldout_questions.yaml:2`) |
| R-39 c3 | `matcher_version` on every match; cache key (question hash, matcher version); a re-grade makes no new match | §7.3 |
| R-39 c4 | normalisation is one function with a test per rule; nothing fuzzy | §7.2 |
| US-10 (`harness-bench.md:354`) | each reply is an annotated clarification's text or exactly the default; the log records question, match decision, reply | §6, §8 |
| US-31 (`harness-bench.md:456-458`) | recall, precision, ask-versus-assume from the log; the matcher qualified on a labelled set; below the S-04 threshold, `low-confidence matcher`; a re-grade reuses the cached match | §7.3, §10 |
| US-46 (`harness-bench.md:487-490`) | a matcher that calls a model is tool-less, schema-bound, and sees agent text only as data | N/A in wave 2: the matcher calls no model (R-39) |

## 3. Domain model

Bounded context: **clarification** (part of cell execution; read by grading). Ubiquitous language: *question* (the `question` argument of one `ask_user` call, verbatim), *clarification* (an annotated entry in `oracle/clarifications.yaml`, `bench-clarifications/1`), *match decision*, *reply*, *default reply*.

- **Clarification set** (value object, per task version): `default_reply` plus `clarifications[]` (`id`, `question`, `reply`, …). Its identity is its file hash. It never changes inside a run.
- **Clarification match** (aggregate; spec `:210`, invariant `:245`).
  - **Key:** (question hash, clarification-set hash, matcher version). The value is the decision.
  - **Invariant:** the same key always yields the same stored decision.
  - The spec's key omits the clarification set. The same question gets a different decision under another task, or under an edited `clarifications.yaml`. So the spec's invariant is false as written, and a spec amendment is requested (§13, DR-S04-3).
- **Match decision** (value object): `{clarification: <id> | null, rung: "exact" | "normalised" | "none"}`. `null` with rung `none` means the default reply.
- **Scripted-user call** (fact, append-only). **Grain: one row is exactly one `ask_user` call in one cell.**
  - Columns: sequence number, time, question, question hash, decision, reply, matcher version.
  - No measure is additive per row. The grader counts rows (asked), distinct matched ids (the recall numerator) and matched rows (the precision numerator).
- **History rule:** nothing is updated. A re-grade reads the stored decisions and never re-matches (US-31 `:458`).
- **Derived, never stored:** recall, precision, ask-versus-assume.

## 4. Mechanism (R-37)

### 4.1 Shape

One MCP server per scenario-1 cell. The harness learns of it from the entry the driver puts in `session/new` `mcpServers` (today `[]`, `src/harness_bench/driver.py:236`). For Claude Code and Codex, the entry is the ACP `McpServerStdio` shape, `{name, command, args, env: [{name, value}]}`, with **no `type` field**.

- *Verified*, ACP schema in the pinned SDK (`McpServerStdio`): `name`, `command` (an absolute path), `args` and `env` are all required. The items are `x-deserialize-skip-invalid-items`.
- *Verified*, `claude-agent-acp` 0.81.2 `dist/acp-agent.js:6214-6239`: an entry with no `type` becomes an SDK stdio server. An entry with `type: "stdio"` is **silently dropped**.
- *Verified*, `codex-acp` 1.12.0 `dist/index.js:19535-19557`: a malformed entry is skipped (`vecSkipError`) with no error.
- *Verified*, S-04: Copilot 1.0.89-1 logs `Rejecting non-http/sse MCP server "scripted_user" from client` and still returns a session. It advertises `mcpCapabilities: {http: true, sse: true}`. The rejection is identical in 5 of 5 runs, with and without `--disable-builtin-mcps`.

**Consequence:** in all three harnesses, a server that does not reach the agent does not fail `session/new`. A process start is not proof either, because under HTTP (DR-S04-1) the engine starts the server itself.

The proof is the server's own rows (§8): `initialize` from the harness's MCP client, then `tools/list`. The engine records `tool_listed: false` when the `tools_listed` row is missing (T-37-1b). Clarification metrics are then NOT_RECORDED.

- **Server name:** `scripted_user` (an underscore: the name becomes part of each harness's tool id).
- **Command:** the bench's own Python interpreter, by absolute path. **Args:** the server module, the clarifications path, the log path. **Env:** `SCRIPTED_USER_LOG` (the log path, again).
  - *Verified*, S-04: both Claude Code and Codex forwarded the ACP `env` list (`log_source: env`, 6 of 6 runs).
  - The argument stays as a fallback: it costs nothing and removes a dependency on the adapter.
- **Lifetime.**
  - *Verified*, by an operator check after the runs; not in the committed results: no probe server survived all eleven runs, and no server log ended in `eof`.
  - *Inferred*: the server ran inside the cell's Job Object (kill-on-close, no breakaway, `src/harness_bench/procs.py:8`) and was killed with the cell. The same evidence fits an adapter that ends its own children.
  - Either way, the server is not given a clean EOF. So it must flush each row before it replies, and it cannot write a closing row itself (§8).

### 4.2 Why this does not touch the lifecycle

The tool call is answered inside the one prompt. So `AT_MOST_ONCE` (`lifecycle.py:21`, R-37), the end-of-turn kill and R-21's grace are unchanged.

The MCP traffic runs harness ↔ server and never crosses the ACP channel. So the driver's refusal of client requests (`driver.py:174-179`) and its discarding of agent text (`driver.py:180-184`) need no change. Evidence:
- No run had a permission request: *Verified* in `s04-results.json`.
- No S-04 recording has an `mcp/*` ACP method: *Verified* by reading the raw recordings, which are not committed.

### 4.3 Per harness (R-37 c1): measured

| Harness · pinned build · model (R-33) | `mcpServers` shape accepted | Server started / listed | Tool in the native record | Called (probe prompt) | One A1 turn called it | Reply reached the model |
| --- | --- | --- | --- | --- | --- | --- |
| claude-code · Claude Code 2.1.282 via `claude-agent-acp` 0.81.2 · `claude-opus-5-5` | stdio, no `type`: **yes** | yes / yes (3/3) | yes, `mcp__scripted_user__ask_user` | yes | **yes, 1 question** | yes (the token in its text) |
| codex · Codex 0.156.0 via `codex-acp` 1.12.0 · `gpt-6-sol` | stdio, no `type`: **yes** | yes / yes (3/3) | yes when called, `mcp__scripted_user__ask_user` (the rollout does not record tool definitions) | yes | **no** (listed, not called) | yes |
| copilot · Copilot 1.0.89-1, native ACP · `gpt-6-sol` | stdio: **rejected** (Copilot log). http: *pending S-04b* | no / no (0/5) | no | no ("the tool isn't available") | no (could not) | — |

Copilot is a harness the tool never reaches over stdio. It returns as **DR-S04-1** (§13). Nobody switches it to multi-turn alone.

## 5. The allowlist class "scripted user" (R-37 c2, R-34)

ADR-0004's classes are platform-independent, and their ids are per build (R-34). This design adds a third class, **scripted user**, with one tool per harness:

| Harness | Mechanism | Id | Evidence |
| --- | --- | --- | --- |
| claude-code | `permissions.allow` in the seeded `settings.json` (`bench/profiles/claude-code.yaml:14`) | `mcp__scripted_user__ask_user` | *Verified* (S-04): the id in the native record and the ACP title; 0 permission requests with it allowed |
| codex | none: `agent-full-access` (approval `never`) covers MCP tool calls | native `mcp__scripted_user__ask_user`; ACP title `mcp.scripted_user.ask_user` | *Verified* (S-04): 0 permission requests |
| copilot | `--allow-tool scripted_user` in the profile's `command` (`bench/profiles/copilot.yaml:7`) | `scripted_user` (the server's tools) | Syntax *Verified* from `copilot --help` 1.0.89-1. Effect *pending S-04b*, because the tool has not yet reached Copilot |

- **The coverage test.** The class coverage test (R-34 c2, `tests/test_allowlist_classes.py`) lists the Claude id, read from a native record of the pinned build (a scrubbed cut of the S-04 record), never from memory. A build that renames the id turns it red.
- **Deferred tools (R-35 c3).** *Verified*: Claude Code 2.1.282 defers the MCP tool behind `ToolSearch`. The model called `ToolSearch` first, then the tool. `ToolSearch` raised no permission request, so no allowlist change is needed for it. *Inferred*: the deferral costs one extra tool call per cell that asks, only on Claude Code. That is a harness property, disclosed, not corrected.
- **Symmetry (US-14).** The server logic, its one tool and its replies are identical for every harness and both pack settings. Only the id that allows it differs, as for the shell class. The transport is identical *unless* DR-S04-1 rules otherwise.

**Copilot `--disable-builtin-mcps` (R-37 c2).** Measured in S-04, *Verified*:
- The flag is **not** what drops the server: stdio is rejected with and without it.
- Without the flag, the Copilot cell connects to the remote `github-mcp-server`; with the flag, it does not.
- The profile does not carry the flag (`bench/profiles/copilot.yaml:7`, against ADR-0004:58). The Owner is ruling on that separately. This design cites the finding and does not change the profile.
- Whether the flag drops a session-supplied **HTTP** server is the first S-04b variant.

## 6. The responder

- **The reply.** On `tools/call ask_user {question}`, the server matches (§7), then replies with the matched clarification's `reply` verbatim, or with `default_reply` verbatim (`Decide and state your assumption.`, `tasks/A1/oracle/clarifications.yaml:14`).
  - The reply is the only content item: `type: "text"`, `isError: false`.
  - Every call is answered, whatever the number of calls. Each call is one log row.
- **Invalid questions.** A question that is not a string, that is empty, that is empty after `normalise`, or that holds a lone surrogate gets the default reply. It is logged with decision `none` and `"invalid": "<reason>"` (T-37-6a).
  - *Inferred* as the safest choice: an error reply would be shown to the model differently by each harness.
- **Nothing else is exposed.** The server has no other tool, resource or prompt. `initialize` declares `tools` only, and unknown methods get `-32601`.
  - *Verified* harmless: Claude Code sent `server/discover` at start and continued.
- **Protocol version.** The server answers with the client's MCP protocol version when it supports it. S-04 saw `2025-11-25` (Claude Code) and `2025-06-18` (Codex).
  - W2-USER-M pins the supported list to those two.
  - Any other requested version is answered with the newer of them (MCP version negotiation; T-37-6b).
- **Fail closed at load.** The server loads the clarification set at start and refuses to start if two clarifications normalise to the same text, or if one normalises to `""` (T-37-6c). A refused start is then visible as `tool_listed: false` (§8). `bench validate` checks the same rule earlier (T-39-4c).
- **No decision request mid-turn.** The match is a pure, synchronous function (R-37).

## 7. The matcher (R-39)

### 7.1 Tiers

1. **Exact:** the question equals an annotated `question`, compared as decoded text.
2. **Normalised:** `normalise(question) == normalise(annotated)` for exactly one clarification.
3. **None:** the default reply.

There is no partial, token-overlap or edit-distance rung: "nothing fuzzy" (R-39 c4).

### 7.2 Normalisation: one function, one test per rule

`normalise(text) -> str` applies these rules in this order.
- The function reads its parameters from the rule table itself: the NFKC form, the quote map, the whitespace rule and the trailing strip set. So the code cannot drift from the table that `matcher_version` hashes.
- Each rule has its own test: a pair that the rule joins, and a near pair that it must keep apart.

| # | Rule | Joins | Keeps apart |
| --- | --- | --- | --- |
| N1 | Unicode NFKC | full-width and compatibility forms | a different letter |
| N2 | curly quotes and apostrophes to straight (`“ ” „ ‟ ‘ ’ ‚ ‛` → `" '`) | `“find the sum”` = `"find the sum"` | quotes around different words |
| N3 | case fold (`str.casefold`) | `Does` = `does` | a different word |
| N4 | whitespace: strip both ends, collapse every run to one space | `the  sum ` = `the sum` | `thesum` ≠ `the sum` |
| N5 | drop trailing `?`, `.`, `!` and spaces | `…total value?` = `…total value` | punctuation inside the text stays |

**Provenance, disclosed (review finding 3).**
- The rule *semantics* were fixed at `dda9f62`, before the measurement. The "Keeps apart" column was filled in after it; that column is test guidance, not a rule.
- Before measuring, the author knew the held-out set's `kind` counts and its `transform` labels (quotes, case, punctuation, whitespace). N2–N5 are exactly those transforms. So the 5/5 on the `normalised` kind confirms the design; it is not held-out evidence.
- The held-out evidence is:
  - precision (0 of 21 default-labelled questions matched, including 0/15 near-misses);
  - paraphrase and compound recall (0/11).
- N1 has no held-out item. TASKS-a is asked for N1 items and for surface-transform items this author has not seen (§13).
- The matcher's author (W2-USER-M) implements the table as written and never reads the held-out set. The held-out test is owned elsewhere (§12, T-39-1).

### 7.3 `matcher_version`, the hashes and the cache key

- **`matcher_version`** is a committed constant, `"t0-" + sha256(canonical)[:12]`. `canonical` is the JSON of `{tiers, rules, unidata_version}`, written with `sort_keys=True`, `separators=(",", ":")` and `ensure_ascii=True`.
  - It includes `unicodedata.unidata_version` (16.0.0 on the host's Python 3.14.6), because NFKC and `casefold` change with the Unicode data.
  - **T-39-3a** recomputes the hash and requires it to equal the committed constant. A changed table, or a Python with other Unicode data, turns the test red until the version is bumped.
  - **T-39-3d** pins golden vectors: fixed inputs must give fixed `normalise` outputs and decisions under the constant. That catches code that drifts from the table.
- **Question hash:** `sha256(question.encode("utf-8", "surrogatepass"))`, so a lone surrogate cannot crash the hash. The question is still invalid (§6).
- **Clarification-set hash:** the `sha256` of `clarifications.yaml`'s bytes, frozen in the plan.
- **Cache key:** (question hash, clarification-set hash, matcher version). It amends spec `:210` and `:245` (DR-S04-3).
- **Store:** in wave 2, the cell's log (§8) is the store. Each call row carries the three key parts and the decision.
  - The **reply sent** is an immutable fact.
  - A re-grade under the **same** matcher version reads the stored decision and never re-matches (T-39-3b).
  - A later matcher version (the wave-3 rung) may make **new** decisions over the stored verbatim questions, under its own key. Wave-2 decisions are never overwritten. This keeps DR-S04-2's option (d) open.

## 8. The log (R-37 c4, US-10)

There is one file per scenario-1 cell: `<cell_dir>/scripted-user.jsonl`, schema `bench-scripted-user-log/1`. It is archived with the cell (spec `:199`, "scripted-user log").

```
{"kind":"header","schema":"bench-scripted-user-log/1","task":"A1","clarifications_sha256":"…","matcher_version":"t0-…"}
{"kind":"initialize","client":{"name":"claude-code","version":"2.1.282"},"protocol_version":"2025-11-25"}
{"kind":"tools_listed"}
{"kind":"call","seq":1,"t":12.4,"question":"…","question_sha256":"…","clarifications_sha256":"…","matcher_version":"t0-…","decision":{"clarification":null,"rung":"none"},"reply":"Decide and state your assumption."}
{"kind":"end","calls":1,"client_initialized":true,"tool_listed":true}
{"kind":"end","calls":0,"client_initialized":true,"tool_listed":true,"note":"no question asked"}
{"kind":"end","calls":0,"client_initialized":false,"tool_listed":false,"note":"tool not reached"}
```

- **The server** writes:
  - `header` at start;
  - `initialize` and `tools_listed` when the harness's MCP client does those;
  - one `call` row per call.

  Every row is flushed before the matching reply is sent. Rows are written under one lock, because an HTTP transport (DR-S04-1) can take calls concurrently, and `seq` is assigned under the same lock.
- **The engine** writes `end` after the turn, because the server gets no clean EOF (§4.1). It reads the rows it finds:
  - **A torn last line** (the server killed mid-write) is not a row. The engine records `"torn_tail": true` (T-37-4c).
  - **No `header`:** the engine writes one from the plan.
  - **`tool_listed: false`:** the note is `"tool not reached"`, and the clarification metrics are NOT_RECORDED with that reason, never 0 (T-37-1b).
  - **The tool listed, no `call` row:** the note is `"no question asked"`. That is an assume, and it is scored.
  - The file is never empty and never absent for a scenario-1 cell (T-37-4b).
- This separates "the agent asked nothing" (Codex on A1, S-04) from "the agent could not ask" (Copilot over stdio, S-04). A process start alone does not count as reached (§4.1).
- **Tampering.** The agent's shell can write to `<cell_dir>`. The log sits outside the working copy (`ws/`), but on the same host. Integrity against a hostile agent is a Security hand-off (§14), not a property this design claims.

## 9. Seams for W2-USER-W (file:line against `main` at `c9960ed`)

| Seam | Where | Change |
| --- | --- | --- |
| Pass the server | `src/harness_bench/driver.py:219-221` (the `run_turn` signature), `:236` (`session/new`) | Add `mcp_servers: list[dict] \| None = None`. Send `mcp_servers or []`. T-37-3 asserts both forms. |
| Choose the server per cell | `src/harness_bench/engine.py:415-417` (`_attempt`'s `run_turn` call) | Pass the entry when `self.plan["tasks"][cell["task"]]["scripted_user"]` is true, else nothing. |
| Close the log | `src/harness_bench/engine.py:363-376` (`_run_cell`, after the outcome) | Write the `end` row (§8) before `_archive` at `:382`, so it is archived. |
| Freeze the task's inputs | `src/harness_bench/plan.py:129-132` (`_prompt`) and the plan's task record | Carry `scripted_user`, the clarification-set hash and `matcher_version`, so the plan freezes all three. T-39-3c compares them with every row. |
| The class id | `src/harness_bench/profiles.py:60-63` (`seed_home` writes `files`), `:82-97` (`argv`) | No code change. The ids live in the YAML. |
| Claude Code id | `bench/profiles/claude-code.yaml:14` | Add `mcp__scripted_user__ask_user` to `permissions.allow`. |
| Copilot id | `bench/profiles/copilot.yaml:7` | Add `--allow-tool`, `scripted_user`, and the transport DR-S04-1 rules. |
| Codex | `bench/profiles/codex.yaml` | None. |
| Scenario-1 rule | `src/harness_bench/config.py:166-167` | Already requires `scripted_user: true` (*Verified*). |

## 10. The S-04 threshold (R-39 c1, US-31, spec R10)

**Held-out set:** `tasks/A1/oracle/heldout_questions.yaml`, 38 questions. It joined `main` in `c9960ed` ("join W2-TASKS-a … held-out matcher set of 38"). Its `sha256` is recorded in the spike note and pinned in T-39-1, so an edit to the set makes the numbers visibly stale.
- 17 are labelled `goal-maximum`: 1 exact, 5 normalised, 10 paraphrase, 1 compound.
- 21 are labelled `default`: 15 near-miss, 6 off-topic.

**Measured** (spike note; `tests/fixtures/acp/scripted-user/heldout_measure.py` over the §7 table):

| Measure | Value | Held-out evidence? |
| --- | --- | --- |
| Precision | 6/6 = **1.0** | yes |
| Default-labelled questions matched | **0/21** (near-miss 0/15) | yes |
| Recall, paraphrase + compound | **0/11** | yes |
| Recall, exact + normalised | 6/6 | no: the author knew the transforms (§7.2) |
| Recall, overall | 6/17 = 0.353 | mixed: moves with the set's share of surface variants |
| Live A1 questions matched | 0/1 (Claude's one question: the key ambiguity, paraphrased) | live, n = 1 |

**Threshold:**
1. **Regression floor** (a matcher version below it is not used):
   - precision 1.0;
   - 0 default-labelled matches;
   - exact + normalised recall 1.0.

   It equals what the table scored. It is a floor against regressions, not an independent qualification.
2. **Confidence:** **paraphrase + compound recall at least T = 0.80.** Below T, the clarification metrics carry `low-confidence matcher` (US-31 `:457`). **Not met: 0/11.**
   - So every A1 cell's clarification metrics carry the label in wave 2.
   - T is defined on the paraphrase and compound kinds because live questions are paraphrases (1/1 in S-04). Overall recall depends on how many surface variants the set's author included, and does not estimate live recall.
   - *Why 0.80 (Inferred):* A1 has one clarification, so a cell's key-question recall is 0 or 1. If held-out paraphrase recall r approximates live recall, a right ask scores 1 with a probability of about r. At 0.80, a miss is at most one in five right asks. It is a policy value, open to the Owner.

## 11. Spike S-04: the probe

`tests/fixtures/acp/scripted-user/`:
- `probe_server.py`: the probe's MCP server, stdio or Streamable HTTP.
- `probe_turn.py`: one turn per harness, built as `tools/acp_record.py turn` builds one, with `--transport session-stdio | session-http | copilot-config`.
- `probe_selftest.py`: offline, 41 checks.
- `heldout_measure.py`: the §10 measurement.
- `s04-results.json`: the scrubbed facts of the eleven runs. The raw recordings, server logs and native records are not committed.

## 12. Promise → test table

Tests are named for W2-USER-M (`tests/test_scripted_user.py`) and W2-USER-W (`tests/test_driver.py`, `tests/test_engine.py`, `tests/test_allowlist_classes.py`). Each is red first.

| Promise | Test | Owner |
| --- | --- | --- |
| R-37: one tool, `ask_user(question)`; `initialize` declares tools only; unknown methods get `-32601` | T-37-0 `test_server_lists_exactly_ask_user` | USER-M |
| R-37 / US-10: the reply is the matched `reply` or exactly the default | T-37-R `test_reply_is_clarification_text_or_exact_default` | USER-M |
| R-37 c1: per harness, the shape accepted, the tool in the native record, the A1 turn calls it | spike S-04 (`s04-results.json`, spike note); T-37-1a `test_mcp_server_entry_is_stdio_without_type` | USER-D (done), USER-W |
| R-37 c1: a harness the tool never reaches is visible, never silent | T-37-1b `test_tool_not_reached_is_recorded_and_not_scored` (no `tools_listed` row → `tool_listed: false`, note "tool not reached", clarification metrics NOT_RECORDED) | USER-W |
| R-37 c2: the id is in each allowlist as the class "scripted user" | T-37-2a `test_allowlist_covers_scripted_user_class` (in `test_allowlist_classes.py`; the id read from a scrubbed cut of the S-04 Claude native record) | USER-W |
| R-37 c2: `--disable-builtin-mcps` does not drop a session-supplied server | S-04: stdio is rejected with and without the flag (Verified). T-37-2c `test_copilot_session_server_listed_under_disable_builtin_mcps`: a replay assertion over the scrubbed S-04b Copilot run for the transport DR-S04-1 picks, plus the same check in the Copilot profile's qualification canary. T-37-2b `test_copilot_profile_disables_builtin_mcps` only if the Owner's ruling adds the flag | USER-D (fixture), USER-W |
| R-37 c3: the server only with `scripted_user: true`; else `mcpServers: []` | T-37-3 `test_mcp_servers_only_for_scripted_user_tasks` (both forms) | USER-W |
| R-37 c4: question, decision, reply per call, flushed before the reply, under one lock | T-37-4a `test_log_row_per_call_before_reply` | USER-M |
| R-37 c4: zero calls → "no question asked", never an empty file | T-37-4b `test_zero_calls_writes_no_question_asked` | USER-W |
| R-37 c4: a torn last line is not a row | T-37-4c `test_torn_tail_is_not_a_row` | USER-W |
| R-37 c5: the prompt is identical across combos | existing US-10 hash test (`plan._prompt`), plus T-37-5 `test_a1_prompt_names_ask_user` | USER-W |
| §6: invalid questions get the default reply | T-37-6a `test_invalid_question_gets_default_and_is_logged` (not a string, empty, empty after normalise, lone surrogate) | USER-M |
| §6: protocol version negotiation | T-37-6b `test_protocol_version_negotiation` | USER-M |
| §6: fail closed at load | T-37-6c `test_server_refuses_ambiguous_or_empty_clarifications` | USER-M |
| R-39: exact, then normalised, then default; nothing else | T-39-0 `test_tiers_exact_normalised_default_only` | USER-M |
| R-39 c1: the matcher meets the S-04 floor on the held-out set | T-39-1 `test_matcher_meets_s04_floor_on_heldout`. It pins the set's `sha256`, prints **aggregates only** (per-kind counts, never the failing questions), and is owned outside USER-M | USER-D / Test Architect |
| R-39 c1: spec R10 closes by citation | T-39-1b `test_spec_r10_cites_the_s04_note`: the spec's R10 row names `docs/notes/spike-s04-scripted-user.md` (the edit belongs to the spec's owner) | Leader (spec edit), USER-W (test) |
| R-39 c2: the held-out set is not the matcher author's | T-39-2 `test_no_commit_touches_matcher_and_heldout`: no commit touches both `src/harness_bench/scripted_user/**` and `tasks/*/oracle/heldout_questions.yaml` (git log over both paths) | USER-M |
| R-39 c3: `matcher_version` is the hash of the table and its Unicode data | T-39-3a `test_matcher_version_constant_matches_table`; T-39-3d `test_golden_vectors` | USER-M |
| R-39 c3: a re-grade under the same version makes no new match | T-39-3b `test_regrade_reads_stored_decisions` | USER-M |
| R-39 c3: `matcher_version` on every match | T-39-3c `test_every_row_carries_the_frozen_key`: `question_sha256`, `clarifications_sha256` and `matcher_version` on every call row, equal to the header and to the plan's frozen values | USER-W |
| R-39 c4: one function, a test per rule | T-39-4-N1 … T-39-4-N5 (join and keep-apart per rule) | USER-M |
| R-39 c4: nothing fuzzy; near-misses get the default | T-39-4b `test_near_misses_get_default_reply` (on the task's own non-held-out fixtures); T-39-4c `test_ambiguous_clarifications_rejected` (`bench validate`) | USER-M |
| US-31: recall, precision, ask-versus-assume from the log | S-08d (`grade/clarify.py`), out of scope here | — |

## 13. Decision requests

### DR-S04-1 (R-37 c1): the tool never reaches Copilot over stdio

*Verified*: Copilot 1.0.89-1 rejects client-supplied stdio MCP servers. The options:

- **(a) HTTP for every harness.** The engine runs one Streamable-HTTP server per cell on `127.0.0.1` and passes `{type: "http", name, url, headers: []}` in `session/new`.
  - Pro: one transport, so US-14 symmetry holds.
  - Costs and risks, each a success criterion for S-04b or USER-W:
    - **Same-cell injection.** The URL travels in `session/new`, which is in the cell's ACP recording and may be in Copilot's `home/logs`. The agent's own shell can `POST` to it and write rows that bypass the model's tool call; with stdio, only the harness holds the pipe. The mitigation (a secret header, not a path, and the `ws/`-to-log separation) is a **Security** hand-off. Cross-cell calls are the same risk, from a neighbour.
    - **Concurrency.** `seq` and flush-before-reply under one lock (§8).
    - **Readiness and teardown.** The server listens before `session/new`, lives until after R-21's grace, not only to the end of the turn, runs in its own Job Object, and leaves no port behind if the engine crashes.
    - **Proxy environment.** `HTTP_PROXY`/`NO_PROXY` in the cell's environment must not route `127.0.0.1`.
    - **Timeouts.** Tool-call timeouts differ per harness and per transport; S-04b records them.
  - Needs S-04b variants 1, 2, 5 and 6 green.
- **(b) HTTP for Copilot only; stdio for Claude Code and Codex.** The same server logic behind two transports: asymmetric in transport, and disclosed. The (a) risks apply to Copilot cells. Needs S-04b variants 1–2.
- **(c) Copilot through its own launch flag.** `--additional-mcp-config @<cell>/mcp-config.json`, the same stdio server. This leaves ACP `session/new` for one harness, so it amends R-37's "passed in `session/new`". Needs S-04b variants 3–4.
- **(d) Copilot A1 cells not applicable in wave 2.** The cost is not only 2 of 36 cells: one of three harnesses leaves the only scenario-1 task's cross-harness comparison. It is disclosed in the report.
- **(e) Re-pin Copilot** (R-33) to a build that accepts client stdio servers, if one exists. Unverified that one does; a pin change re-opens the Copilot profile's qualification.

**Default:** decide after S-04b. The author leans to (a) if the HTTP variants pass and Security clears the injection mitigation; else (b).

### DR-S04-2: the responder shares the matcher's recall ceiling (numbers for the Owner's ruling)

**Measured:**
- On the held-out set: paraphrase and compound recall is **0/11**; precision is **1.0**; default-labelled matches are **0/21**. Overall recall is 6/17 = 0.353, but that figure is set by the share of surface variants in the set (§10).
- On the live A1 turns:
  - Claude Code asked **1** question: the key ambiguity, paraphrased. It did not match, so the agent got `Decide and state your assumption.`
  - Codex asked **0**, with the tool listed.
  - Copilot could not ask.
- **Live matched: 0 of 1 asked.** With n = 1, this shows that the case occurs; it is not a rate.

**Consequences (Inferred):**
- An agent that asks the right question in its own words gets no answer. A1's hidden tests then measure whether it assumed "maximum".
- **Phrasing bias.** The ceiling acts on each model's wording. A model that happens to quote the annotated question gets the answer; one that paraphrases does not. So the cross-harness A1 comparison carries a phrasing bias, not only a low-confidence label.
- **What stays intact.** The ask-versus-assume measure: the log records every ask.
- **What is not intact.** US-31 precision (matched ÷ asked) and recall: both are driven by matcher recall.

**Options:**
- **(a)** Accept, and disclose it in the report header beside `low-confidence matcher`, naming the phrasing bias.
- **(b)** Hold scenario-1 correctness NOT_RECORDED until the wave-3 model rung.
- **(c)** Decide on measurement. Done: the numbers are above.
- **(d)** Separate the responder fact from the grading judgement.
  - The reply sent stays an immutable fact.
  - Key-question matching for *grading* is re-run under a later matcher version (the wave-3 rung) over the stored verbatim questions, as a new decision (§7.3).
  - Wave-2 grading of A1 is then provisional, not frozen at the T0 ceiling.
- **(e)** TASKS-a-authored question aliases in `clarifications.yaml`, disjoint from the held-out set: more annotated wordings of the same clarification.
  - Deterministic, and raises recall.
  - Needs an R-39 ruling on whether an alias counts as "annotated", and a fresh held-out set that the aliases were not written from.

The author's reading: (d) with (a)'s disclosure keeps the wave-2 cells usable without claiming a clarification outcome that the matcher cannot see.

### DR-S04-3: the spec's clarification-match key

Spec `:210` and `:245` key the match on (question hash, matcher version). The decision also depends on the clarification set. This design uses (question hash, clarification-set hash, matcher version), §7.3. It asks the spec's owner to amend both lines the same way.

### Requests to W2-TASKS-a (not decisions)

- N1 (NFKC, full-width) held-out items.
- A few surface-transform items this design's author has not seen.
- Keep any aliases, under DR-S04-2 (e), disjoint from the held-out set.

## 14. Review

**AI Systems Engineer (Adversary mode), on revision 2 before these edits: `CLEAR WITH CONDITIONS`. The hard veto is not triggered.**
- The matcher is T0, a pure function.
- The model's non-deterministic question reaches grading only through a typed decision.
- The held-out measurement reproduced offline: 38 questions, precision 1.0, 0/15, 6/6, 0.3529. The reviewer also found `normalise` idempotent on its edge cases.

Findings, and how this revision closes each:

| # | Severity | Finding | Closed by |
| --- | --- | --- | --- |
| 1 | Major | The cache key omits the clarification set; `matcher_version` hashes a description, not behaviour (Unicode data, undefined canonical JSON, a self-fulfilling test) | §3, §7.3 (three-part key, `unidata_version`, defined canonical JSON, committed constant, golden vectors T-39-3d); DR-S04-3 |
| 2 | Major | Held-out independence broken by the test plan (USER-M owns T-39-1; T-39-2 checks a comment; set not hash-pinned) | §12 T-39-1 (owned outside USER-M, aggregates only, `sha256` pinned), T-39-2 (a path check over git history); §10 |
| 3 | Major | The qualification bar equals the result; `normalised` recall is in-sample; T on overall recall does not estimate live recall | §7.2 provenance; §10 (a regression floor; T on paraphrase + compound, 0/11; "about r" labelled Inferred); requests to TASKS-a |
| 4 | Major | DR-S04-2 overstates fairness; options missing | §13 DR-S04-2 (phrasing bias, precision not intact, options (d) and (e)) |
| 5 | Major | `server_started` is not "the agent could ask"; "no question asked" conflated with not reached | §4.1, §8 (`initialize` and `tools_listed` rows; `tool_listed`; note "tool not reached"; NOT_RECORDED), T-37-1b |
| 6 | Major | HTTP risks incomplete (same-cell injection, concurrency, readiness and teardown, proxy, timeouts; re-pin option; the true cost of (d)) | §13 DR-S04-1; §8 lock |
| 7 | Major | Gaps in the promise→test table (R-37 c2 second clause, R-39 c3 on every match, R-10 citation, §6 promises) | §12: T-37-2c, T-39-3c, T-39-1b, T-37-6a/b/c; §9 plan freezes `matcher_version` |
| 8 | Minor | The question hash crashes on a lone surrogate | §7.3 `surrogatepass`; §6; T-37-6a |
| 9 | Minor | Two "Verified" claims exceed the committed evidence | §4.1 lifetime relabelled; §4.2 split; §10 cites `c9960ed`; the spike note states the raw artefacts are not committed |
| 10 | Minor | A torn last log line | §8; T-37-4c |

**Hand-offs named by the reviewer:**
- Test Architect: T-39-1 ownership, T-39-2, and the new tests.
- Security: DR-S04-1's injection path, and log tampering (§8).
- Owner: DR-S04-3, and DR-S04-2's options (d) and (e).

**Residual risk:**
- Live recall is unmeasured beyond n = 1.
- Each model's phrasing bias is unmeasured.
- The held-out set has no N1 item.
- Copilot over HTTP is unmeasured (S-04b).
- Log integrity against a hostile agent is not claimed.
