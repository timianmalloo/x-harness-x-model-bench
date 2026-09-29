# A5 — Users want to see what changed

Write the product specification to `docs/specs/what-changed-view.md`.

The AiDe.Core agent-lane worktree spine is provided under `src/AiDe.Core/`:

- `AgentPlane/WorktreeProvisioner.cs` — provisions one agent's own git worktree (a sibling of the
  primary checkout) and, today, `Inspect()` reports only two booleans about it: whether it has
  uncommitted changes and whether it has unpushed work. Neither says *which* files changed.
- `Workbench/AgentWorktree.cs` — plans that worktree's branch name and directory, from the
  repository root, the harness and the session id.

License: `LICENSE` (MIT, Copyright (c) 2026 timianmalloo).
