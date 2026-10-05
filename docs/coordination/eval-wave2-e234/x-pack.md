---
id: brief-eval-x-pack
title: "Brief X-PACK: Lane F - the ai-forward upstream of nine pack fixes, then /updatepack here (Claude Code Opus)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-e2e4, rel: implements }
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: defect-classes, rel: depends-on }
review-by: "2026-10-19"
summary: "X-PACK (Lane F) upstreams nine coordination and verify-gate fixes into ai-forward's pack sources, red first in ai-forward's own tests and proven by tools/verify-bundle.ps1, in its own worktree of C:\\Projects\\ai-forward (phase 1); after the Leader pushes ai-forward, it runs /updatepack in this repo in a second worktree and retires the Grok transport deviation (phase 2, joins P5). Claude Code Opus, session lanef-e1e4 (Coordinator #30)."
---

# X-PACK: Lane F, the ai-forward upstream

Written by Coordinator #30 on `coord/eval-c30-t0` at `37ec0585` (`integrate/e2e4-18`), from the plan's *Lane F* section and its X-PACK track rows (`docs/coordination/coordination-e2e4.md`). Where this brief differs from `docs/coordination/eval-wave2-e1/README.md` sections 1-4, this brief wins.

## Seat
- **Claude Code Agent tool, `model: opus`**, served `claude-opus-5-5` expected. The served id is the first line of each report. Why Opus: these fixes edit the coordination engine (merge driver, runner, transport) that every consuming repository inherits, and REG-C showed a defect there commits conflict markers silently (plan, Track assignment detail).
- **Session** `lanef-e1e4` for both phases. **Leader** `leader-e1e4`, epoch 18. **Owner** `owner-fable`. `AGENT_SESSION=lanef-e1e4` inline on every commit and coord call, in both repositories.
- **Budget:** 250 calls · 350k context · 1 session over two trees · 4 h (plan, Inferred). At 85 %: commit, stop, report what remains by item. **Fallback:** a fresh Sonnet session (`model: sonnet`, served `claude-sonnet-5-5`) from this brief.

## Phase 1: ai-forward (tree `C:\Projects\ai-forward-fix-xh-e2e4-upstream`, branch `fix/xh-e2e4-upstream`)
- **Tree.** From `C:\Projects\ai-forward`: `python docs/ai-forward-pack/scripts/coord-core.py worktree new --branch fix/xh-e2e4-upstream --session lanef-e1e4 --base main` (`origin/main` = `4a22f12`, read by Coordinator #29 and again by #30). *assume:* the ai-forward copy of `coord-core.py` supports `worktree new` as this repo's does. **Confirm:** its output prints the tree path. **If false:** `git -C C:\Projects\ai-forward worktree add ..\ai-forward-fix-xh-e2e4-upstream -b fix/xh-e2e4-upstream origin/main`. Record the base SHA.
- **The clone's primary is not yours.** `C:\Projects\ai-forward` carries other sessions' untracked and modified paths and five other worktrees. Nothing is edited, staged or checked out there; work only in your tree by absolute path. Never `EnterWorktree`.
- **Method.** `/extendaibundle` for each item (its consistency steps; sources under `pack/**`). Each item lands **red first** in ai-forward's own tests, failing on an assertion, then green. A test that already passes is recorded "green on arrival".
- **Owned paths:** the ai-forward `pack/**` sources and the ai-forward tests for the nine items below, plus the bundle files `/extendaibundle`'s consistency steps regenerate. Any other ai-forward path is a finding for the report, not an edit.

### The nine items (the plan's Lane F list; each traced to its class in this repo's `docs/lessons/defect-classes.md`)
1. **XPORT-A:** the Grok `session/new` race fix in `coord_transport.py` (this repo's deviation: `docs/notes/deviation-coord-transport-grok-session-new.md`).
2. **HYG-VERIFY:** the verify-gate findings: a file-level exemption for byte-exact captured records; the relative-glob false positive in `verify-no-machine-paths`; the fix text that names `python3` on Windows (`docs/coordination/eval-wave2-e1/hyg-verify.md`).
3. **BASE-A (the pack half):** runner support for a dispatch base other than the invoking checkout.
4. **MUT-A:** the session-start `--check-clean` control, as a generic hook that runs a repo-declared check command.
5. **The gate-stamp rule, where it generalises:** a renewal computes its digest under the suite lock (MUT-A's stamp shape). If it does not generalise beyond this repo's `tools/gate_stamp.py`, report it "not upstreamed" with the reason.
6. **REG-C:** `coord doctor` refuses a `register` entry on a non-`.jsonl` path, and `merge-register` exits non-zero instead of writing a marker file.
7. **ATTR-A:** `coord install` reconciles `.gitattributes` (removes merge attributes the registry no longer declares).
8. **PRIM-A, where it generalises:** an edit guard that refuses writes under the primary checkout's path from non-Leader sessions (KILL-GUARD's shape). If it does not generalise, report it "not upstreamed" with the reason.
9. **The staged-markers control (a GATE-B instance):** a pre-commit and pre-merge-commit scan that refuses staged conflict markers.

### Phase 1 gate (each command on its own line, exit status read, never behind a pipe)
- each item's red test observed failing by assertion, then green, in ai-forward's test runner;
- `/extendaibundle`'s consistency steps for each item;
- `pwsh -File tools/verify-bundle.ps1` exits 0 on the final commit.

**Phase 1 ends at a report and a stop.** The Leader pushes `fix/xh-e2e4-upstream` from your tree once `verify-bundle.ps1` is green (never from `C:\Projects\ai-forward`'s primary). You do not push.

## Phase 2: `/updatepack` here (tree `C:\Projects\x-harness-x-model-bench-coord-pack-update-e2e4`, branch `coord/pack-update-e2e4`)
Starts when the Leader gives you the pushed ai-forward revision: a continuation of this session, or a fresh Opus session from this section.
- **Tree.** From `C:\Projects\x-harness-x-model-bench`: `python docs/ai-forward-pack/scripts/coord-core.py worktree new --branch coord/pack-update-e2e4 --session lanef-e1e4 --base <integration head>`. Record the base SHA. Never `coord install` in a worktree; never checkout or switch in the primary.
- **Method.** `/updatepack` from the pushed ai-forward revision: `pack-apply.py`'s action table, the managed-block re-paste and three-way merges over repo-local deviations. Mark `docs/notes/deviation-coord-transport-grok-session-new.md` retired (its fix is now upstream). Edit generated skill copies only through their source and `tools/sync-skills.py`.
- **Owned paths:** this repo's pack-managed paths that `pack-apply.py`'s action table names, and the deviation note. Any other path is a seam request to `coord-opus-e1e4`.
- **Gate (each on its own line, exit status read):** `pack-apply.py`'s action table in the report; `python docs/ai-forward-pack/scripts/coord-core.py doctor` reads back; `uv run pytest -q tests/test_architecture.py tests/test_identity.py tests/test_atomic_sites.py tests/test_arms_guard.py tests/test_discriminate.py tests/test_mutate_check.py tests/test_skills_in_sync.py tests/test_timing_hygiene.py` (the guard list, on your first and final commits); the transport tests green; `uv run ruff check src tests tools`; `python docs/ai-forward-pack/scripts/docs-graph.py validate`.
- **Join:** the Leader merges this branch in batch P5, when no external dispatch is live (serial spine 9). You do not merge.

## Rules (both phases)
- Commit named paths only (never `-A`, `.` or `-a`). Never kill a process by name or pattern, only PIDs you started. A multi-line program is a file, then a run (no heredoc into Python). Conflict resolution only by Read then Edit, with a marker scan before any add.
- Findings in ai-forward go in ai-forward's own register; defect-class text for this repo goes in your report (the Coordinator owns `docs/lessons/defect-classes.md`).
- No campaign ledger (`bench/campaigns/**`) on your branch.

## Not in scope
Pushing either repository; merging; editing `C:\Projects\ai-forward`'s primary; any `src/`, `tests/` (other than through `pack-apply.py`'s action table) or `tasks/` path of this repo; Lane F items beyond the nine.

## Report (per phase, at most 12 lines)
Served model id first · tree, branch, base SHA and tip · per item: red SHA, test node, failing assertion, green SHA, or "not upstreamed" with the reason · each gate command's exit status · `pack-apply.py`'s action counts (phase 2) · defect-class text · every `assume:` and whether it held · budget used.
