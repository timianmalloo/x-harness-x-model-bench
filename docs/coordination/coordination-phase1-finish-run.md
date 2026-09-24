---
id: coordination-phase1-finish-run
title: "Run record - coordination-phase1-finish"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [coordination, run-record, planned-vs-actual]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  What happened when the phase-1 finish plan was executed: the measured qualification of grok and agy (both failed;
  ruling R-4 moved the tracks to Claude Code), the mutation-tool probes, the hardened checker's findings, and
  planned against actual time for each track.
---

# Run record: coordination-phase1-finish

## Steps 1–3 (Coordinator, 2026-09-24)

| step | planned | actual (measured) |
| --- | --- | --- |
| 1. leader | pin `coord-opus` | pinned at epoch 1. The TTL cap is 900 s, so the plan's idea of a long TTL was refused (`COORD-LEADER-TTL-CAP`); a background loop renews every 90 s. The loop's first version passed `--host` to `renew`, which does not accept it: every renewal failed until read back and fixed |
| 2. qualify transports | one smoke turn each through `coord-runner` | run `qualify-1`. **grok 1.0.30**: `protocol_error` 2.4 s after the prompt started, 0 turns; the requested model was not set (`selected_model_set: false`, grok reported `grok-4.7`). **agy 1.2.3**: `blocked` by one native denial in `accept-edits`, 0 turns. Neither worker changed any file (both trees clean at base). Ruling **R-4** applied the Claude Code fallback |
| 2. probe R13 | mutmut on Windows | mutmut refuses native Windows ("please use the WSL"). WSL has Ubuntu-24.04. **cosmic-ray 8.7.0 installs natively**, so T1 and T2 use it natively; the engine's Job Object paths cannot run under WSL |
| 3. harden `mutate_check` | before fan-out | commit `ae6e8f0`. Under the new rule (a kill needs exit 1 with a named test failing) the first sweep showed 5 entries not killed. 4 were the checker's own bug: a parametrized case fails as `name[param]`, which was then fixed and tested. 1 was real: `engine.json`'s "budget never enforced" was only ever "killed" by a timeout. T1 owns it |
| 3. rulings | the Owner rules on R-2 and R-3 | the Owner seat (Fable) ruled R-2 (a), R-3 (a) and R-4 (a), with conditions; see `docs/notes/rulings.md` |

## Harness and tool findings (for the human)

- **Agent tool worktree isolation refused, twice.** The session's cwd is `C:\projects\…` and git reports `C:/Projects/…`; the tool compared the two case-sensitively and refused both of its own worktrees ("a core.worktree redirect, or a checkout discovered above it"). Two locked, unused worktrees remain under `.claude/worktrees/agent-*` (created by the tool, holding no work). They were not removed; that is left to the human. The tracks run instead in trees made with `coord worktree new`, the skill's own Stage 2 path.
- **Next steps for the human (R-4 conditions):**
  - upgrade grok to 1.0.34 or later, and re-qualify it;
  - decide whether agy may run in a mode that allows shell commands;
  - R-1 stands for re-qualification.

## Tracks: planned against actual

**Where the spend figures come from:** the harness's completion notice for each sub-agent reports `tool_uses`, `duration_ms` and `subagent_tokens`. Duration is wall clock from dispatch to the last stop, so a resumed track's figure includes the time it waited. What `subagent_tokens` counts is not documented here, so it is reported as given (Inferred: the context at the stop, not cumulative spend).

| track | harness (planned → actual) | joined | budget → spend (calls · wall) | tokens reported | exit evidence verified by the Coordinator |
| --- | --- | --- | --- | --- | --- |
| T1 engine-hardening | agy `claude-opus-4-6-thinking` → Claude Code, Opus (R-4) | `9c32b00` | 450 calls · 8–12 h → **415 · 5.4 h** | 599,619 | two red SHAs re-run; `engine.json` 44/44 killed; cosmic-ray record checked current |
| T2 ledger-verify | grok `grok-4.7` → Claude Code, Opus (R-4) | `e69dc38` | 350 calls · 5–7 h → **297 · 2.3 h** | 426,970 | two red SHAs re-run; cosmic-ray record (1803 mutants, 0 open) checked current |
| T3 process-edges | agy `gemini-3.1-pro-high` → Claude Code, Opus (R-4) | `eb3ac27` | 250 calls · 4–6 h → **145 · 0.42 h** | 258,945 | two red SHAs re-run; `t3.json` 15/15 killed |
| T4 surfaces | grok `grok-4.6` → Claude Code, Sonnet (R-4) | `861ac76` | 200 calls · 3–5 h → **199 · 0.60 h** | 351,893 | status 12/12, report 21/21, cli 11/11 killed; frontmatter `type` corrected at the join |
| T5 n5-spike | grok `grok-4.7-build-fast` → Claude Code, Sonnet (R-4) | `f47c5c9` | 120 calls · 3 h → **88 · 0.25 h** | 139,473 | negative result; the canary run observed; ruling R-5 |
| T6 workspace-race (loop-back, unplanned) | Claude Code | `51a39e1` | none planned → **34 · 0.12 h** | 103,671 | red `0082875` re-run; `workspace.json` 2/2 killed |
| T8 reader-and-paths (loop-back, unplanned) | Claude Code | `0e24cb9` | none planned → **98 · 0.27 h** | 185,688 | both red SHAs re-run; `t8.json` 2/2 killed; fixture scanned |
| T9 cleanup-and-log (loop-back, unplanned) | Claude Code, Sonnet | `81c5b10` | 60 calls · 1 h → **81 · 0.25 h** | 156,927 | red `e225ff5` re-run (4 of 4 failed as stated); `t9.json` 3/3 killed; `engine.py` diff confined to `configure_logging`. **Over its call budget, 81 against 60.** Cause (Inferred): the budget did not allow for the four-test red set across three test files |

T6, T8 and T9 are loop-backs. Each real E2E found defects in files owned by tracks that had already closed, so the loop-back rule reopened them as small fix tracks. T7 is the Coordinator's own close (this record). No planned track exceeded its call budget. T9, a loop-back, did (81 against 60), and that is a signal about how T9's budget was set, not a reason to raise the next one. Every planned track finished well under its wall-clock estimate. The estimates were Inferred and too high by a factor of 2–14.

**Which of the plan's parallelism justifications paid:**
- **T1–T4 independence: paid.** Their authored paths stayed disjoint. No file was authored by two tracks. Every join passed `conductor-join`'s conflict-marker gate at the first attempt. T1 and T2 each merged `impl/phase1` into their own branch before joining; those merges were not inspected for hand resolution.
- **The seams worked as seams:**
  - T1→T3's `last_update_seconds` (req-01M38KX8503601BEP857749VVF) stayed open, so `last_update_ms` records null, a disclosed residual;
  - the N5 flag reached T4 as a seam request.
- **Context hygiene: paid.** T1 alone used about 600k reported tokens across 17 items. One session holding T1–T4 would have gone past the 400k ceiling.
- **T5 machine time: paid, and cheaply.** The spike took 15 minutes against a 3-hour budget, because the negative result came early.
- **Starting early was right.** T3–T5 were started about 30 minutes into T1/T2. No rate limit was observed.

## Coordinator decisions during the fan-out

- **T3–T5 started early.** The plan held them until T1 and T2 returned, to guard against an *inferred* rate-limit risk. After about 30 minutes, two concurrent agents had produced 29 and 15 commits with no rate limit observed, so the Coordinator started T3–T5 then. If rate limits appear, T4 and T5 pause first.
- **Two join gates stopped a join; both were real.**
  - After the T5 join, `docs-graph validate` found the index out of date. `docs-graph derive` was added to `join.json`'s regenerate step.
  - At the T4 join, T4's findings file carried `type: proof`, which the docs graph does not know. It was corrected to `proof-pack`.
- **Loop-back tracks.** The real E2E was run three times.
  - Run 1: the workspace race (T6).
  - Run 2: all 4 cells valid, but US-10 failed on Codex pack-on, and a relative `--tools-dir` broke the pack install (T8).
  - Run 3 (`e2e-1790237978`): green, which is M1. It also exposed two cleanup defects (T9).
  - Run 4 (`e2e-1790239442`), after the T9 join: green, and the run's folder was removed. That is M1 on the final code.
- **Close checks (T7):**
  - all 13 mutation files (188 entries) killed at `d13b222`;
  - all cosmic-ray records current (the `engine.py` diff is confined to the out-of-scope `configure_logging`);
  - the Proof Pack is at `docs/proof/phase1.md`.
- **The Coordinator's own close work (T7), with one boundary correction.** T7 took `tools/heredoc_guard.py` and `tests/test_heredoc_guard.py`, which no track owned, to build the E2E-E control. That control was red at `291468b` and fixed in `727cbb4`.
- **Boundary correction.** Ruling R-3 requires `skills/start-benchmark/SKILL.md`'s `bench-status/1` field list to change in the same commit as `status.py`. The plan gave that file to no track, so it went to T4. Its synced copies stay derived (regenerated by `tools/sync-skills.py`).
