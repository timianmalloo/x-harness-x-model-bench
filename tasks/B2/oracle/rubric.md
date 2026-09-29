# B2 spec rubric (judge)

Score the cell's `docs/specs/freshness-prober.md`. This is the /specify definition of done for the ai-de Freshness Prober primer: core scenario, non-goals, Gherkin acceptance criteria, the ISO 25010 checklist, and three layers. Do not score harness identity or cost.

The reference spec under `oracle/reference/` shows one spec that meets these items. Another wording that meets an item scores the same.

Each item is 0, 1, or 2. 0 = missing or contradicted. 1 = named, with a gap or a claim a test could not check. 2 = stated so a test could be written from it.

1. **Core scenario.** Names the one path: for each scope, compare the repository-observed revision to the indexed revision; on disagreement, record one drift and raise one incident for that scope.
2. **Non-goals.** States explicit non-goals that include repairing/re-extracting the drift itself, deciding the probe's run cadence, and displaying or acknowledging incidents. Says the probe detects and reports only.
3. **Gherkin acceptance criteria.** User stories use Given / When / Then, cover a happy path (revisions agree, nothing raised) and an error path (revisions disagree, one incident raised), and state observable outcomes.
4. **ISO 25010.** Walks performance efficiency, reliability, security, usability, compatibility, maintainability and portability. Each attribute is a measurable requirement or an explicit N/A.
5. **Three layers.** Part A (functional), Part B (UX) and Part C (UI) are each present. A layer this capability does not have is marked N/A with a reason. Part C is not a visual design sitting on an absent Part B.
6. **Domain model.** Names the bounded context (workspace freshness), the scope/observed-revision/indexed-revision vocabulary, and the freshness-drift fact with the invariant it protects: a drift fact exists only when the two revisions disagree.
7. **Independent comparison source.** States that the comparison reads the repository directly, in explicit contrast to the daemon's own last-known/last-event state — the reason an independent prober exists at all, per the primer.
8. **Detection, not repair.** States that the prober itself never repairs, fixes or re-extracts to close the drift, and that exactly one incident is raised (deduplicated) per divergent scope rather than one per occurrence.

The judge returns the sum (0–16) and one line per item. A heading with an empty body scores 0 on the items that heading was supposed to carry.
