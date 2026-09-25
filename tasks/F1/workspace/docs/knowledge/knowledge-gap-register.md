---
id: knowledge-gap-register
title: "Knowledge Gap Register — What the End-to-End Is Missing"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [gaps, review, end-to-end, validation, structures, unsteady, process]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
  - { to: kb-design-automation, rel: refines }
  - { to: kb-cad-ux-geometry, rel: refines }
  - { to: kb-flow-visualization, rel: refines }
  - { to: kb-fabrication-interop, rel: refines }
  - { to: kb-cfd-orchestration, rel: refines }
review-by: 2026-12-06
summary: >-
  A deliberate sweep of the whole design-to-fabrication chain for knowledge we have not gathered.
  Sixteen gaps ranked by whether they block, reshape, or merely inform — with the two that would
  most change the product named explicitly, and two process gaps in how this project has been run.
---

# Knowledge gap register

Compiled 2026-09-06 by walking the end-to-end chain — **state a goal → optimise → edit → analyse →
visualise → export → fabricate** — and asking at each step what we would need to know that we have
not yet gathered.

**Summary:** the chain is well covered on *hydrodynamics* and *software*, and thin-to-absent on
**structures, unsteady behaviour, the user, and how we prove any of it is right.**

---

## Tier 1 — these block or reshape the product

### GAP-01 · Validation data — we still have no case to check against

**Status:** *partially closed during this review.* The v1 base recorded "a solver with no validation
case is not a solver, it is a renderer" and then never went looking. It has now been looked for, and
**it exists**:

- **DTIC ADA032272 — "Lift and Drag Characteristics of NACA 16-309 and NACA 64A309 Hydrofoils"**
  (DTNSRDC). Lift and drag measured in the **High-Speed Tow Facility and Rotating Arm Facility**,
  flap angles to 17.5°, pitch to 12°, with **good agreement between the two facilities**. Publicly
  available via the Internet Archive. *(Verified)*
- Towing-tank data for a **T-foil** at the Australian Maritime College, used to derive viscous and
  free-surface adjustments. *(Verified)*

**And it independently corroborates a Phase 0 result.** The DTNSRDC report found that
**the 64A309 achieves a higher lift-to-drag ratio than the 16-309.** *(Verified)* That is now the
**third independent line** agreeing on 6-series over 16-series: the IHS practitioner recommendation
(prose), our NeuralFoil measurement (64A410 best L/D of the set), and now towing-tank experiment.
**Three methods, one answer** — this is the strongest single claim in the whole knowledge base.

**What remains:** the actual coefficient tables have not been extracted, and no validation case has
been *run*. **Do this before the CFD tier is trusted**, not after.

### GAP-02 · Structural analysis — the largest genuine hole

Phase 0 established that **thickness has no hydrodynamic optimum** and is therefore *set by
structure*. The tool consequently has a variable whose value is decided entirely by physics it does
not model. **A wing that is hydrodynamically optimal and snaps at 25 knots is worse than useless.**

What the literature offers, and it is directly usable at our fidelity tier:

- **Beam + lifting-line hydroelastic models** — there is published work on *static hydroelastic study
  of composite T-foils with beam and lifting line models*, which is exactly the low-order pairing
  this project already uses on the hydrodynamic side. *(Verified)*
- **Spars carry the bending loads**; composite hydrofoils are carbon/glass-epoxy, and *the primary
  difference is the orientation of structural carbon layers relative to the spanwise axis*.
  *(Verified)*
- **Bend–twist coupling** from layup anisotropy changes the steady hydroelastic response — a foil
  deflects *and twists* under load, which changes its angle of attack, which changes the load.
  *(Verified)*
- Predicted vs experimental bending stiffness agreed **within 20%**. *(Verified)*

**Why this reshapes the product rather than merely extending it:** with a beam model, thickness
stops being a user-set constraint with a displayed hydrodynamic cost and becomes a **solved
quantity** — "the thinnest section that survives your loads with your layup". That is a materially
better tool, and it closes the loop Phase 0 opened.

**Also unmodelled:** deflection changes the geometry the hydrodynamics sees. At high aspect ratio —
which is where this domain is heading — that coupling is not small.

### GAP-03 · Who the user is

**Three UX proposals have been written without any user research.** No personas, no
jobs-to-be-done, no interviews, no observation. The pack's UX Researcher/IA lens **holds the
UX-specification veto** and has never been convened.

The unanswered question is not cosmetic:

- **A rider** wants "will this be fast for me at my weight" and does not know what `Cp_min` is.
- **A shaper or small manufacturer** wants repeatability, a mold, and a file that machines.
- **An engineer or researcher** wants the polars, the assumptions, and the ability to disbelieve the
  tool.

These want **three different applications**. The proposals as written lean engineer — the
goal-driven screen exposes cavitation margin and validity envelopes — which may be exactly right,
but it is currently an assumption with no evidence behind it. **Everything downstream of a wrong
answer here is wasted.**

### GAP-04 · Units, coordinate systems and sign conventions

Flagged as a defect class in v1 (*"kinematic vs dynamic viscosity is a factor-of-1000 error
class"*), and **never actually settled**. There is still no written convention for:

- **The foil coordinate frame** — origin at leading edge or quarter chord; x aft or forward; z up or
  down. Marine and aero conventions differ, and both appear in our sources.
- **Sign of anhedral, twist and incidence.** Anhedral is tips-down here, but positive or negative?
- **Metric vs imperial.** The IHS source is in English units and apologises for it; foil products are
  sold in cm² and cm span; ITTC is SI.
- **Where units live** — the geometry knowledge base says "carry units in the type system, not in
  comments", which is a good instinct that has never been turned into a specification.

This is cheap to close and expensive to leave. **It should be written before the first line of
geometry code**, because retrofitting a convention is how sign errors become permanent.

---

## Tier 2 — architecturally significant

### GAP-05 · Unsteady behaviour and pumping

Every method in the stack is **steady**. Foiling is not — and for **downwind, pumping is the entire
sport**, not an edge case. The design practice base already records that high-aspect foils have
*"long, relaxed pump cycles"* as a primary selling point, and we have no way to evaluate that claim.

The literature is mature and quantitative:

- **Strouhal number governs it.** Peak propulsive efficiency clusters near **St ≈ 0.4** regardless of
  body geometry or speed. *(Verified)*
- **Heaving generates thrust through lift-based mechanisms; pitching through unsteady added-mass.**
  Combined motion exploits both, and reaches **up to 75% propulsive efficiency** at lower Strouhal
  numbers. *(Verified)*
- At **St ≈ 0.3** two-dimensional effects dominate the flow structure; 3D effects dominate above and
  below. *(Verified)*

**Consequence:** "pumpability" is a *computable* property, not a vibe — and it is one of the two or
three things riders actually choose a foil on. Currently the tool cannot say anything about it.

### GAP-06 · Multi-fidelity reconciliation

We committed to verification at a higher tier (COMMIT-01) and to *"disagreement between layers is a
finding"* — but **we have no method for what to do with a disagreement.** When the estimator says
L/D 19.8, the VLM says 17.2 and CFD says 15.9:

- Which number does the UI show?
- Is the difference model error, mesh error, or a genuine physical effect the cheap model omits?
- Can the discrepancy be *learned* — a correction factor from accumulated comparisons?

Multi-fidelity fusion and uncertainty quantification are established fields and we have gathered
nothing from them. **This is the gap most likely to make the tool feel untrustworthy in use**, since
users will see the numbers move and want to know why.

### GAP-07 · Manufacturing constraints feeding back into design

`kb-fabrication-interop` covers formats and CAM. It does not cover **what is actually
manufacturable**, and those constraints belong *in the design space*, not after it:

- **Minimum trailing-edge thickness.** You cannot mold or lay up a 0.2 mm trailing edge. Real foils
  have a finite TE, and our measured sections have TE gaps of 0.00–0.10% chord — which at an 80 mm
  chord is *0 to 0.08 mm*. **Physically unbuildable as drawn.**
- **Draft, parting line, and demoldability** for a two-part mold.
- **Layup-driven minimum thickness** — a carbon skin plus core has a floor.
- **Shrinkage and layup allowance** — flagged in the fabrication base as unaddressed and still is.

**These are constraints in the optimiser's sense**, and omitting them means the optimiser will
happily converge on a wing nobody can build. The thinnest-is-best result from Phase 0 makes this
*more* urgent, not less.

### GAP-08 · Project data model, persistence and provenance

Sketched in one paragraph (append-only versions, results reference the geometry that produced them)
and never researched. Open:

- What is a "project"? One wing, or a family of variants?
- How are sweeps, CFD runs and their results stored — especially results that took hours?
- How is a result invalidated when the geometry changes underneath it?
- File format for our own import path (COMMIT-03) — this is now **load-bearing**, since it is the
  only import route.

### GAP-09 · How the application itself is tested

We have been rigorous about validating *physics* and silent about validating *software*. Testing a
numerical application has established practice we have not gathered — analytic reference cases,
method of manufactured solutions, golden-master regression on solver output, tolerance-based
comparison. The Phase 0 parser defect (Lednicer files read as Selig, returning *plausible* wrong
geometry) is exactly the class this addresses, and it was caught by luck of good instinct rather
than by a strategy.

---

## Tier 3 — worth knowing, not blocking

| # | Gap | Why it matters |
|---|---|---|
| **10** | **Roughness and fouling** | XFOIL's e^N assumes clean, smooth, 2D transition. Real foils are scratched, sanded and grow algae. Published performance is a best case, and users will notice |
| **11** | **Junction and interference drag** | Even designing one wing, the fuselage/mast junction sits at the root where loading is highest. Listed as excluded from the estimator and never quantified |
| **12** | **Real product benchmarks** | We have geometry *bands* from retailer guides but no actual product specs (Axis, Armstrong, Unifoil, F-One) to sanity-check output against. A tool that proposes a wing unlike anything on the market is either innovative or wrong, and we cannot currently tell which |
| **13** | **Class and box rules** | Racing classes may constrain span, area or configuration. If the user is designing for competition this is a hard constraint we do not model |
| **14** | **Safety framing** | A foil failing at 25 kn injures someone. What the tool says about its own limits — and does not claim — is a real design question, not a legal footnote |
| **15** | **Colour maps and accessibility** | Flagged in the visualisation base, never researched. The default rainbow map is known-poor for scalar fields, and nothing has been decided about colour-blind safety in a tool whose output is colour-encoded fields |
| **16** | **Onboarding and the empty state** | Every proposal shows a populated screen. What the user sees on first launch, with no design, is undesigned |

---

## Process gaps — how this project has been run

Two observations about method rather than content.

### PROC-01 · The domain-expert personas were never added

`/adddomainexperts` has been recommended at the end of every knowledge pass and **never run**. There
is no marine-hydrodynamics lens, no GPU/HPC lens, and no structures lens in the persona roster. Every
finding in this base has been produced and reviewed by the same general-purpose reasoning, which is
precisely the silo the pack's adversarial-review discipline exists to break.

**Given GAP-02, a structures lens is now the most valuable one to add**, and it would have caught
that gap earlier.

### PROC-02 · No architecture decisions have been recorded

There are twenty knowledge artifacts, four proposals and **zero ADRs**. Real decisions have been
made — layered fidelity tiers, station-and-loft geometry, WPF + HelixToolkit, native CUDA over
ILGPU, permissive licensing only — and they live in prose inside proposals rather than as decision
records with context, options and consequences.

`decision-0001-geometry-kernel` is the first, written today. **The rest should be back-filled before
`/specify`**, because a specification that rests on undocumented architecture decisions cannot be
reviewed against them.

---

## What to do next, in priority order

1. **GAP-04 (units and conventions)** — cheapest to close, most expensive to leave. Write it now.
2. **GAP-03 (who the user is)** — everything downstream of a wrong answer is wasted, and it gates
   the three UX proposals.
3. **GAP-02 (structures)** — the largest genuine hole, and closing it makes the tool materially
   better rather than merely more complete.
4. **GAP-01 (validation)** — the data has now been located; extract DTIC ADA032272 and build the
   first real validation case.
5. **PROC-01 (domain experts)** — cheap, and it improves everything after it.
6. **GAP-07 (manufacturing constraints)** — needed before the optimiser is trusted to propose shapes.

## Sources gathered during this review

| Source | Type | URL |
|---|---|---|
| DTIC ADA032272 — Lift and Drag Characteristics of NACA 16-309 and NACA 64A309 Hydrofoils (DTNSRDC) | primary (experimental) | https://archive.org/details/DTIC_ADA032272 |
| Static hydroelastic study of composite T-foils with beam and lifting line models | primary (peer-reviewed) | https://proceedings.open.tudelft.nl/imdc24/article/download/900/912 |
| Static and dynamic response of a carbon composite full-scale hydrofoil (automated fibre placement) | primary (peer-reviewed) | https://www.sciencedirect.com/science/article/pii/S2666682021001109 |
| Load-dependent bend-twist coupling on composite hydrofoils | primary (peer-reviewed) | https://www.sciencedirect.com/science/article/abs/pii/S0263822317317130 |
| Strouhal number impact on propulsion efficiency in oscillating foils | primary (peer-reviewed) | https://www.sciencedirect.com/science/article/abs/pii/S0029801824000234 |
| Variable thrust and high efficiency propulsion with oscillating foils at high Re | primary (arXiv) | https://arxiv.org/pdf/1907.01097 |
| A scaling law for thrust generating unsteady hydrofoils | primary (peer-reviewed) | https://www.sciencedirect.com/science/article/abs/pii/S0889974615300530 |

All accessed 2026-09-06.
