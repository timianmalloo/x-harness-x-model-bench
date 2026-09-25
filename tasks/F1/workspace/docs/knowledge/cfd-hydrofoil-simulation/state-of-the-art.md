---
id: kb-cfd-state-of-the-art
title: "State of the Art — Hydrofoil and Planing-Craft Simulation"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [cfd, state-of-the-art, lbm, panel-method, rans, surrogate]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
review-by: 2026-12-04
summary: >-
  Current best-practice methods for hydrofoil and planing-craft hydrodynamics, ordered by cost:
  empirical correlations, potential-flow panel/VLM methods, GPU lattice Boltzmann, RANS+VOF, and
  ML surrogates — with where each wins and where each fails.
---

# State of the art

> **SCOPE NOTE (v2, 2026-09-05).** The project no longer covers surfboards or planing craft.
> Section 1 (Savitsky) and the free-surface/6-DOF parts of section 4 are **RETIRED** — kept because
> the two-tier architecture was reasoned from them, not deleted. Sections 2, 3 and 5 remain live.

Methods are listed **cheapest first**. Cost spans roughly nine orders of magnitude from top to
bottom, and that spread — not any single method's merit — is the design lever.

## 1. Empirical correlations — Savitsky planing method  `[RETIRED — v2 scope cut]`

**What it is.** Savitsky (1964) reduced systematic prismatic-hull towing-tank tests to algebraic
equations for lift, drag, wetted area, centre of pressure and porpoising stability, as functions of
speed, trim, deadrise and loading. *(Verified)*

- **Wins:** microseconds to evaluate. Closed form. Decades of practitioner trust. It directly
  predicts **running trim and draft**, which is the actual question for a planing board.
- **Fails:** prismatic hulls only, calm water, steady state. Takes *geometric parameters*, not a 3D
  model — so it cannot see the shape of a real surfboard. Ignores lateral wave-making and spray,
  which are principal drag sources. Degrades in the pre-planing transition. *(Verified)*

## 2. Potential flow — lifting line, vortex lattice (VLM), panel methods

**What it is.** Solve inviscid, irrotational flow over the lifting surface only; append viscous drag
from 2D sectional polars (typically XFOIL). Meshes *surfaces*, not volumes. *(Verified)*

- **Wins:** "orders of magnitude faster than RANS" — reported execution times around **1% of an
  equivalent CFD solution**. Only the lifting surface needs meshing, so setup is seconds, not hours.
  Accurate where its assumptions hold. *(Verified)*
- **Fails:** valid only at small angle of attack, attached flow, high Reynolds. **Stall is a
  non-linear viscous effect and is simply not represented.** No 3D separation, no vortex shedding.
  The XFOIL-polar coupling assumes a finite wing behaves like an infinite one at the same local Cl.
  *(Verified)*
- **Frontier:** non-linear VLM variants recover useful viscous behaviour at a fraction of RANS cost.
  *(Verified)*

## 3. GPU lattice Boltzmann (LBM)

**What it is.** Evolve particle distribution functions on a uniform Cartesian lattice. Local, explicit
and stream-and-collide — which maps almost perfectly onto GPU memory bandwidth. *(Verified)*

- **Wins:** massively parallel by construction. Free surface via VOF+PLIC is a solved extension.
  Complex/moving geometry needs no body-fitted mesh. Memory-efficient implementations reach
  **55 bytes/cell**, roughly 19 M cells per GB. *(Verified)*
- **Fails — and this is the load-bearing weakness:** the standard bounce-back wall condition
  **cannot capture wall shear drag accurately on coarse grids at high Reynolds number**. Resolving
  wall layers at high Re demands extremely fine meshes. The BGK collision operator itself limits
  high-Re application. *(Verified)*
- **Mitigations that exist:** wall functions (WFB), RANS-coupled near-wall models, Smagorinsky-Lilly
  LES, and recent data-driven near-wall models reported to friction-Re up to 1e6. *(Verified)*
- **Validation status:** published LBM airfoil validation clusters at **Re 2e5 to 5e5**, with force
  and pressure coefficients comparing favourably. Validation **at and above 1e6 is much thinner**.
  Our envelope is 5.5e5 to 1.6e6. *(Flagged — this is the gap)*

## 4. RANS + VOF — the full package (OpenFOAM, SU2, commercial)  `[PARTLY RETIRED — planing/6-DOF only]`

**What it is.** Reynolds-averaged Navier-Stokes on a body-fitted volume mesh, with volume-of-fluid
interface capture and 6-DOF body motion for trim and sinkage.

- **Wins:** the reference standard. Handles separation, free surface, dynamic attitude together.
  Planing-hull trim/sinkage via dynamic overset mesh + SST k-omega is established practice.
  *(Verified)*
- **Fails:** cost and expertise. For free-surface work specifically, VOF **requires very high mesh
  resolution at the interface and small time steps** because of unphysical air-side accelerations.
  OpenFOAM's `interFoam` is known for **free-surface wiggles and light-phase acceleration**, needing
  extra VOF sub-cycles or shorter steps; practitioners have written replacement solvers
  (`marineFoam`, Ghost Fluid Method variants) specifically to fix it. Trim/sinkage accuracy degrades
  beyond V/sqrt(L) > 2.79. *(Verified)*
- **SU2 specifically:** primarily a *compressible aerospace* RANS solver with incompressible and
  artificial-compressibility modes; its free-surface capability is a **level-set** formulation over
  the incompressible solver. It is aimed at aerodynamic shape optimisation, not marine free surface.
  Adjoint-based shape optimisation is its genuine differentiator. *(Verified)*

## 5. ML surrogates — neural operators, DeepONet, PINNs

**What it is.** Learn the map from geometry/conditions to flow field or integrated forces, trained on
CFD or experimental data.

- **Wins:** online cost drops by orders of magnitude with "little to no degradation in prediction
  accuracy" for shape optimisation within the training distribution. Operator learning (DeepONet)
  generalises better than direct regression because it maps function to function. *(Verified)*
- **Fails:** **needs a training corpus that does not exist yet for this problem.** Accuracy is
  reported as notably worse for *high-drag* samples — precisely the off-design cases a designer
  cares about. Generalisation outside the training distribution is the open research question, not a
  solved feature. *(Verified)*
- **Implication:** a surrogate is a **phase-3 accelerator over your own solver's output**, never a
  starting point. It cannot precede the thing that generates its training data.

## The frontier

- Data-driven and physics-informed near-wall closures for LBM at high Re — active, promising, not
  yet turnkey. *(Verified)*
- Adaptive mesh refinement for free-surface LBM on multi-GPU — published, but absent from the
  fastest available implementation. *(Verified)*
- Surface-piercing and ventilating foil regimes remain genuinely hard for every method; ventilation
  onset is a stability problem with hysteresis, not a steady-state one. *(Verified)*
