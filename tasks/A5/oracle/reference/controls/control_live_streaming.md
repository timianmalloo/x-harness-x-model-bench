# Spec: What Changed View

- **Status:** Draft
- **Tier (cost-of-error):** T1
- **Related:** ai-de AiDe.Core agent-lane worktrees (`AgentPlane/WorktreeProvisioner.cs`, `Workbench/AgentWorktree.cs`).

## Part A — Functional specification

This specification defines a changed-files view so an operator can see what one agent's own lane has
touched, without opening a shell and running git themselves.

### Problem

`WorktreeProvisioner.Inspect()` already asks git about a lane's own worktree, but today it reduces
the answer to two booleans — `HasUncommittedChanges` and `HasUnpushedWork` — used only to decide
whether the tree is safe to remove at lane close. Neither tells an operator *which* files the agent
touched while the lane was open. An operator watching a running lane, or reviewing one that just
closed, has no way to see what changed short of opening a shell in that lane's own worktree and
running git commands by hand.

### Conceptual domain model

Bounded context: Lane Change Visibility, alongside the AgentPlane worktree lifecycle.

Ubiquitous language:

- **Changed File** — one path in a lane's own worktree that differs from where that lane's branch
  started, together with its change kind.
- **Change Kind** — one of `added`, `modified`, `deleted`.
- **Changed-Files View** — the file-level list an operator watches for one lane.

Domain invariants:
1. The list is scoped to exactly one lane's own worktree; it never merges in another lane's changes
   or the wider repository.
2. Every entry names a path and a change kind; no entry carries the full text of the change.
3. The list is computed from git, never reconstructed from the tool-call or audit log.
4. The list stays open on the lane and updates itself as the agent works, for as long as the view
   is displayed.

### Core scenario

An operator watching a running agent lane opens the changed-files view for that lane and leaves it
open. The view is computed from git, in the lane's own worktree only — the same directory
`WorktreeProvisioner` provisioned for that agent — comparing the working tree against where that
lane's branch started. The view lists every changed file path, each labelled added, modified, or
deleted; it does not show the full line-by-line diff content of any file. While the view stays open,
it refreshes itself in the background as the agent keeps working, so the operator always sees the
latest state without asking again.

### In scope / Out of scope (explicit non-goals)

- **In scope:**
  - Listing the changed files for the current agent's own lane/worktree, computed from git.
  - Labelling each changed file added, modified, or deleted.
  - Continuously refreshing the list in the background while the view stays open, so it reflects
    the agent's latest edits without the operator asking again.
- **Out of scope (explicit non-goals):**
  - Changes from any other agent's lane, or from the wider repository; the view never covers all
    lanes or every agent at once — each lane's view is scoped to that lane's own worktree.
  - The full line-by-line diff content of a changed file; only the file-level list and its change
    kind are shown, never a unified diff or patch content.
  - Reconstructing the list from the tool-call or audit log: the audit log records what the agent
    attempted, not what the filesystem holds, so it is never the source of the list.
  - Push notifications or alerts when a file changes; the view updates its own display, but does
    not interrupt the operator elsewhere.

### User stories & acceptance criteria (testable)

**US-1 — See the current lane's own changes**
- **Given** an agent lane whose own worktree has two modified files and one new file,
- **When** the operator opens the changed-files view for that lane,
- **Then** the view lists exactly those three files, each labelled with its change kind (modified,
  modified, added).

**US-2 — No changes yet**
- **Given** a lane whose worktree matches the point its branch started from,
- **When** the operator opens the changed-files view,
- **Then** the view reports no changed files.

**US-3 — One lane's changes do not leak into another's**
- **Given** two agent lanes, each with different changes in their own worktrees,
- **When** the operator opens the changed-files view for one lane,
- **Then** only that lane's own changes are listed; the other lane's changes do not appear.

**US-4 — Updates while open**
- **Given** an open changed-files view for a lane,
- **When** the agent changes another file in that lane while the view stays open,
- **Then** the view shows the new file without the operator opening or reloading it again.

### Non-functional requirements (ISO/IEC 25010 checklist)

| Characteristic | Requirement |
|---|---|
| **Performance Efficiency** | Background refresh polls the lane's worktree at a bounded interval, within the same order of magnitude as `WorktreeProvisioner.Inspect()`'s own `git status --porcelain` call. |
| **Reliability** | When git cannot answer for that worktree, the view reports that it could not compute the changes rather than showing an empty or stale list. |
| **Security** | The view only ever reads the requesting operator's own lane worktree; it has no access to another lane's directory or the primary checkout. |
| **Usability** | Each entry is legible without decoding a diff: a path and one of `added` / `modified` / `deleted`. |
| **Compatibility** | Reads the same `git status --porcelain`-class output `WorktreeProvisioner` already parses, on Windows and macOS alike. |
| **Maintainability** | The list-building logic sits beside `WorktreeProvisioner.Inspect()` in `AgentPlane`, sharing its `IProcessRunner` seam rather than inventing a second way to run git. |
| **Portability** | No shell wrapper; paths are compared and reported with forward slashes, matching `WorktreeState`'s own host-neutral shape. |

## Part B — UX specification

The operator opens the changed-files view from the lane's own row in the workbench (the same row
that already shows `HasUncommittedChanges` today). While the view stays open, it keeps itself
current in the background, so the operator never has to ask again to see the latest state.

## Part C — UI specification

A panel listing one row per changed file: the path, and a small label reading `added`, `modified`,
or `deleted`, refreshing itself while the panel is open. A small indicator shows the view is live.
An empty state reads "No changes in this lane yet." No line-by-line diff content is rendered
anywhere in this panel.
