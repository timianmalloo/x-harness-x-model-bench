# Workspace

`task.yaml` sets `source.workspace_from: source`, so the engine's own `workspace.task_source()`
builds the run workspace as `source.repo` at `source.commit` — a full, unmodified tree of the
pylint repository (GPL-2.0-or-later) at `1e55ae64624d28c5fe8b63ad7979880ee2e6ef3f` — with this
folder (`tasks/E5/workspace/`) overlaid on top (empty for E5: nothing here adds to or replaces the
upstream tree). `task_source()` fetches `source.repo` once into a cached, verified clone under the
tools directory, `git archive`s its tree at `source.commit`, overlays this folder, and commits the
result as the one base commit — the cell sees a tree at that commit, never the upstream's history
(tasks/README.md; R-83).

This is the whole given codebase (`pylint/`, `tests/`, `doc/`, `setup.cfg`, ...) as SWE-bench
Verified gives it: the entire pinned repository, not an excerpt (the same "no vendoring, no excerpt"
shape E4's workspace uses). Nothing here overlays the clone: nothing in this task needs a stub, a
public test or a doc beyond what the repository itself already contains at that commit.

Nothing under `tasks/E5/tests/` or `tasks/E5/oracle/` is reachable from this clone or its history.
