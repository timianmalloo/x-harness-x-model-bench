---
id: kb-cfd-comparables
title: "Comparable Solutions — Foil and CFD Tools"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [comparables, prior-art, xflr5, typhoon, fluidx3d, openfoam, su2]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
review-by: 2026-12-04
summary: >-
  Named prior art across three bands — full CFD packages, GPU LBM solvers, and small foil-design
  tools — with what each does well and badly. Establishes that the small-tool band is already
  occupied by XFLR5, Typhoon and FoilBoard, which any new tool must beat rather than duplicate.
---

# Comparable solutions & problem framings

> **SCOPE NOTE (v2, 2026-09-05).** Surfboard/planing is out of scope. One of the three gaps that
> justified building was planing; it is struck through below and the case-against was re-tested on
> the remaining two. Band C now also includes the estimation-and-catalog gap surfaced in v2.

## Band A — full CFD packages (what the user wants to avoid)

| Solution | How it frames the problem | Approach | Does well | Does badly | Confidence |
|---|---|---|---|---|---|
| **OpenFOAM** | General PDE toolbox; you assemble the solver | Finite volume, unstructured; `interFoam` VOF for free surface | Anything, eventually. Huge marine literature. Free | Steep setup. `interFoam` shows free-surface wiggles and light-phase acceleration; needs VOF sub-cycles or shorter steps. Meshing is the real work | Verified |
| **SU2 (Stanford)** | Aerodynamic shape optimisation with adjoints | Compressible RANS core; incompressible + artificial compressibility; **level-set** free surface | Best-in-class adjoint shape optimisation. Clean C++ codebase | Aerospace-first. Free surface is peripheral, not marine-hardened. Not aimed at planing or multiphase marine work | Verified |
| **Commercial (Star-CCM+, FINE/Marine, Orca3D)** | Turnkey marine analysis | RANS+VOF, overset, 6-DOF | Validated marine workflows out of the box | Licence cost. Closed. Not the brief | Verified |

## Band B — GPU LBM solvers (the performance reference)

| Solution | Framing | Approach | Does well | Does badly | Confidence |
|---|---|---|---|---|---|
| **FluidX3D** | Maximum cells per GB, maximum cells per second | LBM, **OpenCL**, FP32/FP16 mixed precision | **55 B/cell** (vs ~93 B/cell FP32; ~19 M cells/GB). **19,141 MLUPs/s on desktop RTX 5090**. Free-surface VOF+PLIC, Smagorinsky-Lilly LES, immersed-boundary particles, GPU force/torque summation | **No adaptive mesh refinement** — uniform cell size everywhere. **OpenCL, not CUDA.** **Free for non-commercial use only.** No native .NET binding | Verified |
| **waLBerla** | HPC framework, multi-node | LBM with AMR, Python bindings | Scales to clusters; has the AMR FluidX3D lacks | Framework weight; overkill for one laptop | Verified |

**Why FluidX3D matters even though we will not ship it.** It sets the honest ceiling. Any
hand-written LBM kernel should be measured against 55 B/cell and its MLUPs/s figure; landing within
2-3x is a good result, and landing at 10x worse means the approach is being executed badly rather
than being inherently slow.

## Band C — small foil-design tools (**the band this project would enter**)

| Solution | Framing | Approach | Does well | Does badly | Confidence |
|---|---|---|---|---|---|
| **XFLR5** | Model-aircraft / foil analysis | XFOIL 2D viscous + 3D VLM/panel | Free, mature, huge community. Viscous drag from real polars. Transition and separation-bubble modelling in 2D | **Linear methods — stall is not represented.** No 3D separation, vortex shedding, or high-alpha behaviour. No free surface. Convergence issues with sparse panelling | Verified |
| **Typhoon (Ghent University)** | Whole-craft hydrofoil equilibrium | Static forces/moments; **Newton-Raphson equilibrium**; **eigenvalue stability matrix** | Open source. Solves the question owners actually ask: what trim and ride height does this craft settle at, and is it stable? | Underlying numerical method not documented on the site — needs source inspection | Verified (capabilities); Flagged (method) |
| **FoilBoard** | Kite/windsurf foil board simulator | Real-time parametric GUI | **Instant feedback with sliders** — explicitly positions responsiveness as its advantage over XFLR5 | Narrow scope; specific to its board model | Verified |
| **WingHopper / Wing_Bot** | Parametric foil geometry design | Web CAD; exports 3DM/STL/OBJ/STEP and **XFLR5-importable XML** | Geometry authoring, then hand off to XFLR5 | Design tools, not analysis tools | Verified |

## The Simplifier's challenge, stated plainly

Band C is **not empty**. XFLR5 + Typhoon + a geometry tool already covers submerged-foil design for
free, and the foiling community uses them today. A new tool must justify itself on something they
genuinely lack. From the evidence, the real gaps are:

1. **Free surface.** None of Band C models the water surface. Hydrofoils run at shallow submergence
   where lift falls off with depth and ventilation can collapse it entirely. This is a first-order
   effect that Band C cannot see at all.
2. ~~**Planing.** No Band C tool handles a surfboard.~~ `[RETIRED — v2 scope cut. This gap no longer counts toward the justification; see open-questions.md for the re-tested case.]`
3. **Integration.** Nothing joins "design the foil" to "solve the craft equilibrium" to "watch the
   flow" in one interactive Windows application.

## Adjacent problems worth borrowing from

- **Real-time graphics fluid simulation** — SIGGRAPH-lineage LBM work optimises for *interactive
  feedback over strict accuracy*, which matches a design-exploration tool better than a
  certification tool. *(Verified)*
- **Aerospace adjoint optimisation (SU2)** — the adjoint idea (one extra solve yields the gradient
  with respect to every shape parameter) is the single highest-leverage technique to borrow if
  shape optimisation is ever in scope. *(Verified)*
- **Model-aircraft aerodynamics (XFLR5)** — the whole 2D-polar-plus-3D-linear-method architecture is
  directly transferable; hydrofoils are aerofoils in denser fluid. *(Verified)*
