# Spec: What Changed View

- **Status:** Draft
- **Tier (cost-of-error):** T1
- **Related:** ai-de AiDe.Core agent-lane worktrees (`AgentPlane/WorktreeProvisioner.cs`, `Workbench/AgentWorktree.cs`).

## Part A — Functional specification

This specification defines a changed-files view so an operator can see what work is happening
across the fleet of agent lanes, without opening a shell and running git themselves.

### Problem

`WorktreeProvisioner.Inspect()` already asks git about a lane's worktree, but today it reduces the
answer to two booleans — `HasUncommittedChanges` and `HasUnpushedWork` — used only to decide
whether the tree is safe to remove at lane close. Neither tells an operator *which* files any agent
touched while its lane was open. An operator watching the fleet, or reviewing a batch of lanes that
just closed, has no way to see what changed short of opening a shell in every worktree and running
git commands by hand.

### Conceptual domain model

Bounded context: Fleet Change Visibility, alongside the AgentPlane worktree lifecycle.

Ubiquitous language:

- **Changed File** — one path in any agent lane's worktree that differs from where that lane's
  branch started, together with its change kind.
- **Change Kind** — one of `added`, `modified`, `deleted`.
- **Changed-Files View** — the file-level list an operator requests across the fleet.

Domain invariants:
1. The list spans every agent lane in the repository at once, so an operator sees the whole
   picture in one place.
2. Every entry names a path and a change kind; no entry carries the full text of the change.
3. The list is computed from git, never reconstructed from the tool-call or audit log.
4. The list reflects a single point in time — the moment it was requested — and is not a live feed.

### Core scenario

An operator watching the fleet opens the changed-files view. The view is computed from git, across
every agent lane in the repository — comparing each lane's working tree against where that lane's
branch started. The view lists every changed file path in any lane, each labelled added, modified,
or deleted; it does not show the full line-by-line diff content of any file. The operator requests
the view when they want it; it is a snapshot at that moment, not a stream that keeps updating while
they are not looking.

### In scope / Out of scope (explicit non-goals)

- **In scope:**
  - Listing the changed files across every agent's lane in the repository, computed from git.
  - Labelling each changed file added, modified, or deleted.
  - Computing the list on demand, when the operator asks for it.
- **Out of scope (explicit non-goals):**
  - A cross-lane comparison view; comparing two lanes' changes against each other rather than
    listing each lane's own.
  - The full line-by-line diff content of a changed file; only the file-level list and its change
    kind are shown, never a unified diff or patch content.
  - Reconstructing the list from the tool-call or audit log: the audit log records what the agent
    attempted, not what the filesystem holds, so it is never the source of the list.
  - A live-updating or continuously streaming view; the list is computed once per request, not
    refreshed in the background while the operator is not looking.

### User stories & acceptance criteria (testable)

**US-1 — See changes across the fleet**
- **Given** three agent lanes, each with different changed files in their own worktrees,
- **When** the operator requests the changed-files view,
- **Then** the view lists every changed file from all three lanes, each labelled with its change
  kind and which lane it belongs to.

**US-2 — No changes yet**
- **Given** every lane's worktree matching the point its branch started from,
- **When** the operator requests the changed-files view,
- **Then** the view reports no changed files.

**US-3 — A snapshot, not a stream**
- **Given** an open changed-files view,
- **When** an agent in any lane changes another file after the view was requested,
- **Then** the already-open view does not show the new file until the operator requests the view
  again.

### Non-functional requirements (ISO/IEC 25010 checklist)

| Characteristic | Requirement |
|---|---|
| **Performance Efficiency** | Computing the list across every lane completes within a bounded time proportional to the number of open lanes. |
| **Reliability** | When git cannot answer for a worktree, that lane's entry reports it could not compute the changes rather than showing an empty or stale list. |
| **Security** | The view only ever reads worktrees the operator is already permitted to see. |
| **Usability** | Each entry is legible without decoding a diff: a lane, a path, and one of `added` / `modified` / `deleted`. |
| **Compatibility** | Reads the same `git status --porcelain`-class output `WorktreeProvisioner` already parses, on Windows and macOS alike. |
| **Maintainability** | The list-building logic sits beside `WorktreeProvisioner.Inspect()` in `AgentPlane`, sharing its `IProcessRunner` seam rather than inventing a second way to run git. |
| **Portability** | No shell wrapper; paths are compared and reported with forward slashes, matching `WorktreeState`'s own host-neutral shape. |

## Part B — UX specification

The operator opens the changed-files view from a fleet-wide panel. Selecting it issues one on-demand
request and renders the returned list of lanes, paths and change kinds. There is no auto-refresh; a
visible "Refresh" action re-issues the same on-demand request.

## Part C — UI specification

A panel listing one row per changed file across every lane: the lane, the path, and a small label
reading `added`, `modified`, or `deleted`. An empty state reads "No changes across any lane yet." A
"Refresh" button re-requests the list; there is no live-updating indicator, because the view never
updates itself. No line-by-line diff content is rendered anywhere in this panel.
