---
id: kb-cfd-open-questions
title: "Open Questions and Domain Failure Modes"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [open-questions, risks, failure-modes, disconfirming]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
review-by: 2026-12-04
summary: >-
  What the research could not settle, the ways this domain silently produces wrong answers, and the
  disconfirming views deliberately sought against the headline findings — including the strongest
  argument for not building this at all.
---

# Open questions & domain failure modes

## Unresolved by research — each needs a spike, not an opinion

1. **Does ILGPU work on Blackwell (sm_120)?** *(Flagged, load-bearing)*
   Latest release is **v1.5.3, July 2024**, predating Blackwell hardware. Release notes mention
   "improved CUDA compatibility with future devices" but never name sm_120. NuGet confirms 1.5.3 as
   current. **What would settle it:** run a trivial ILGPU kernel on this machine. Thirty minutes.
   **What breaks if wrong:** the entire pure-.NET GPU path, forcing a native C++/CUDA boundary.

2. **Is LBM accurate enough for foil lift/drag at Re 5.5e5-1.6e6?** *(Flagged, load-bearing)*
   Published LBM airfoil validation clusters at Re 2e5-5e5 with good agreement. Our envelope sits
   **above** that. Bounce-back walls are known to mispredict shear drag on coarse grids at high Re.
   **What would settle it:** simulate a NACA section at a Reynolds number with published
   experimental polars and compare CL and CD directly. **What breaks if wrong:** drag predictions
   are unusable, though lift may remain acceptable — lift is pressure-dominated, drag is
   shear-sensitive. A tool that gets lift right and drag wrong is still useful, but only if it says so.

3. **What is this machine's actual LBM throughput?** *(Flagged)*
   All performance figures here are bandwidth-scaled from a **desktop** RTX 5090 benchmark. Laptop
   thermal and power limits (175 W observed cap) are not in that model. **What would settle it:**
   run the FluidX3D benchmark on this machine. Under an hour.

4. **What numerical method does Typhoon actually use?** *(Flagged)*
   Its site documents capabilities (Newton-Raphson equilibrium, eigenvalue stability) but never the
   underlying hydrodynamic method. **Settle by reading the GitHub source.** Matters because Typhoon
   may already be the answer to the hydrofoil half of the brief.

5. **Is the target use commercial?** *(Unresolved — a licensing question, not a technical one)*
   FluidX3D is **free for non-commercial use only**. If this tool is ever sold, FluidX3D cannot be
   a component and its role is reduced to a validation reference.

6. **What validation data will be used?** No hydrofoil experimental dataset has been identified for
   this project. **A solver with no validation case is not a solver, it is a renderer.**

## Known failure modes of this domain — where errors are silent and expensive

- **Plausible-looking wrong answers.** CFD always produces a colourful field. Nothing about a
  converged run indicates it is physically right. This domain has no natural error signal, which is
  precisely why the validation case above is non-negotiable.
- **Free-surface numerical artefacts.** `interFoam` is documented to produce free-surface wiggles
  and spurious light-phase acceleration. These look like physics. They are not.
- **The unit-and-scale error class.** Kinematic vs dynamic viscosity, PSU vs absolute salinity,
  knots vs m/s, model vs full scale. Each is a silent factor error. Mitigation: carry units in the
  type system, not in comments.
- **Reynolds-number extrapolation.** A polar computed at one Re applied at another is a common and
  invisible error. Foiling spans a 3x Reynolds range across its speed envelope.
- **Confusing ventilation with cavitation.** Different physics, different triggers, different
  mitigations — and ventilation has **hysteresis**, so a steady-state solver cannot capture onset
  and washout with one curve.
- **Linear methods used past their validity.** VLM and panel methods return a confident number at
  30 degrees angle of attack. It is meaningless — stall is not in the model. Any tool exposing these
  methods must **enforce** the validity envelope rather than document it.
- **Trim/sinkage divergence.** Free-attitude planing simulations are reported to diverge from
  experiment beyond V/sqrt(L) > 2.79, and practitioners report bow-sinking instabilities in coupled
  solvers.

## Disconfirming views deliberately sought

**Against headline finding 3 ("hardware is not the constraint"):**
Sought and partially sustained. The counter-argument is that uniform-grid LBM without AMR means the
tight 43 M-cell box is the *only* affordable configuration — widen the domain to capture free-surface
waves or a whole board and cost rises as dx^-3 over the entire volume. **The finding survives for a
foil in a tight box; it does not survive for a full free-surface craft simulation.** Rewritten
accordingly in `data-and-constants.md`.

**Against headline finding 1 ("salt vs fresh is just parameters"):**
Sought, not overturned. Both fluids are Newtonian and incompressible at these speeds; the only
candidate exception is that salinity changes cavitation-nucleation behaviour, which matters only if
cavitation modelling enters scope. Finding stands, with that boundary noted.

**Against building anything at all — the strongest counter-argument, stated at full strength:**

> XFLR5 is free, mature, and already couples XFOIL viscous polars to 3D panel methods. Typhoon is
> free, open source, and already solves whole-craft hydrofoil equilibrium with stability
> eigenvalues. FluidX3D is free for non-commercial use and is *the fastest LBM implementation in
> existence* — nothing hand-written on one laptop will beat 19,141 MLUPs/s and 55 bytes/cell. For
> the surfboard, Savitsky's equations fit on one page and have sixty years of practitioner trust.
> Every component of the stated problem already has a free, better-validated solution. Building a
> new one is a learning exercise, not an engineering necessity.

**How it fared: it substantially survives, and it must shape the scope.** The evidence does not
support building a general CFD package or a faster LBM kernel. It does support a narrower claim —
that **no existing tool joins foil design, free-surface effects, craft equilibrium and interactive
visualisation into one Windows application**, and that free-surface effects on shallowly submerged
foils are a first-order gap in Band C specifically.

The honest conclusion: **the defensible project is an integrated application over largely
established methods, not a novel solver.** Any proposal claiming otherwise is arguing against this
evidence base and owes a rebuttal.

---

# v2 additions (2026-09-05) — hydrofoil-only scope

## The case-against, re-tested on the narrower scope

The v1 counter-argument rested on three gaps. **The scope cut removes one of them** (planing), so
the argument had to be re-run rather than carried forward.

**The remaining gaps, and whether each still holds:**

| Gap | Status after the cut |
|---|---|
| **Free surface** — no small tool models submergence effects or ventilation | **Holds, and is now the load-bearing justification.** Hydrofoils run shallow; lift falls with submergence and ventilation can collapse it. XFLR5 and Typhoon cannot see this at all |
| ~~Planing~~ | **Retired with the scope cut** |
| **Integration** — nothing joins section choice, parametric geometry, estimation and craft equilibrium in one interactive application | **Holds, and v2 strengthened it.** The estimation chain and the catalog are real, absent capabilities, not repackaging |

**A gap v2 added that v1 did not see:** no tool in this domain couples a **section catalog with
`Cp_min` retained** to a **cavitation check** and a **live L/D estimate over a parametric
multi-surface assembly**. XFLR5 has the polars but no cavitation model and no hydrofoil framing;
Typhoon has craft equilibrium but its numerical method is undocumented; the retail sizing guides
have discipline knowledge but no physics.

**Verdict: the case-against survives the cut, but with less margin.** The honest position is now:

> The defensible project is a **design tool** whose core is closed-form estimation over a
> parametric geometry model, with simulation reserved for free-surface and separation questions
> no low-order method can reach. It is not a CFD package, and on the hydrofoil-only scope it is
> **closer to a better XFLR5-for-hydrofoils than to a new solver.** That is a smaller claim than
> v1 made, and it should be stated that way rather than dressed up.

## New open questions from v2

7. **What thickness ratio should a water-sports foil actually use?** *(Flagged, load-bearing —
   the largest evidence gap in the base)*
   The only quantitative source found (10–12% typical, 8–10% thin, 12–15% thick) is a retailer blog
   **whose adjacent tables were demonstrably garbled** — it published aspect ratios of "80–120",
   which are physically impossible. A source that mangles one table is not trustworthy on another.
   **What would settle it:** measure it. Sweep `t/c` through the estimator with XFOIL polars at our
   Reynolds numbers and find where the L/D penalty appears. This is a question the tool being
   proposed can answer about itself.
   **What breaks if wrong:** default sections and the catalog's recommendations mislead users.

8. **Which coordinate revision of each Eppler section is authoritative?** *(Flagged)*
   Coordinates in circulation differ in point count and trailing-edge treatment, and those
   differences change XFOIL results. Eppler's own *Airfoil Design and Data* is out of print and was
   not obtained. **Settle by** fixing a provenance policy per section and recording the revision,
   rather than by finding one true file.

9. **Do published aspect ratios use projected, developed or planform area?** *(Flagged)*
   Sources confirm manufacturers differ but none states the conventions. Matters only for comparing
   against published specs, not for the tool's own numbers — which is itself the mitigation.

10. **How much drag does the strut actually contribute?** *(Unresolved)*
    The estimator is wing-only, and the strut is a large fraction of real-world foil drag. No source
    in this research quantified the split for water-sports foils. **Settle by** applying the same
    estimation chain to the strut as a low-aspect surface-piercing surface, then validating the
    total against a measured whole-craft L/D — which requires a measurement that does not yet exist.

11. **Is spline lofting between sparse stations safe?** *(Inferred risk, not measured)*
    Spline interpolation can introduce curvature reversals that are hydrodynamically real and
    visually invisible. **Mitigate** with a curvature check surfaced in the UI rather than trusting
    the interpolation.

## New failure modes surfaced in v2

- **Trusting a source that is internally inconsistent.** The IHS document gives both
  `V_crit = 14/sqrt(sigma_i)` and `pv = 17000 Pa`; these contradict each other by a factor of ten in
  vapour pressure. Deriving the constant caught it. **The general lesson: when a source gives both a
  formula and its inputs, re-derive — the redundancy is a free consistency check.**
- **Ingesting a manufacturer's aspect ratio as truth**, importing an unknown area convention.
- **Storing area or aspect ratio alongside the geometry that implies it** — guaranteed drift, and no
  way to say which is right.
- **A polar without `Ncrit`** is not reproducible; a polar without `Cp_min` cannot support a
  cavitation check. Both omissions are silent.
- **Quoting wing-only L/D as whole-craft L/D** — flattering by an unquantified margin.

---

# Phase 0 resolutions (2026-09-05)

Three of the questions above are now **CLOSED by measurement**. Full evidence in
`phase-0-findings.md`.

## CLOSED — Q7, thickness ratio (was the largest gap in the base)

**Answer: the question was malformed.** There is no hydrodynamic optimum. Section L/D and cavitation
margin both fall **monotonically** from 6% to 20% t/c, at both Re 6e5 and 1e6. Thickness is a
**structural variable with a hydrodynamic price**, and the price is now quantified: 9%→12% costs
~14% of section L/D and 3.8 kn of cavitation-free speed. The retail band of 10–12% was not wrong
about the range, but wrong about the reason — and calling it an optimum would send a designer
hunting a maximum that does not exist.

Independently corroborated: the five *cambered* Eppler hydrofoil sections measure 7.90%–10.98% t/c,
which is what "as thin as the structure allows" predicts.

*Residual:* computed with a surrogate (NeuralFoil), so the trend is reliable and absolute drag is
not. Re-run through XFOIL before anything structural depends on the magnitude.

## CLOSED — Q8, Eppler coordinate provenance

Eleven sections vendored from UIUC with SHA-256 hashes, source URL, retrieval date and measured
geometry in `sections/manifest.md`. The provenance policy is now concrete: the `.dat` file in the
repo is the record, and geometry is measured from it rather than transcribed.

**A defect was caught in the process and is worth recording as a class.** The first parser read
every file as Selig format and returned 6.00% thickness with 3.00% camber for NACA 0012 — impossible
for a symmetric section. Six of the eight Eppler files are **Lednicer** format. It was caught only
because analytic NACA sections were used as a regression test *before* the Eppler numbers were
trusted. **Class: a file-format assumption that produces plausible-looking wrong numbers rather than
an error.** Control: format detection in the parser, with the analytic NACA check as its test.

## CLOSED — Q4, Typhoon's numerical method

**Tornado vortex lattice method** — `fLattice_setup2.m` states verbatim *"This file is part of
Tornado"*, Tomas Melin, 1999/2007, **GPL v2+**, MATLAB.

Reclassified: Typhoon is **not** a possible answer to the hydrofoil half of the brief, because GPL
copyleft and a MATLAB runtime rule out reuse. It is a **reference and a validation benchmark** — and
it independently corroborates the Option 2 architecture, since the only open-source tool solving
whole-craft hydrofoil equilibrium chose exactly the recommended method.

## Partially addressed — Q9, aspect-ratio conventions

Not resolved and probably not resolvable from public sources. The mitigation stands and is
sufficient: compute AR from own geometry under a stated convention, and never ingest a published
figure as truth.

## STILL OPEN — the GPU questions

Q1 (ILGPU on Blackwell), Q2 (LBM accuracy above Re 10⁶), Q3 (real throughput) and Q10 (strut drag
share) all remain open. Q1–Q3 need a CUDA Toolkit install, which requires elevation and was out of
scope for this pass. **None blocks Phase 1**, which is layers 1–3 and touches no GPU.

## New question from Phase 0

12. **Does the discrete-station `Cp_min` under-read sharp suction peaks enough to matter?**
    *(Inferred risk, load-bearing for the cavitation check)*
    `Cp_min` is recovered from 32 boundary-layer edge-velocity stations per surface. A suction peak
    *between* stations is invisible, which biases `V_crit` **optimistically** — the reported
    cavitation-free speed is a best case. For a safety-relevant check that is the wrong direction to
    err. **Settle by** comparing against a true XFOIL pressure distribution on a section with a known
    sharp peak (NACA 4412 at incidence is a good candidate). **Mitigate meanwhile** by applying an
    explicit margin and labelling the number as optimistic in the UI.
