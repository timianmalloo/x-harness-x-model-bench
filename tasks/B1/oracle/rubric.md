# B1 spec rubric (judge)

Score the cell's `docs/specs/p0-conventions-and-spine.md`. This is the /specify definition of done for the P0 conventions and spine primer: core scenario, non-goals, Gherkin acceptance criteria, the ISO 25010 checklist, and three layers. Do not score harness identity or cost.

The reference spec under `oracle/reference/` shows one spec that meets these items. Another wording that meets an item scores the same.

Each item is 0, 1, or 2. 0 = missing or contradicted. 1 = named, with a gap or a claim a test could not check. 2 = stated so a test could be written from it.

1. **Core scenario.** Names the one path: define a wing and obtain span, planform area, aspect ratio and mean chord, with tests that show those four are right.
2. **Non-goals.** States explicit non-goals that include a fabrication implementation, a user-facing UI, and the later-phase estimator. Says export stays an interface so fabrication is not foreclosed.
3. **Gherkin acceptance criteria.** User stories use Given / When / Then, cover a happy path and an error path, and state observable outcomes.
4. **ISO 25010.** Walks performance efficiency, reliability, security, usability, compatibility, maintainability and portability. Each attribute is a measurable requirement or an explicit N/A.
5. **Three layers.** Part A (functional), Part B (UX) and Part C (UI) are each present. A layer this phase does not have is marked N/A with a reason. Part C is not a visual design sitting on an absent Part B.
6. **Domain model.** Names the wing aggregate, its root, and the invariant it protects, and the two layers (stations and loft), in domain terms.
7. **Conventions.** States a coordinate frame, the sign of anhedral and of twist, and that units live in the type system rather than in comments. A convention the primer left open is either decided or marked as an assumption.
8. **Import.** Says the wing document this product writes is the only import path, and that reconstructing stations from an arbitrary CAD body is out of scope.

The judge returns the sum (0–16) and one line per item. A heading with an empty body scores 0 on the items that heading was supposed to carry.
