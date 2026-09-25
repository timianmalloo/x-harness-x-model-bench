---
id: "note-spike-s04-scripted-user"
title: "Spike S-04: the scripted user's ask_user tool reaches Claude Code and Codex over stdio; Copilot rejects stdio from the client"
type: doc
status: draft
owner: "@timianmalloo"
tags: [benchmark, spike, phase-2, scenario-1, scripted-user, mcp, acp, matcher, S-04]
links:
  - { to: design-phase2-scripted-user, rel: relates-to }
  - { to: spec-harness-bench, rel: relates-to }
  - { to: adr-0004-static-permissions, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-12-25"
summary: >-
  Eleven probe turns on the pinned builds (Leader-run, 2026-09-25). Claude Code 2.1.282 and Codex 0.156.0 start a
  stdio MCP server given in ACP session/new mcpServers, list ask_user, and call it on request; the reply reaches the
  model. Copilot 1.0.89-1 accepts session/new but rejects the stdio entry ("Rejecting non-http/sse MCP server"), with
  or without --disable-builtin-mcps, so the tool never reaches it: a decision request (R-37 c1), with an HTTP and a
  launch-config variant written for the Leader. On A1, Claude asked once (the key ambiguity, paraphrased; no match),
  Codex asked nothing. The rule table's held-out measurement: precision 1.0, 0/21 default-labelled matches,
  paraphrase recall 0/11 (overall 6/17); S-04 threshold set (regression floor met; T = 0.80 on paraphrase recall
  not met, so A1 clarification metrics carry "low-confidence matcher" in wave 2).
---

# Spike S-04: the scripted user (R-37 c1, c2; R-39 c1)

**Track:** W2-USER-D. **Runs:** the Leader ran all eleven turns on 2026-09-25, 04:10–04:15 UTC, from
`tests/fixtures/acp/scripted-user/probe_turn.py` at `dda9f62`. **Evidence:**
- `tests/fixtures/acp/scripted-user/s04-results.json`: the scrubbed facts of every run. It holds no paths, no agent text and no system prompt.
- The raw recordings, server logs and native records stay under the operator's cells root. They are not committed.
- The Copilot process logs are in each cell's `home/logs/`.

## Question

Per harness, on the pinned builds:
- Does a bench-owned stdio MCP server, passed in ACP `session/new` `mcpServers`, reach the agent?
- Is `ask_user` in the native record?
- Does one A1 turn call it (R-37 c1)?
- Does Copilot's `--disable-builtin-mcps` drop the session-supplied server (R-37 c2)?

And: what does the design's deterministic rule table score on the held-out set (R-39 c1)?

## Method

- **Probe server** (`probe_server.py`): stdlib stdio MCP with one tool, `ask_user`. It gives a fixed reply and logs every message in and out. The server's log is the ground truth for *started*, *listed* and *called*, because a malformed entry is dropped silently by both adapters (design §4.1).
- **Probe turn** (`probe_turn.py`): the turn `tools/acp_record.py turn` runs, with the probe server in `session/new` and the probe tool on each allowlist. There are three kinds of turn:
  - `--handshake-only` stops before the prompt, so it spends no model turn;
  - `--prompt probe` asks the model to call `ask_user` once and repeat the reply, which carries the token `S04-TOKEN-4417`;
  - `--prompt a1` sends A1's `prompt.md` verbatim. The server answers every call with exactly `Decide and state your assumption.`, since no matcher existed at run time.
- **Models (R-33):** `claude-opus-5-5` (Claude Code), `gpt-6-sol` (Codex, Copilot).

## Results

| Harness · build | Run | `session/new` | Server started (log via) | Listed | Tool in ACP stream (title) | Called | Reply reached the model | Native record id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Code 2.1.282 · `claude-agent-acp` 0.81.2 | handshake | accepted | yes (`env`) | yes | — | — | — | — |
| | probe | accepted | yes (`env`) | yes | `ToolSearch`, then `mcp__scripted_user__ask_user` | yes, 1 | yes (token in the text) | `mcp__scripted_user__ask_user` |
| | A1 | accepted | yes (`env`) | yes | `ToolSearch`, then `mcp__scripted_user__ask_user` | **yes, 1** | n/a (default reply) | `mcp__scripted_user__ask_user` |
| Codex 0.156.0 · `codex-acp` 1.12.0 | handshake | accepted | yes (`env`) | yes | — | — | — | — |
| | probe | accepted | yes (`env`) | yes | `mcp.scripted_user.ask_user` | yes, 1 | yes | `mcp__scripted_user__ask_user` |
| | A1 | accepted | yes (`env`) | yes | none | **no** | n/a | none (the rollout names `ask_user` only in the user message) |
| Copilot 1.0.89-1 (native ACP), with `--disable-builtin-mcps` | handshake, probe, A1 | accepted | **no** | no | none | no | no: the model says the tool "isn't available" | none |
| Copilot 1.0.89-1, profile flags only (no `--disable-builtin-mcps`) | handshake, probe | accepted | **no** | no | none | no | no | none |

Every figure is *Verified*: it is read from the run's server log, ACP recording and native record, re-analysed by the committed `analyse`. Those raw artefacts are **not committed**; the committed, re-checkable form is `s04-results.json`, which carries every column of this table. No run had a permission request. Every turn ended `end_turn` with no cause, except the handshake-only runs, which by design sent no prompt.

**The MCP clients seen by the server** (`initialize`):
- Claude Code: `claude-code` 2.1.282, protocol `2025-11-25`. In the handshake it also sent `server/discover`, which the probe answered `-32601`.
- Codex: `codex-mcp-client` 0.156.0, protocol `2025-06-18`.

**Lifetime:**
- *Verified* by an operator process check and by reading the logs; neither is in `s04-results.json`. After all eleven runs, no `probe_server.py` process was running, and no server log ends in `eof`.
- *Inferred*: each server was ended with its cell's Job Object. The same evidence fits an adapter that ends its own children.

### Why Copilot never lists the tool (Verified)

Each of the five Copilot runs writes the same line to its own process log (`home/logs/process-*.log`), 2 ms after `ACP server started`:

```
[WARNING] [rust:acp::mcp_servers] Rejecting non-http/sse MCP server "scripted_user" from client
```

- Copilot 1.0.89-1 accepts only `http` and `sse` MCP servers from an ACP client. It advertises exactly that: `mcpCapabilities: {http: true, sse: true}`.
- `session/new` still returns a session, with no error. So the rejection is visible only in Copilot's own log.
- The ACP schema says stdio is the transport "All Agents MUST support". Copilot's refusal departs from the schema; this is recorded, not argued.
- **The cause is the transport, not the shape, the env or the allowlist:**
  - the same entry started the server on Claude Code and Codex;
  - Copilot rejects it before any env or tool permission applies;
  - the rejection is identical with and without `--disable-builtin-mcps`.

**`--disable-builtin-mcps` (R-37 c2), Verified in these runs:**
- The flag is **not** what drops the server. Stdio is rejected with the flag (3 runs) and without it (2 runs).
- Without the flag, the Copilot cell connects to the remote `github-mcp-server` ("Service initialized as client … `github-mcp-server`"). With it, no such line appears. This is evidence for the Owner's separate ruling on the profile's missing flag (ADR-0004:51, :58). It is cited here, not fixed.
- Whether the flag drops a session-supplied **HTTP** server is not yet measured. It is the first variant below.

### Further variants (written; for the Leader to run)

`probe_turn.py` now has `--transport`:

| Variant | What it tests | Command (from the worktree, `$T` = the pinned tools dir, `$P` = the probe) |
| --- | --- | --- |
| Copilot · session HTTP · handshake | Copilot starts a session-supplied `{type: "http"}` server under the flag (R-37 c2) | `uv run python $P run --harness copilot --model gpt-6-sol --tools-dir $T --transport session-http --handshake-only --copilot-disable-builtin-mcps` |
| Copilot · session HTTP · probe | the model calls it; the reply arrives | `uv run python $P run --harness copilot --model gpt-6-sol --tools-dir $T --transport session-http --copilot-disable-builtin-mcps` |
| Copilot · launch config · handshake | Copilot's own `--additional-mcp-config @file` with the same stdio server | `uv run python $P run --harness copilot --model gpt-6-sol --tools-dir $T --transport copilot-config --handshake-only --copilot-disable-builtin-mcps` |
| Copilot · launch config · probe | the model calls it | `uv run python $P run --harness copilot --model gpt-6-sol --tools-dir $T --transport copilot-config --copilot-disable-builtin-mcps` |
| Claude Code · session HTTP · probe | one transport for every harness is possible | `uv run python $P run --harness claude-code --model claude-opus-5-5 --tools-dir $T --transport session-http` |
| Codex · session HTTP · probe | the same | `uv run python $P run --harness codex --model gpt-6-sol --tools-dir $T --transport session-http` |

- Cost: four short model turns; the handshake-only runs spend none.
- Output: `C:\Projects\bench-cells\s04-probe\<label>.summary.json`, as before.
- The launch-config shape is what `copilot mcp add --json` 1.0.89-1 writes (`type: "local"`, `command`, `args`, `tools: ["*"]`, `env`). It was read by running the pinned binary against a throwaway home.

### A1: ask versus assume (R-37 c1; bears on DR (c))

| Harness | Reached | Questions asked | The question | Matches an annotated clarification (rule table) | Reply sent |
| --- | --- | --- | --- | --- | --- |
| Claude Code | yes | 1 | "The statement says "find the sum of the values of the chosen balls" but doesn't say which sum. Should I output the maximum possible sum over all valid choices (the empty choice gives 0)?" | **no** (rung `none`) | `Decide and state your assumption.` |
| Codex | yes (listed) | 0 | — (the log would record "no question asked") | — | — |
| Copilot | no (rejected) | 0 (could not) | — | — | — |

- Claude's question asks the key ambiguity (maximum or not). By the held-out file's labelling rule ("the same core ambiguity"), it would be labelled `goal-maximum`. That labelling is *Inferred*: it is this author's application of TASKS-a's rule, not TASKS-a's label.
- A deterministic matcher misses it, so in a real cell the agent would have got the default reply for the right question.
- One turn per harness is a sample of one. It shows the case occurs; it does not estimate a rate.

## The held-out measurement (R-39 c1)

**What ran:**
- **The table:** the design's rule table (§7: exact, then N1 NFKC, N2 quotes, N3 casefold, N4 whitespace, N5 trailing `?.!`). The rule semantics were fixed at `dda9f62`, before this ran.
- **The set:** `tasks/A1/oracle/heldout_questions.yaml`, 38 questions. It joined `main` in `c9960ed` as W2-TASKS-a's work. Its `sha256` is `7710c34509319b6cf07be70615c8eecadc63b80ce293ca2aa7b10b0c4d583f23`.
- **The clarifications:** `clarifications.yaml`, `sha256` `86fee6273e75d4fad474a89e25edde6f71a676a1112169149f733e8288963e0d`.
- **The run:** `tests/fixtures/acp/scripted-user/heldout_measure.py`, Python with Unicode data 16.0.0.

This is a reference measurement of the table. The matcher W2-USER-M builds must reproduce it; the check is T-39-1, owned outside USER-M. The AI Systems Engineer reproduced the numbers offline.

| Kind | n | Matched | Correct | False matches |
| --- | --- | --- | --- | --- |
| exact | 1 | 1 | 1 | 0 |
| normalised | 5 | 5 | 5 | 0 |
| paraphrase | 10 | 0 | 0 | 0 |
| compound | 1 | 0 | 0 | 0 |
| near-miss | 15 | 0 | 0 | 0 |
| off-topic | 6 | 0 | 0 | 0 |
| **all** | **38** | **6** | **6** | **0** |

**What is held-out evidence and what is not.**
- **Held-out evidence:**
  - precision 6/6 = **1.0**;
  - **0/21** default-labelled questions matched (near-miss 0/15);
  - paraphrase + compound recall **0/11**.
- **Not held-out evidence:** the 6/6 on the exact and normalised kinds. The author knew the set's transform labels before measuring, and N2–N5 are exactly those transforms.
- **Overall recall, 6/17 = 0.353,** moves with the set's share of surface variants. It does not estimate live recall.
- **No held-out item exercises N1.**
- **Live:** 0/1 A1 questions matched (above).

**The S-04 threshold (set here; spec R10 closes by citation, T-39-1b):**
1. **Regression floor.** A matcher version below it is not used:
   - precision 1.0;
   - 0 default-labelled matches;
   - exact + normalised recall 1.0.

   It equals what the table scored, so it guards against regressions; it is not an independent qualification. **Met.**
2. **Confidence:** **paraphrase + compound recall ≥ T = 0.80.** Below T, the clarification metrics carry `low-confidence matcher` (US-31 `:457`). **Not met: 0/11.** So in wave 2, every A1 cell's clarification metrics carry the label.

   *Why 0.80 (Inferred):* A1 has one annotated clarification, so a cell's key-question recall is 0 or 1. If held-out paraphrase recall r approximates live recall, an agent that asks the right question scores 1 with a probability of about r. At 0.80, a miss is at most one in five right asks. This is a policy value, and the Owner may amend it.

## Findings

1. Claude Code and Codex: the R-37 mechanism works as ruled. Stdio in `session/new`, with no `type` field, is started, listed and called, and the reply reaches the model. *Verified.*
2. Claude Code defers MCP tools behind `ToolSearch`. The model called `ToolSearch` first, then the tool. `ToolSearch` raised no permission request with the current allowlist. *Verified*: 0 requests in both called runs.
3. The class ids (R-37 c2, R-34):
   - Claude Code: `mcp__scripted_user__ask_user`, which the design's `assume:` marker predicted; now *Verified* in the native record.
   - Codex: ACP title `mcp.scripted_user.ask_user`, native id `mcp__scripted_user__ask_user`. No allowlist entry is needed under `agent-full-access`: the call raised no permission request.
   - Copilot: not reached.
4. Copilot 1.0.89-1 rejects client-supplied stdio MCP servers, silently to the client. **Decision request** (R-37 c1): see the design §13.
5. `--disable-builtin-mcps` does not cause the rejection. Without it, a Copilot cell connects to `github-mcp-server` (Owner ruling pending; cited).
6. Probe defects found and fixed, red-first in `probe_selftest.py`:
   - **OUT-A:** the summary printed to a cp1252 console crashed after it was saved. It hit three runs (Copilot probe with the flag, Claude A1, Copilot A1). Only for Claude A1 did it change the verdict: that exit status was 1, although the turn called the tool. The Leader's exit-code line ("claude-code a1 1") is superseded by the saved summary.
   - A `TEST-A` instance: "tool in the native record" counted the prompt's own bare word `ask_user`. It now needs the harness's qualified id.
