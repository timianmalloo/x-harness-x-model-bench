---
id: note-20261008-spike-s-j4
title: "Spike S-J4 - is the first session/update after the adapter's lazy helper spawns?"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [spike, acp, multi-turn, job-object, baseline, S-J4]
links:
  - { to: design-eval-multi-turn, rel: relates-to }
review-by: "2026-12-24"
summary: >-
  Verified on all three harnesses (Windows host; macOS unverified): the Job Object process count at the
  first session/update of turn 1 (B) is at least the count at the end of a no-tool turn 1 (C), so the
  W1-J section 4.4 assume: holds on Claude Code, Codex and Copilot. Counts A/B/C: Claude Code 4/6/4,
  Codex 4/4/4, Copilot 2/2/2.
---

# Spike S-J4: the helper-before-first-update order

**Question (W1-J section 12, row S-J4):** is the first `session/update` of turn 1 after the adapter's lazy
helper spawns, on each real adapter? Section 4.4 carries it as an `assume:`: a helper the adapter spawns lazily
at the first prompt exists by the time the adapter streams its first update; it holds where the first-update
count is at least the end-of-turn count of a no-tool prompt.

## Method

`tools/spikes/s_j4_baseline.py` (commits `5ac5857f`, then `94d8239b`, which only changed tokens to "not recorded"
when a native record names no model call and added the adapter's usage field). It uses the engine's own launch path:
`profiles.load`, `profiles.ProfileLauncher` (`check_build`, `argv_env`, `seed`, `clean`), `procs.spawn`,
`driver.open_session`, `driver.send_turn` with `on_first_update`. Cell home and working folder are under
`C:\tf\xsj4\<harness>\`. Count `job.active` (through the engine's `_job_query`):

- A: right after `driver.open_session` returns (after `session/new`).
- B: inside `on_first_update` (the first `session/update` of turn 1).
- C: right after `send_turn` returns turn 1.

Prompt: "Reply with the single word OK. Do not use any tool." One turn per adapter. The process is ended the
engine's way (stdin closed, job drained) and `clean_home` removes the credential copy.

## Host facts (Verified, measured here)

| Harness | Pin | Build | ACP adapter | Served model (as reported) |
|---|---|---|---|---|
| Claude Code | `claude-opus-5-5` | 2.1.282 | `@agentclientprotocol/claude-agent-acp` 0.81.2 | `claude-opus-5-5` and `claude-haiku-4-5-20251001` (an auxiliary call) |
| Codex | `gpt-6.1-sol` | 0.156.0 | `@agentclientprotocol/codex-acp` 1.12.0 | not recorded (the record and the ACP report name no model call) |
| Copilot | `gpt-6.1-sol` | 1.0.89-1 | none (native `--acp`) | `gpt-6.1-sol` |

Host: Windows 11; macOS unverified. Tools folder: the primary's `.tools\harness`, read only.

## Counts (Verified: each measured here)

| Adapter | A (after `session/new`) | B (first update) | C (end of turn 1) | B >= C | Tokens | Outcome |
|---|---|---|---|---|---|---|
| Claude Code | 4 | 6 | 4 | yes | 21,447 | completed, `end_turn`, no tool call, 5 updates |
| Codex | 4 | 4 | 4 | yes | not recorded | completed, `end_turn`, no tool call, 6 updates |
| Copilot | 2 | 2 | 2 | yes | 5,787 | completed, `end_turn`, no tool call, 7 updates |

Codex tokens: its rollout record holds no token-count event for this turn and the ACP report is empty
(`model_usage: []`), so the figure is not recorded. Codex was run twice: the first run used the script before
`94d8239b`, and its figures were A 4, B 4, C 4 and a token field of 0, which that commit corrected to "not
recorded"; the second run is the one in the table.

## Verdict on the section 4.4 `assume:` (this host, Windows; macOS unverified)

The `assume:` **holds on all three adapters** (B >= C on each). No W0 amendment of the read point is indicated by
this spike. Two readings carry weight:

- Claude Code: B (6) is above both A (4) and C (4). Two helpers are alive at the first update and gone by the end
  of the turn, so the first-update read point sees the larger tree, which is the safe side for the filter; the
  end-of-turn count would under-read it.
- Codex and Copilot: the tree is flat (4/4/4 and 2/2/2) on a one-word turn; no lazy helper was visible at these
  instants, so for these two the order is not contradicted but also not exercised.

Limits: one run per adapter and one no-tool prompt; a helper that lives for less than the sampling instant is
invisible. The Coordinator writes the result into W1-J section 12.
