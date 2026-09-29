# A5 Spec Rubric (Judge)

Score the cell's `docs/specs/what-changed-view.md`. This evaluates the specification against the 4
key clarification dimensions and the /specify definition of done: scope (own lane vs every lane),
granularity (file list vs full diff), source of truth (git vs audit log), refresh (on demand vs
live), plus core scenario, non-goals, Gherkin acceptance criteria, ISO 25010 NFRs, and three-layer
structure.

The reference spec under `oracle/reference/` demonstrates a complete specification meeting all
items. `oracle/reference/controls/` holds four negative controls, each meeting every item except
one.

Each item is scored 0, 1, or 2:
- 0 = Missing, contradictory, or incorrect.
- 1 = Mentioned or partially addressed, but with ambiguity or missing testable criteria.
- 2 = Fully articulated, unambiguous, and directly testable.

### Items

1. **Scope (Clarification 1):** Confines the changed-files view to the current agent lane's own
   worktree; explicitly excludes other lanes and the wider repository.
2. **Granularity (Clarification 2):** Defines a file-level list, each entry labelled added,
   modified, or deleted; explicitly excludes full line-by-line diff content.
3. **Source of Truth (Clarification 3):** Computes the list from git, comparing the lane's worktree
   against where its branch started; explicitly excludes the tool-call/audit log as the source.
4. **Refresh (Clarification 4):** Computes the list on demand, as a snapshot at request time;
   explicitly excludes a live-updating or continuously streaming view.
5. **Core Scenario:** Describes the end-to-end workflow: an operator opens the view for one lane,
   it queries git in that lane's worktree, and returns a labelled file list.
6. **Non-Goals:** Enumerates explicit non-goals matching items 1–4 (other lanes, full diff, audit
   log, live streaming).
7. **Gherkin Acceptance Criteria:** User stories specify testable Given / When / Then criteria
   covering the happy path, the no-changes case, and cross-lane isolation.
8. **ISO/IEC 25010 Checklist:** Addresses performance, reliability (a failed git query never shows
   a stale or empty list silently), security (no cross-lane read), and maintainability (reuses
   `WorktreeProvisioner`'s `IProcessRunner` seam rather than inventing a second git runner).
9. **Three-Layer Structure:** Contains Part A (Functional), Part B (UX), and Part C (UI), each
   describing the on-demand, file-level, single-lane view.

Total score is the sum across items (0–18).
