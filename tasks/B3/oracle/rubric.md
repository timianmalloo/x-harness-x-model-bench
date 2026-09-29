# B3 spec rubric (judge)

Score the cell's `docs/specs/p1-estimator-validated.md`. This is the /specify definition of done
for the cfd-bench P1 "Estimator, validated" primer: core scenario, non-goals, Gherkin acceptance
criteria, the ISO 25010 checklist, and three layers. Do not score harness identity or cost.

The reference spec under `oracle/reference/` shows one spec that meets these items. Another
wording that meets an item scores the same. `oracle/reference/controls/` holds two negative
controls, each meeting every item except one.

Each item is 0, 1, or 2. 0 = missing or contradicted. 1 = named, with a gap or a claim a test
could not check. 2 = stated so a test could be written from it.

1. **Core scenario.** Names the one path: a wing definition and an operating point go in; L/D,
   Cl/Cd, required angle of attack and cavitation margin come out, headless and scriptable.
2. **Non-goals.** States explicit non-goals that include any UI/dashboard/plot rendering the
   output, fabrication or export, and section catalog entries beyond the 11 already vendored.
3. **Gherkin acceptance criteria.** User stories use Given / When / Then, cover a happy path and
   an error path (an unrecognized section format), and state observable outcomes.
4. **ISO 25010.** Walks performance efficiency, reliability, security, usability, compatibility,
   maintainability and portability. Each attribute is a measurable requirement or an explicit N/A.
5. **Three layers.** Part A (functional), Part B (UX) and Part C (UI) are each present. A layer
   this phase does not have is marked N/A with a reason (headless on purpose). Part C is not a
   visual design sitting on an absent Part B.
6. **Domain model.** Names the section catalog as the aggregate root, its invariant (a usable
   entry carries a detected coordinate format and a measured-geometry hash), and the Estimate as
   a value object recomputed rather than stored, in domain terms.
7. **Validation source (decided fact 1).** States that the closed-form chain is validated against
   DTIC ADA032272's real towing-tank lift and drag data for the NACA 16-309 and 64A309 sections —
   not against a synthetic, CFD-computed, or self-consistency reference.
8. **Format support (decided fact 2).** States that the section catalog accepts both the Selig and
   the Lednicer aerofoil coordinate formats, with the format detected automatically — not
   restricted to one format or left for the caller to specify.

The judge returns the sum (0–16) and one line per item. A heading with an empty body scores 0 on
the items that heading was supposed to carry.
