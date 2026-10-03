---
id: coordination-eval-q0
title: "Q0: harness qualification for the Evaluation Campaign build (Codex 0.160.0, Agy 1.2.13, Grok 1.0.41)"
type: plan
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: serial spine item 1 (Q0)"
tags: [coordination, qualification, coord-runner, evaluation-campaign]
links:
  - { to: coordination-eval-campaign, rel: implements }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  The Q0 runner contract (q0-contract.json) and the Leader's command sequence through the operator-approved wrapper:
  one smoke turn each for Codex 0.160.0 / gpt-6.1-sol, Agy 1.2.13 / gemini-3.8-flash-high and Grok 1.0.41 / grok-4.7
  (high), in one run with parallelism 3, then the served model read back per worker.
---

# Q0: harness qualification

**Contract:** `docs/coordination/eval-q0/q0-contract.json` (`coord-run/1`, run id `q0-e1e4`, owner `leader-e1e4`, 3 workers, parallelism 3, 600 s each). Each worker gets one turn: the already-compiled qualification prompt `al-01M38J29Z3V8YNRWCNF44W9XDC` ("create `docs/notes/qualify-worker.md` with one line and commit only that file"), the same prompt qualify-5 and qualify-codex-2 used. The runner prefixes each prompt with the worker's own `start` line (`coord-runner.py:300-304`).

**Argv source, per worker (copied, not invented):** Codex = `qualify-codex-2`'s adapter argv and runtime. The wrapper's `CODEX_PATH` points the adapter at the global 0.160.0 exe; the adapter reads `CODEX_PATH` (`codex-acp/dist/index.js`, read 2026-10-03). Agy = `w5-b2`'s argv. Grok = `w4-lr`'s argv.

## Commands (the Leader, in order, from any shell)

```
W=C:/Projects/x-harness-x-model-bench/.tools/coord/runner-leader.sh
env -u XAI_API_KEY sh $W prepare --contract docs/coordination/eval-q0/q0-contract.json
env -u XAI_API_KEY sh $W fingerprint --run q0-e1e4
#   write the attestation (template below) with the three fingerprints, as a file outside the repo
env -u XAI_API_KEY sh $W run --run q0-e1e4 --qualification <attestation.json>
env -u XAI_API_KEY sh $W status --run q0-e1e4
```

- **`env -u XAI_API_KEY` on every call.** The runner passes `os.environ` to the workers (`coord-runner.py:226`), and the plan's phase-1 rule launches Grok with `XAI_API_KEY` removed. The wrapper does not unset it. The fingerprints must be computed in the same environment the run uses (the wrapper's own comment).
- Run the four calls with `main` at W0's merge, so the workers' base includes this folder.

**Attestation template** (`coord-qualification/1`; one entry per worker; the fingerprint comes from the `fingerprint` call):

```json
{"schema": "coord-qualification/1", "workers": {
  "worker-codex-q0e": {"fingerprint": "<from fingerprint>", "version": "codex-cli 0.160.0 (global npm exe via CODEX_PATH), codex-acp adapter from .tools/harness, model gpt-6.1-sol, reasoning high (CODEX_CONFIG)",
    "evidence": "Q0 smoke turn; profile of qualify-codex-2 with the 0.160.0 exe", "effective_policy": "agent-full-access, approval never, permissions deny (runtime)",
    "trust": "AGENTS.md bound; the pack's Codex hook is unexercised under Codex (plan: unsupported); ownership holds at the commit floor",
    "capabilities": {"worktree_isolation": "observed-only", "instructions": "observed-only", "hooks": "observed-only", "permissions": "observed-only"}},
  "worker-agy-q0e": {"fingerprint": "<…>", "version": "agy 1.2.13, native stream-json, --mode accept-edits, --model gemini-3.8-flash-high", "evidence": "Q0 smoke turn; last qualified at 1.2.3 (qualify-5)", "effective_policy": "accept-edits", "trust": "Pack hooks (.agents/hooks.json) bound", "capabilities": {"worktree_isolation": "observed-only", "instructions": "observed-only", "hooks": "observed-only", "permissions": "observed-only"}},
  "worker-grok-q0e": {"fingerprint": "<…>", "version": "grok 1.0.41, -m grok-4.7 --reasoning-effort high, ACP stdio", "evidence": "Q0 smoke turn; same version as qualify-5 and w4-lr", "effective_policy": "default", "trust": "Pack hooks (.grok/hooks/ai-forward.json) bound; XAI_API_KEY removed", "capabilities": {"worktree_isolation": "observed-only", "instructions": "observed-only", "hooks": "observed-only", "permissions": "observed-only"}}}}
```

## What Q0 must read back (exit evidence for the Coordinator)
1. Per worker: `status` shows the commit and the file evidence (`docs/notes/qualify-worker.md`, one line, only that file in the commit).
2. **The served model, per worker,** read from the run's transcript or native record, not from the argv: `gpt-6.1-sol`, `gemini-3.8-flash-high`, `grok-4.7`. A different id means that harness is `unsupported` for this plan, and its tracks take their fallback.
3. The Codex binary that ran is 0.160.0: the native session record's CLI version, or the adapter's log line.
4. **Not testable through this wrapper:** the plan's *assume:* that a follow-on dispatch can be prepared from a linked tree. The approved wrapper always `cd`s to the primary checkout, so the runner's base is always the primary's HEAD (`coord-runner.py:426`). Consequence: a green-after-red follow-on cannot start from the red branch tip through the runner. Until the wrapper takes the invoking tree, a follow-on runs either (a) as a Claude Sonnet sub-agent in the same tree (the plan's stated fallback), or (b) in a fresh external dispatch that does red and green in one turn. The Coordinator records this in the plan's harness table after Q0.
5. A `claude` runner worker is **not** in this contract. R-87 condition 5 allows one, but its argv and its model pin through the runner are unexercised (0 of 106 runs). Sonnet tracks use the Agent tool (R-87 Option 1). Adding one is a later, separate contract.

## Q0 result (run `q0-e1e4`, 2026-10-03; verified by `coord-opus-e1e4`)

Run state `ready_for_review`, epoch 13, 138 s. Each worker completed 1 turn with 0 permission requests, 0 native denials and 0 tool errors. Each commit adds exactly one line to `docs/notes/qualify-worker.md` and touches nothing else (`git show --stat`, read by the Coordinator).

| worker | wall | commit | version (evidence) | served model (evidence) | verdict |
| --- | --- | --- | --- | --- | --- |
| `worker-codex-q0e` | 68.6 s | `6676e9d2` | codex-cli **0.160.0** (native record `cli_version`); adapter 1.12.0 (`agentInfo.version`) | **`gpt-6.1-sol`**, effort high (`~/.codex/sessions/2026/10/03/rollout-2026-10-03T10-01-43-01a102b6-e540-76c2-b6c1-05c332032bcc.jsonl`) | observed-only: **qualified** |
| `worker-agy-q0e` | 135.3 s | `344a9b24` | agy **1.2.13** (`~/.gemini/antigravity-cli/cli.log`) | **`gemini-3.8-flash-high`** (`cli.log` model resolution; conversation store `64e95f68-….db` `executor_metadata`) | observed-only: **qualified** |
| `worker-grok-q0e` | 71.6 s | `b732b3ea` | grok **1.0.41** (`_meta.agentVersion`) | **`grok-4.6`** (ACP `selected_model`; `~/.grok/sessions/…q0-grok-e1e4/01a102b6-e198-…/summary.json` `current_model_id`; `chat_history.jsonl` `grok-4.6-build`) despite `-m grok-4.7` | **unsupported at the pin** |

- The runner reports `selected_model` null for Codex and Agy because neither adapter returns one. The native records are the evidence.
- Not tested, as stated above: a follow-on dispatch prepared from a linked tree (the wrapper always runs from the primary checkout).
- Grok: a decision request to `owner-fable` asks for the route of the four Grok tracks. None of them starts before W1-G or W1-B passes its gate, so nothing waits on it yet.
- The three `q0-*` branches and trees are qualification-only, never joined. After this review they are removed through `coord worktree cleanup` (WT8 checks).
