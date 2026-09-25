---
id: coordination-finish-harness-bench-run
title: "Run record - coordination-finish-harness-bench"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses"
tags: [coordination, run-record, planned-vs-actual]
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  What happened when the finish-harness-bench plan was executed: qualifications, gate rounds, dispatches, slice
  joins, capture windows and planned against actual per track.
---

# Run record: coordination-finish-harness-bench

## Setup (Leader `coord-opus-cq`, 2026-09-24)

| step | result (measured) |
| --- | --- |
| Codex qualification | `qualify-codex-1` (default mode; its escalations were approved by Codex's own model reviewer) and `qualify-codex-2` (`agent-full-access`, selected). See `coordination-phase1-finish-run.md` (commit `e22ca74`) |
| Owner rulings | R-7, R-8, R-9 by the Owner seat (Fable): 44 tool calls, 465 s, 137,703 subagent tokens (as reported). Commit `0a64b0c` |
| Compile | raw `al-01M3AKF5D9FSZ2BE0ARDZCXNKQ` → compiled `al-01M3AKF6FZSG1RCB5FB5MR3C76`, dispatchable. One refusal first: the raw prompt named a forbidden construct, so it was rephrased and recompiled |
| Layer | `req-01M38KX8…` expired with its recorded fallback; `coord doctor` requests ok |
| W0-QUAL (`qualify-6`) | **Grok 1.0.41, no model pin:** `ready_for_review` in 101 s, 1 turn, 0 permission requests, 5 compatibility responses; ACP `selected_model: grok-4.7`. **Agy 1.2.10, no model pin, `accept-edits`:** `ready_for_review` in 75 s, 1 turn, 0 native denials; the conversation store shows executor `gemini-3.8-flash-high` and 17 generations on `gemini-3.8-flash`. Both commits touched only `docs/notes/qualify-worker.md`. The branches were qualification-only and were deleted |
| Stage 8 gate | round 1: Test Architect BLOCK, Tech Lead PASS WITH CONDITIONS, Simplifier BLOCK. Version 2 applied every finding or recorded a rationale. Round 2: Test Architect and Simplifier cleared their vetoes. Spend as reported: Test Architect 14 + 4 calls; Tech Lead 15 calls; Simplifier 25 + 5 calls |

## Correction

The 31-row to-do list said row 11 (power request) was "not built". It was built and wired in phase 1 (`host.py:89`; `engine.py:216/258`). The Simplifier found this at the gate, and the Leader verified it. Row 11 is closed by citation.

## Tracks: planned against actual

Wave 1, 2026-09-24/25. The times are committer times of the joins on `main` (local clock). A session duration is the closing audit entry's measured `duration_seconds`, where one exists. "planned" is the plan's harness column.

| track | planned harness | actual harness · model | budget | actual | joined (`main`) | exit evidence verified by the Leader |
| --- | --- | --- | --- | --- | --- | --- |
| W1-COP-D | Claude Opus 5.5 | as planned | 150 calls · 2 h | 4 design rounds: 1495 + 458 + 795 + 178 s (≈ 49 min) | `2e9cc3b` 15:38 (squash; REG-A) | design rev 3.1; ADR-0006 Amendment 1; scrubbed fixtures |
| W1-ACP | Claude Opus 5.5 | as planned | 260 calls · 4 h | not recorded as one duration | `124af8e` 15:50 | 11 reds re-run; Codex review F2 fixed red-first; `driver.json` 5/5 killed |
| W1-PACK (-2) | Claude Opus 5.5 | as planned, upstream | 150 calls · 2 h | revisions 94 and 95 (`df3baf2`) | ai-forward `origin/main` | runner limits (R-11), `protocol_error` detail, the hooks under `pwsh`. Pulled in here by `/updatepack` 93 → 95 |
| W1-HOST | Grok (`grok-4.7`, default) | slices 1–3 Grok (unpinned); slice 4 Claude Sonnet 5 (R-29, after a Grok `protocol_error`) | ≤ 3 slices | 4 slices; slice 4 took 221 s | `2b5743b` 14:42 · `7d73ada` 15:05 · `c57cbcb` 15:18 · `6cf7755` 15:28 | reds re-run; Test Architect veto cleared (`2f8c645`) |
| W1-TOOLB | Agy (`gemini-3.8-flash`, default) | Claude Sonnet 5 (R-10, after Agy's `native_tool_error`); follow-up Claude | ≤ 2 slices | 1 + a follow-up | `f141610` 15:05 · `a9f8bbc` 16:07 | red re-run; Codex review CLEAR; no-summary → `error` (CLN-B tool side) |
| W1-COP-R | Grok (default) | Claude Sonnet 5 (R-29: Grok held for new runner tracks) | ≤ 2 slices | 1233 s + a join-fix round | `791dba2` 16:31 | Codex review BLOCK and Test Architect BLOCK fixed; `copilot_reader.json` 21/21 |
| W1-COP-I | Codex `gpt-6-sol` | Codex `gpt-6-sol` (slices 1–5, 6a, 6b), plus loop-backs: fix (Claude Sonnet), L2 (Claude Opus), R-32 (Claude Sonnet, 1605 s), R-34 (Claude Opus, 773 s) | ≤ 5 slices × 55 min | 7 Codex slices + 4 Claude loop-backs | `b7ce26e` 16:02 … `da14061` 19:34 | the claim table in `docs/proof/phase2.md` (Join: W1-COP-I); Test Architect 47/47 kills at `da14061` |
| W1-CAP2 | Leader seam | Claude subagent (2 phases: 679 + 1129 s) | — | 30 min | `dc15d99` 18:15 | Copilot recording in D5/D7; rev-95 pack-on fixture swap |
| Wave-1 exit | Leader | Leader | 6 cells | 147 s | `4724248` 19:41 | `e2e-wave1-1790303859`: 6/6 valid, all assertions (`docs/proof/wave1-e2e-last.json`) |

**Planned against actual.**
- **Two of three runner harnesses were replaced mid-wave.** Agy (W1-TOOLB) failed on a runner limit (R-10). Grok finished 3 of 4 slices, then hit a `protocol_error` with no detail recorded (R-29). Both limits were fixed upstream in revision 95, and the re-qualification is `qualify-7`. Codex ran every W1-COP-I slice to a commit, with no R-4 fallback.
- **Loop-backs: 4 unplanned, against a reserve of 2.** Two came from served-model and tool-id facts that only a live cell showed: the `[1m]` tag (R-32) and `PowerShell` (R-34). The other two came from review findings (6a, 6b).
- **Negative runs on the way to the exit:**
  - `e2e-wave1-1790299304`: model mismatch, fixed by R-32;
  - `e2e-wave1-1790302505`: US-14 failed on `PowerShell`, fixed by R-34.
- **Leader misses, now registered:** SUITE-A, REG-A, GATE-B, CLN-B, COORD-B (`docs/lessons/defect-classes.md`).
- **Wave-1 close, 2026-09-25:**
  - **`/updatepack` 93 → 95** (`65075f2`, joined at `51ffb68`). Source: the revision-95 checkout `df3baf2`. Result: 14 UPDATE, 2 MERGE, 0 CONFLICT; pack-doctor 0 FAIL; offline suite 817 passed.
  - **`qualify-codex-3`**, the R-33 pin (`CODEX_CONFIG` model `gpt-6-sol`, effort `high`): `ready_for_review` in 68.5 s. The rollout's `turn_context` shows `gpt-6-sol`, effort `high`, `approval_policy: never`, `danger-full-access`. The operator's `~/.codex/config.toml` sets the same model and effort, so the run confirms the served model but cannot tell the pin from the default.
  - **Codex ownership hook: not qualified.** `qualify-codex-4` forced `apply_patch` on a path leased to the Owner, and the patch was **applied**; no ledger decision carries `hook_host: codex`. `qualify-codex-5` placed three marker hooks (`UserPromptSubmit`, `PreToolUse` `apply_patch` and `exec`), and none fired. Two measured facts:
    - codex-cli 0.156 on `gpt-6-sol` runs in code mode: every action is one `exec` call, with `tools.apply_patch` and `tools.exec_command` nested inside it.
    - Hook trust is stored per source path and hash (`[hooks.state]` in `~/.codex/config.toml`).
    - The three runs put the hook only in the worker tree. The launch reference says discovery in a linked worktree comes from the primary checkout (RIG-D instance).
    - **Next, operator-gated:** add the emitter's entry to the primary's `.codex/hooks.json`, and the operator reviews it through native `/hooks`. Then one run measures whether `PreToolUse` `apply_patch` fires for a nested `tools.apply_patch`.
    - Until then ownership for Codex is enforced only at the git pre-commit floor: in `qualify-codex-4` the leased file was written but not committed. Capabilities stay `observed-only`.
  - **`qualify-7`, models stipulated:**
    - **Grok 1.0.41** (`-m grok-4.7 --reasoning-effort high`): `ready_for_review` in 79 s, 1 turn; ACP `selected_model: grok-4.7`; no `protocol_error`. `grok models` reports `XAI_API_KEY` authentication in the operator's environment (disclosed; unchanged).
    - **Agy 1.2.10** (`--model gemini-3.8-flash-high`, the id `agy models` lists; `gemini-3.8-flash` is not an accepted id): `ready_for_review` in 68 s, 0 denials. `executor_metadata` shows `gemini-3.8-flash-high`, and `gen_metadata` shows 18 generations on `gemini-3.8-flash`.
    - Both pins equal the operator default, so the same limit applies as for Codex. The R-11 Agy hold and the R-29 Grok hold lift for new runner tracks.
  - **R-35/R-36(a)** (Claude Sonnet 5, 69 tool calls, 647 s): joined at `6e7ae50`. The Leader tightened two tests at the join (TEST-A).
- **Also done:** the A9 host-sleep probe (`docs/notes/spike-a9-host-sleep.md`); A3 partial (host credentials unchanged across two runs); the R-36 connector comparison (the same 8 account tools pack-on and pack-off).
