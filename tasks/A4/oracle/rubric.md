# A4 Spec Rubric (Judge)

Score the cell's `docs/specs/reusable-wing-definition.md`. This evaluates the specification against the 5 key clarification dimensions and the /specify definition of done: local persistence vs sharing, format, schema versioning, fail-closed validation, and scope, plus core scenario, non-goals, Gherkin acceptance criteria, ISO 25010 NFRs, and three-layer structure.

The reference spec under `oracle/reference/` demonstrates a complete specification meeting all items.

Each item is scored 0, 1, or 2:
- 0 = Missing, contradictory, or incorrect.
- 1 = Mentioned or partially addressed, but with ambiguity or missing testable criteria.
- 2 = Fully articulated, unambiguous, and directly testable.

### Items

1. **Persistence vs Sharing (Clarification 1):** Specifies local file/project document persistence on disk across runs; explicitly excludes or rejects networked/cloud sharing.
2. **File Format (Clarification 2):** Defines a structured human-readable JSON format for persisting the wing definition and its stations.
3. **Schema Versioning (Clarification 3):** Mandates an explicit format version identifier (e.g. `cfd-wing/1`) with fail-closed rejection of unsupported versions.
4. **Validation and Invariants (Clarification 4):** Specifies fail-closed validation on load, enforcing wing aggregate invariants (station count, root at centreline, increasing span, positive chord) and rejecting corrupted files.
5. **Scope & Derived Omission (Clarification 5):** Confines persistence to the core geometric definition (stations); explicitly excludes derived quantities (span, area, aspect ratio, mean chord) and simulation meshes.
6. **Core Scenario:** Describes the end-to-end user workflow: define wing, save to file with version, reload in a subsequent run, verify invariant checks and derived equivalence.
7. **Non-Goals:** Enumerates explicit non-goals including cloud synchronization, GUI dialogs, and CAD/STEP export implementation.
8. **Gherkin Acceptance Criteria:** User stories specify testable Given / When / Then criteria covering both success (round-trip) and failure modes (version mismatch, corrupt JSON, invariant violation).
9. **ISO/IEC 25010 Checklist:** Addresses performance, reliability (fail-closed), security, compatibility, maintainability, and portability.
10. **Three-Layer Structure:** Contains Part A (Functional), Part B (UX), and Part C (UI). Parts B and C appropriately document headless/API nature or mark UI as N/A with rationale.

Total score is the sum across items (0–20).
