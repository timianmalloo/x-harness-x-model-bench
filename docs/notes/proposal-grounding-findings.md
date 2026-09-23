---
id: "note-proposal-grounding-findings"
title: "Proposal grounding findings (scaffold pass)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [benchmark, findings, open-questions]
links:
  - { to: proposal-cross-harness-benchmarking, rel: refines }
review-by: "2026-10-23"
summary: >-
  What the scaffold pass found when it checked the proposal against the mockup and the pack's
  real coord-runner.py: inconsistent task counts, a worker-isolation seam between "fresh clone per
  run" and coord-runner's worktrees, runner limits the design must fit, and gaps with no owner.
---

# Proposal grounding findings (scaffold pass)

Date: 2026-09-23. Pack: ai-forward revision 92, installed from a local ai-forward clone (that clone was 2 commits ahead and 2 behind `origin/main` at install time).

Each finding carries a confidence label and the spec that must resolve it (`docs/specs/README.md`).

## F1. Worker isolation: fresh clone vs coord-runner worktrees — S-02 (blocking)

**[Verified]** The proposal says each run gets "one fresh clone per run: `git worktree`-free, cloned from the task's base commit". It also says every cell is a worker launched by `coord-runner.py`. These do not fit together. `coord-runner.py prepare` makes each worker's worktree from the **invoking checkout** on a new branch (`validate()` checks the branch in `self.cwd`; `prepare()` calls `core.cmd_worktree(..., "new", self.cwd, ...)`). If the coordinator invokes it from this repo, workers start in a worktree of the **bench repo**, not of the task's source repo.

**[Inferred]** Running coord-runner from inside each task clone instead would write coordination state (`.agents/`, logs, bindings) into the clone. For `pack=off` that puts pack artifacts into the control workspace.

Options for the ADR: (a) extend coord-runner with a per-worker external workspace; (b) run coord-runner from inside each task clone and strip coordination state before grading; (c) make each task's workspace a subtree of the bench repo's worker worktree. Decide before building the runner.

## F2. coord-run/1 limits the design must fit — S-05

**[Verified]** from `coord-runner.py` `validate()`:

| Limit | Value | Consequence |
| --- | --- | --- |
| Workers per contract | 1–8 | Full grid of 528 cells needs 66 contracts; smoke needs 18 (`bench plan` prints this) |
| Parallelism | 1–4 | At most 4 cells run at once per contract |
| `deadline_seconds` | ≤ 3600 | No task budget may exceed 60 minutes. F1/F2 budget is exactly 60, leaving no headroom |
| `runtime.max_turns` | 1–8 | These are prompts sent over ACP, not agent tool turns. The proposal's per-scenario "turn cap" needs a different enforcement point |
| `prompts` | 1–8 compiled `/compile` audit ids | Scripted-user answers (A-tasks) cannot be pre-compiled prompts; see F4 |
| Transport | ACP for claude, codex, grok, copilot | See F3 |

`bench validate` already refuses any BOM budget over 60 minutes.

## F3. Headless CLI flags vs ACP transport — S-06

**[Verified]** The proposal's adapter table uses headless CLI modes (`claude -p --output-format json`, `codex exec --json`, `copilot -p --autopilot --share`). `coord-runner.py` refuses any transport other than ACP for those harnesses. The two paths expose different telemetry: the `--output-format json` cost summary is a headless-mode feature. Pick one launch path for every cell, or comparisons mix transports. Run the Spike Protocol per harness over ACP first.

**[Verified]** Copilot workers need one pinned non-`auto` model and a committed `.github/allowed_models.txt` in the invoking checkout. The `pack=off` strip list removes `.github/`. Whether that matters depends on F1.

## F4. Scripted user delivery — S-04

**[Inferred]** The proposal offers "a local MCP server or a stdin responder". Under ACP with prompts limited to compiled audit ids, a stdin responder is not available. An MCP tool the agent calls (`ask_user`) keeps the answer inside one turn and logs every question. Confirm each harness can load a per-worktree MCP server over ACP (spike).

## F5. Task count: 22 or 24 — S-03

**[Verified]** The BOM v0 section lists 22 tasks and computes 528 runs; `tests/test_plan.py` confirms 22 × 4 × 2 × 3 = 528. The mockup header says 24 tasks and 576 runs, the mockup summary mentions F1–F3, and the phased plan's phase 6 says "24 tasks × 8 cells". This repo uses the BOM table (22). Confirm, or add the two missing tasks.

## F6. Mockup content predates BOM v0 — S-10

**[Verified]** The mockup's drill-down shows "D2 · TheTerrace booking module" and "F1 · CFD-Bench mesh ingest". BOM v0 defers TheTerrace, D2 is an ai-de extraction rule, and F1 is the wing spine. The mockup header shows one "third-party, pinned" judge; the proposal specifies two vendor judges with both scores shown. Update the mockup when the report is specified. Synthetic numbers are labelled as such and are fine.

## F7. Gaps with no owner in the proposal

- **[Verified]** Area 6 (autonomy and process) metrics have no module in the proposal's `grade/` layout. The scaffold adds `grade/process.py`.
- **[Verified]** E1–E5 budgets are "per task" (upstream). `bench/bom.yaml` uses 60 as a marked assumption until the upstream instances are picked.
- **[Verified]** `bench/prices.yaml` is empty. Prices must be read from provider price pages with a date; the proposal's NA rule applies until then.
- **[Inferred]** Phase 2's exit ("reproduce fixture scores byte-for-byte") needs frozen fixture runs before any real run exists. The recorded cfd-bench run and existing Claude Code / Copilot session stores can serve as telemetry-reader fixtures; a synthetic run directory can serve the graders.

## F8. YAML 1.1 booleans — fixed in the scaffold

**[Verified]** Bare `on` / `off` in YAML parse as `true` / `false`. The first `bench validate` run caught this in `matrix.example.yaml`. The validator now names the cause, a test covers it, and `/start-benchmark` tells the compiler to quote pack values.
