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
  real coord-runner.py: a worker-isolation seam between "fresh clone per run" and coord-runner's
  worktrees, runner limits the design must fit, gaps with no owner, and the evidence behind the
  formal-methods revision (scenario 7, oracle ladder, protocol conformance).
---

# Proposal grounding findings (scaffold pass)

Date: 2026-09-23. Pack: ai-forward revision 92, installed from a local ai-forward clone (that clone was 2 commits ahead and 2 behind `origin/main` at install time).

Each finding carries a confidence label and the spec that must resolve it (`docs/specs/README.md`).

## F1. Worker isolation: fresh clone vs coord-runner worktrees — S-02 (blocking)

**[Verified]** The proposal says each run gets "one fresh clone per run: `git worktree`-free, cloned from the task's base commit". It also says every cell is a worker launched by `coord-runner.py`. These do not fit together. `coord-runner.py prepare` makes each worker's worktree from the **invoking checkout** on a new branch (`validate()` checks the branch in `self.cwd`; `prepare()` calls `core.cmd_worktree(..., "new", self.cwd, ...)`). If the coordinator invokes it from this repo, workers start in a worktree of the **bench repo**, not of the task's source repo.

**[Inferred]** Running coord-runner from inside each task clone instead would write coordination state (`.agents/`, logs, bindings) into the clone. For `pack=off` that puts pack artifacts into the control workspace.

Options for the ADR: (a) extend coord-runner with a per-worker external workspace; (b) run coord-runner from inside each task clone and strip coordination state before grading; (c) make each task's workspace a subtree of the bench repo's worker worktree. Decide before building the runner.

**Spike 2026-09-23** (`spike-runner-path.md`): (b) works with no runner change when the bench generates the cell repo; worker trees stayed clean. (c) would expose the hidden tests. New blocker found: the runner's prompt delivery is a pack treatment in `pack=off` (spike §2.4).

## F2. coord-run/1 limits the design must fit — S-05

**[Verified]** from `coord-runner.py` `validate()`:

| Limit | Value | Consequence |
| --- | --- | --- |
| Workers per contract | 1–8 | Full grid of 576 cells needs 72 contracts; smoke needs 18 (`bench plan` prints this) |
| Parallelism | 1–4 | At most 4 cells run at once per contract |
| `deadline_seconds` | ≤ 3600 | No task budget may exceed 60 minutes. F1/F2 budget is exactly 60, leaving no headroom |
| `runtime.max_turns` | 1–8 | These are prompts sent over ACP, not agent tool turns. The proposal's per-scenario "turn cap" needs a different enforcement point |
| `prompts` | 1–8 compiled `/compile` audit ids | Scripted-user answers (A-tasks) cannot be pre-compiled prompts; see F4 |
| Transport | ACP for claude, codex, grok, copilot | See F3 |

`bench validate` already refuses any BOM budget over 60 minutes.

## F3. Headless CLI flags vs ACP transport — S-06

**[Verified]** The proposal's adapter table uses headless CLI modes (`claude -p --output-format json`, `codex exec --json`, `copilot -p --autopilot --share`). `coord-runner.py` refuses any transport other than ACP for those harnesses. The two paths expose different telemetry: the `--output-format json` cost summary is a headless-mode feature. Pick one launch path for every cell, or comparisons mix transports. Run the Spike Protocol per harness over ACP first.

**[Verified]** Copilot workers need one pinned non-`auto` model and a committed `.github/allowed_models.txt` in the invoking checkout. The `pack=off` strip list removes `.github/`. Whether that matters depends on F1.

**Spike 2026-09-23** (`spike-runner-path.md`): ACP launch works for all three. Usage comes only from each harness's native store; Copilot's includes a native AI-unit cost basis. Model pinning is enforced for Copilot only, adapters run their own bundled CLI builds, and user-level configuration reaches every cell (spike §1.2–1.5).

## F4. Scripted user delivery — S-04

**[Inferred]** The proposal offers "a local MCP server or a stdin responder". Under ACP with prompts limited to compiled audit ids, a stdin responder is not available. An MCP tool the agent calls (`ask_user`) keeps the answer inside one turn and logs every question. Confirm each harness can load a per-worktree MCP server over ACP (spike).

## F5. Task count: 22 or 24 — resolved (24)

**[Verified]** The BOM v0 section listed 22 tasks (528 runs) while the mockup header and phase 6 said 24. The formal-methods revision added G1 and G2 (scenario 7), so BOM v0 is now 24 tasks and 576 runs; `tests/test_plan.py` checks 24 × 4 × 2 × 3 = 576. The match with the mockup's 24 is a coincidence, not a reconciliation of the original gap.

## F6. Mockup content predated BOM v0 — fixed in the seed, layout still S-10

**[Verified]** The mockup's drill-down showed "D2 · TheTerrace booking module" and "F1 · CFD-Bench mesh ingest", a single "third-party, pinned" judge, six scenarios and F1–F3. The seed mockup now matches BOM v0.2: ai-de D2, the wing-spine F1, two blind vendor judges, seven scenarios (heatmap column for scenario 7, a G1 drill-down with the four formal scores). The layout itself is still owned by S-10. Numbers remain synthetic and labelled. **[Verified]** At 390 px the page scrolls horizontally, in the original mockup as well as the updated one (headless render); fix it in S-10.

## F7. Gaps with no owner in the proposal

- **[Verified]** Area 6 (autonomy and process) metrics have no module in the proposal's `grade/` layout. The scaffold adds `grade/process.py`.
- **[Verified]** E1–E5 budgets are "per task" (upstream). `bench/bom.yaml` uses 60 as a marked assumption until the upstream instances are picked.
- **[Verified]** `bench/prices.yaml` is empty. Prices must be read from provider price pages with a date; the proposal's NA rule applies until then.
- **[Inferred]** Phase 2's exit ("reproduce fixture scores byte-for-byte") needs frozen fixture runs before any real run exists. The recorded cfd-bench run and existing Claude Code / Copilot session stores can serve as telemetry-reader fixtures; a synthetic run directory can serve the graders.

## F8. YAML 1.1 booleans — fixed in the scaffold

**[Verified]** Bare `on` / `off` in YAML parse as `true` / `false`. The first `bench validate` run caught this in `matrix.example.yaml`. The validator now names the cause, a test covers it, and `/start-benchmark` tells the compiler to quote pack values.

## F9. Formal methods: evidence quality and what it changed — S-12, S-13, S-14, S-08g

**[Verified]** Boris Cherny's Sep 23, 2026 post (primary) says Opus 5.5 plus "a couple short prompts" produced 16 PRs fixing bugs and race conditions in the Claude Agent SDK via Lean, with TLA+ sometimes combined. **[Reported, unverified]** The explainx.ai write-up adds 24 bugs (19 from proofs), 1,529 theorems across 6 Lean models, zero `sorry`, 5 PRs merged; it names no bug, model or PR, and has no links beyond the attribution. **[Reported by the papers; read from their abstracts and summaries, not re-derived]** Published measurements are far lower than the anecdote suggests: Verina 4.9% proof success (2025), SysMoBench about 46% conformance and 41% invariants for frontier models, NL→TLA+ 8.6% semantic correctness. That gap is a measurable per-harness, per-model question, so the proposal now has:

- scenario 7 (G1 TLA+, G2 Lean 4) on the pack's own lease fold in `coord-core.py`, which has a pure event→lease fold with idempotent replay and a retried-call guard (verified in the source);
- the oracle ladder (proof or model check → trace conformance → tests → judge);
- four separate formal scores (checks, statement integrity, fidelity, yield), because zero `sorry` does not show the model matches the code;
- `protocol_conformance`: coordination ledgers replayed against a TLA+ model of the pack's protocol;
- a TLA+ model of the run lifecycle, checked before the runner is built.

**[Flagged]** Toolchains are unproven on Windows inside coord-runner worker worktrees under each harness (spike S-12). The lease properties G1/G2 check must come from the pack's docs and tests, not our reading of the code.
