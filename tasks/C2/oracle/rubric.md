# C2 architecture rubric (judge)

This rubric borrows R2ABench's two-layer grading shape **by name only** (arXiv 2604.06683): an
**L1** structural/schema-conformance layer and an **L2** semantic/judge-scoring layer. No
R2ABench text, rubric criteria, seed data, or judge prompt is reproduced here — R2ABench itself is
not used as a source (R-82 DR-W5-2: no licence on its public repository, both share links to its
data return 403, and its L2 judge is keyed to a third-party relay). The hidden tests in
`tests/test_c2_hidden.py` are this task's own L1 (structure and the two decided-content facts);
this rubric is this task's own L2 (semantic quality of `docs/architecture.md`, judged against the
reference note under `oracle/reference/`).

Score the cell's `docs/architecture.md`. Do not score harness identity, cost, or process.

Each item is 0, 1, or 2. 0 = missing or contradicted by the design. 1 = named, with a gap or an
unsupported claim. 2 = stated and internally consistent with the rest of the note.

1. **Component boundaries.** Names the component that orchestrates a probe run, the boundary it
   reads the repository through, the boundary it reads the indexed revision through, and the
   boundary it writes an incident through, as four distinguishable responsibilities (not one
   component doing everything).
2. **Independent comparison source.** States that the observed-revision read is taken from the
   repository directly, in explicit contrast to the daemon's own last-known/cached state — the
   reason this capability exists at all, per the given spec.
3. **Detection, not repair.** States that the prober itself never repairs, fixes, or re-extracts
   to close a drift, and names which other component's job that is.
4. **Deduplication.** States that a divergence raises exactly one incident per `{class, scope}`,
   and that a repeat divergence on an already-open incident updates it rather than creating a
   second one.
5. **Exception safety.** States that a failed read for one scope does not abort the run for the
   remaining scopes and is never reported as fresh.
6. **Complexity.** Gives a cost for a probe run that is consistent with the design described (a
   single pass over the given scopes, not a cost that depends on unrelated scopes).
7. **Decision quality.** The `## Decision` section names a real decision this design makes and at
   least one alternative that was considered and rejected, with a stated reason — not a
   restatement of the decision as its own alternative.
8. **Boundaries respected.** The note does not specify a user interface, a run cadence, or an
   incident-display surface — the given spec's own non-goals for this capability.

The judge returns the sum (0–16) and one line per item. A heading with an empty body scores 0 on
the items that heading was supposed to carry.
