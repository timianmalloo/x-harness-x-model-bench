---
id: note-20261003-spike-e4-post-turn-prompt
title: "Spike E4 - a second session/prompt in the same ACP session after end_turn"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [spike, acp, multi-turn, rework, risk-R-E6, DR-E4, EV-4]
links:
  - { to: spec-enterprise-evaluation, rel: relates-to }
review-by: "2026-12-24"
summary: >-
  Verified on all three harnesses (Windows host; macOS unverified): the ACP session itself accepts a
  second session/prompt on the same sessionId after turn 1 ends with stopReason end_turn, with no
  second handshake and stdin never closed between turns. Turn 2 completed end_turn on claude-code
  (claude-opus-5-5), codex (gpt-6-sol) and copilot (gpt-6-sol), and each adapter's growing
  cachedReadTokens across the turn boundary shows turn 1's context carried into turn 2. The production
  engine does not do this today: driver.run_turn sends exactly one prompt and returns
  (src/harness_bench/driver.py:300), and engine.py's _attempt closes stdin immediately after it returns
  (src/harness_bench/engine.py:752), inside a finally that always runs (engine.py:728-732). Supporting
  DR-E4's two-turn rework task needs driver/engine changes, named below, not just a second RPC call.
---

# Spike E4: a second session/prompt in the same ACP session, after end_turn

**Question (R-E6, DR-E4, EV-4):** can the engine send a second user prompt in the same ACP session
after turn 1 ends, and get a second complete turn, on claude-code, codex and copilot?

## Method (Verified)

Read first, source not memory:
- `src/harness_bench/driver.py` (`run_turn`, lines 249-313): one handshake (`initialize`, `session/new`,
  optional `session/set_model`/`session/set_mode`), the ack barrier (`before_send`, line 294), then
  exactly one `session/prompt` (line 300) and a return. `TurnResult` (lines 90-111) holds one
  `stop_reason`/`usage`/timing set per call.
- `src/harness_bench/engine.py` (`_attempt`, lines 684-747; `_end_process`, lines 749-776): one
  `driver.run_turn` call (line 724), then in a `finally` that always runs, `_end_process` closes stdin
  immediately (line 752, "Graceful first") and the job is confirmed killed before the attempt returns.
  `attempt` is hardcoded to `1` at the three record sites (lines 665, 719, 810) and `archive.archive_cell`
  (line 807, `attempt=1`) writes a folder named `attempt-{attempt}` that `archive.py:57-58` refuses to
  write twice ("an archive attempt is written once") -- there is no existing "turn snapshot" primitive.
- `src/harness_bench/profiles.py`: profile data for all three harnesses (`bench/profiles/*.yaml`); no
  per-turn awareness, no change needed for a second prompt itself.
- `src/harness_bench/tools.py`: pinned builds -- `@agentclientprotocol/claude-agent-acp` 0.81.2,
  `@agentclientprotocol/codex-acp` 1.12.0 (both read from `bench/tools/package-lock.json`), Copilot
  1.0.89-1 native ACP (no adapter).
- The ACP adapters' own source (installed into this worktree's `.tools/harness/node_modules/` by
  `tools.install`, pinned versions above): `@agentclientprotocol/claude-agent-acp` and `-codex-acp`
  dists were present for inspection; neither rejected a second `session/prompt` on an already-created
  `sessionId` -- confirmed empirically below, by running them, not by reading the minified dist further.

**Probe:** `spikes/e4_two_turns.py` (this worktree). It reuses `driver._Channel`, `profiles.Profile`,
`tools.resolve` and `procs.spawn` directly (the same primitives `run_turn` uses) but keeps one channel
and one adapter process alive across two `session/prompt` RPCs on the same `sessionId`: handshake once,
`session/prompt` (prompt 1: "create a.txt containing 1"), wait for the result, hash the tree, a second
`session/prompt` (prompt 2: "change a.txt to 2, add b.txt") on the same channel with stdin never closed
in between, wait for the result, hash the tree again. Each harness got its own fresh scratch home+cwd
(not `C:/projects/x-harness-x-model-bench/runs/`), seeded by `profile.seed_home`/`cell_env` exactly as a
real cell is. Models stipulated per the task: claude-code `claude-opus-5-5`, codex `gpt-6-sol`, copilot
`gpt-6-sol`.

## Results (Verified by execution, not inferred)

| harness | turn 1 stop_reason | turn 2 stop_reason | same session_id | turn 1 s | turn 2 s | turn1 cachedReadTokens | turn2 cachedReadTokens |
|---|---|---|---|---|---|---|---|
| claude-code (claude-opus-5-5, acp 0.81.2) | end_turn | end_turn | yes (no 2nd session/new sent) | 4.4 | 5.1 | 35763 | 41467 |
| codex (gpt-6-sol, acp 1.12.0) | end_turn | end_turn | yes | 9.4 | 10.7 | 11008 | 16384 |
| copilot (gpt-6-sol, native ACP 1.0.89-1) | end_turn | end_turn | yes | 8.8 | 4.2 | 17790 | 30332 |

Final tree after turn 2, all three harnesses identical: `a.txt` = `2`, `b.txt` = `done` (sha256-verified
in each summary; turn 1's intermediate tree, `a.txt` = `1` only, was hashed and recorded before turn 2
was sent, satisfying the "snapshot before turn 2" requirement at the probe level).

**Context carried from turn 1 into turn 2 (Verified, by cache growth, not by model self-report):** every
harness's `cachedReadTokens` on turn 2 is larger than turn 1's *total* input, with no second
`session/new`/system prompt resent -- the adapter's own prompt cache only grows across calls that share
the prior conversation prefix. This is strong evidence the conversation (not just the file on disk) rode
along. Caveat: prompt 2 explicitly named `a.txt`, so this run does not isolate "knows about a.txt
without being told" from "re-reads the file from disk" -- a strictly tighter probe (prompt 2 says
"the file you just created" with no filename) would close that gap; not run here, named as the open item.

**Per-turn usage (Verified, available on all three):** every harness returned `usage`/`_meta.quota` in
the `session/prompt` RPC's own result for *both* turns, independently keyed per call. This is the
`acp_turn` usage source; it is what the probe used. Note the production profiles pick different canonical
sources per harness (`bench/profiles/claude-code.yaml`: `usage_source: acp_turn`; `codex.yaml` and
`copilot.yaml`: `usage_source: native_record`, with the YAML's own comment that the ACP-level report is
incomplete for those two in some cases) -- this spike confirms the ACP-level per-turn figure exists on
all three, not that it is already the engine's chosen source for codex/copilot.

**No errors, no protocol refusal, no permission block** on any harness for either turn. Claude Code's
adapter stderr showed only its own benign `session/create`/`session/models` phase-timing lines (no
`session/request_permission` was observed; the static per-profile allowlists already cover `Write`).

**Raw evidence:** `<cells-root>/e4-<harness>-<timestamp>.summary.json` per run (sha256 file hashes per
turn, full `usage`/`_meta`, argv, agent_version, stderr tail). Written to `C:/Projects/e4-spike-cells/`
(sibling of the worktree, per the "never write to .../x-harness-x-model-bench/runs/" instruction) --
not committed (raw, may carry local paths); this note is the committed record.

## What the engine would need to change to support a real second turn (DR-E4, C-E12)

1. **`driver.py`** -- `run_turn` (lines 249-313) is a closed one-handshake-one-prompt function; it has no
   way to send a second `session/prompt` on an already-open channel. It needs either (a) a second,
   smaller entry point that takes an already-open channel/session and sends one more prompt, reusing
   `_Channel.rpc` (as this spike does directly), or (b) `run_turn` refactored into "open" + "send one
   turn" so the engine can call "send one turn" twice before "close". `TurnResult` (lines 90-111) models
   one turn; the engine needs a per-turn result (e.g. a list) rather than one mutable `TurnResult` that
   a second call would overwrite.
2. **`engine.py` `_attempt`** (lines 684-747) -- the `finally` at line 728 always proceeds to
   `_end_process` (line 732), which closes stdin at `_end_process` line 752 and then force-confirms the
   kill. This runs unconditionally right after the single `run_turn` call returns, including on a clean
   `end_turn`. For a rework task, the attempt must recognize "this cell's task has a turn 2" and keep
   the process alive (skip `_end_process`) until turn 2's prompt has been sent and has itself returned.
3. **Turn snapshot archive** (C-E12, "the turn-1 tree is archived as a turn snapshot before the turn-2
   message is sent") -- no such primitive exists. `archive.archive_cell` (archive.py:55-58) writes
   `attempt-{attempt}` and explicitly refuses to write the same attempt twice. A turn snapshot needs
   either a new folder dimension (`attempt-{attempt}-turn-{n}`) or a dedicated function distinct from the
   final attempt archive.
4. **Attempt/record model** -- `attempt` is hardcoded to `1` at every record site (engine.py:665, 719,
   810); the Cell aggregate (per the spec's amended table) now allows "at most one prompted attempt,
   which may hold more than one turn" -- the records need a turn index alongside the attempt index so a
   reader can tell turn 1's events from turn 2's (today `cell.prompt_sent` and `attempt.process_started`
   are each emitted once per attempt, not once per turn).
5. **The ack barrier** (`before_send`, driver.py:294, consumed at engine.py:710-714) records
   `attempt.session_opened`/`cell.prompt_sent` once, at handshake time. Turn 2 needs its own
   "prompt sent" record without repeating the handshake record.

None of claude-code's, codex's or copilot's ACP adapters themselves were the blocker in this probe -- the
session-level contract already supports a second turn on all three. The blocker is the engine's own
one-shot `run_turn`/`_attempt` lifecycle, named above.

## What was not proven

- **macOS is unverified.** This spike ran only on the operator's Windows 11 host (ADR-0013 section 5:
  Windows or macOS are the only supported hosts). The ACP adapters are the same npm packages on both
  platforms (tools.py's `LAYOUT`/`_DARWIN_TARGET_TRIPLE`), but the ACP session behaviour on macOS, and
  any platform-specific process/stdio quirk, was not exercised here.
- The tighter "knows about the file without being told" isolation (prompt 2 naming no filename) was not
  run -- see caveat above.
- Behaviour under a *third* prompt, a cancelled turn 1, or a turn-1 failure before `end_turn` was not
  probed; DR-E4 only requires turn 2 after a clean turn-1 end.
- Whether the adapter processes hold the conversation in memory indefinitely (a resource/leak question
  for a long-running rework cell) was not measured; only two short turns were sent.
