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
whether the tree is safe to remove at lane close. Neither tells an operator *what* the agent
actually changed while the lane was open. An operator watching a running lane, or reviewing one
that just closed, has no way to see what changed short of opening a shell in that lane's own
worktree and running git commands by hand.

### Conceptual domain model

Bounded context: Lane Change Visibility, alongside the AgentPlane worktree lifecycle.

Ubiquitous language:

- **Changed File** — one path in a lane's own worktree that differs from where that lane's branch
  started, together with its full diff content.
- **Diff Content** — the line-by-line unified diff text for one changed file.
- **Changed-Files View** — the diff an operator requests for one lane.

Domain invariants:
1. The list is scoped to exactly one lane's own worktree; it never merges in another lane's changes
   or the wider repository.
2. Every entry carries the full unified diff text for that file, not only its path.
3. The list is computed from git, never reconstructed from the tool-call or audit log.
4. The list reflects a single point in time — the moment it was requested — and is not a live feed.

### Core scenario

An operator watching a running agent lane opens the changed-files view for that lane. The view is
computed from git, in the lane's own worktree only — the same directory `WorktreeProvisioner`
provisioned for that agent — comparing the working tree against where that lane's branch started.
The view renders the full line-by-line diff content for every changed file, so the operator can read
exactly what the agent wrote. The operator requests the view when they want it; it is a snapshot at
that moment, not a stream that keeps updating while they are not looking.

### In scope / Out of scope (explicit non-goals)

- **In scope:**
  - Listing the changed files for the current agent's own lane/worktree, computed from git.
  - Showing the full line-by-line diff content for each changed file.
  - Computing the list on demand, when the operator asks for it.
- **Out of scope (explicit non-goals):**
  - Changes from any other agent's lane, or from the wider repository; the view never covers all
    lanes or every agent at once — each lane's view is scoped to that lane's own worktree.
  - A collapsed, file-level-only summary; the point of this view is to read the actual change, not
    a bare list of paths.
  - Reconstructing the list from the tool-call or audit log: the audit log records what the agent
    attempted, not what the filesystem holds, so it is never the source of the list.
  - A live-updating or continuously streaming view; the diff is computed once per request, not
    refreshed in the background while the operator is not looking.

### User stories & acceptance criteria (testable)

**US-1 — Read the current lane's own diff**
- **Given** an agent lane whose own worktree has two modified files and one new file,
- **When** the operator requests the changed-files view for that lane,
- **Then** the view shows the full diff content for all three files.

**US-2 — No changes yet**
- **Given** a lane whose worktree matches the point its branch started from,
- **When** the operator requests the changed-files view,
- **Then** the view reports no changed files.

**US-3 — One lane's changes do not leak into another's**
- **Given** two agent lanes, each with different changes in their own worktrees,
- **When** the operator requests the changed-files view for one lane,
- **Then** only that lane's own diff is shown; the other lane's changes do not appear.

**US-4 — A snapshot, not a stream**
- **Given** an open changed-files view for a lane,
- **When** the agent changes another file in that lane after the view was requested,
- **Then** the already-open view does not show the new diff until the operator requests the view
  again.

### Non-functional requirements (ISO/IEC 25010 checklist)

| Characteristic | Requirement |
|---|---|
| **Performance Efficiency** | Rendering the full diff for one lane's worktree completes within a bounded time proportional to the size of the change. |
| **Reliability** | When git cannot answer for that worktree, the view reports that it could not compute the diff rather than showing an empty or stale list. |
| **Security** | The view only ever reads the requesting operator's own lane worktree; it has no access to another lane's directory or the primary checkout. |
| **Usability** | The diff is rendered with syntax-aware highlighting so the operator can read it directly. |
| **Compatibility** | Reads the same `git`-tracked worktree `WorktreeProvisioner` already parses, on Windows and macOS alike. |
| **Maintainability** | The diff-rendering logic sits beside `WorktreeProvisioner.Inspect()` in `AgentPlane`, sharing its `IProcessRunner` seam rather than inventing a second way to run git. |
| **Portability** | No shell wrapper; paths are compared and reported with forward slashes, matching `WorktreeState`'s own host-neutral shape. |

## Part B — UX specification

The operator opens the changed-files view from the lane's own row in the workbench (the same row
that already shows `HasUncommittedChanges` today). Selecting it issues one on-demand request and
renders the returned diff for every changed file. There is no auto-refresh; a visible "Refresh"
action re-issues the same on-demand request.

## Part C — UI specification

A panel showing the full diff for each changed file in the lane, one file per collapsible section.
An empty state reads "No changes in this lane yet." A "Refresh" button re-requests the diff; there
is no live-updating indicator, because the view never updates itself.
