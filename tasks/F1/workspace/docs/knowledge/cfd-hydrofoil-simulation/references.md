---
id: kb-cfd-references
title: "Reference Standards, Specifications and Seminal Works"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [references, standards, ittc, iapws, teos-10, savitsky]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
review-by: 2026-12-04
summary: >-
  The standards, specifications and seminal works this project must honour — ITTC water properties,
  IAPWS/TEOS-10, NVIDIA Blackwell compatibility, and the foundational method papers for planing
  hulls, potential-flow foil analysis and lattice Boltzmann.
---

# Reference information

## Standards & regulations

- **ITTC Recommended Procedures and Guidelines 7.5-02-01-03 Rev 02 — Fresh Water and Seawater
  Properties** (International Towing Tank Conference, effective 2011).
  *Scope:* authoritative density, absolute viscosity, kinematic viscosity and vapour pressure for
  fresh water and standard seawater, tabulated per degree C.
  *What it requires of us:* this is the source of truth for fluid properties. Values must be taken
  from it rather than from textbook approximations, and the standard salinity
  (S_A = 35.16504 g/kg) must be stated wherever seawater is claimed. *(Verified — primary)*

- **IAPWS** (International Association for the Properties of Water and Steam) — the underlying
  international standard for fresh-water properties; ITTC derives its fresh-water table from it.

- **TEOS-10** (Thermodynamic Equation of Seawater 2010) — the underlying standard for seawater
  properties, including the definition of **absolute salinity**. TEOS-10 absolute salinity is *not*
  the older practical salinity (PSU) scale.

- **NVIDIA Blackwell Compatibility Guide** — defines what is required to run and compile for
  compute capability 12.0. *Requires of us:* CUDA Toolkit **12.8 or newer** for native `sm_120`
  cubin generation; older toolkits are forward-compatible **only via shipped PTX**. *(Verified)*

## Specifications & primary sources

- **FluidX3D** (ProjectPhysX, Dr. Moritz Lehmann) — the authoritative source for current LBM
  memory-efficiency and throughput figures: 93 B/cell FP32, **55 B/cell FP32/FP16**, and the
  per-GPU benchmark table including **19,141 MLUPs/s on desktop RTX 5090**. Licence: free for
  non-commercial use. *(Verified — primary)*

- **ILGPU** (m4rs-mt) — the .NET GPU JIT compiler. Current release **v1.5.3 (July 2024)**; licensed
  under the University of Illinois/NCSA Open Source License; requires VS 2022+ / .NET 6.0 SDK
  toolchain. *(Verified — primary; Blackwell support unaddressed)*

- **Typhoon** (Maritime Technology Division, Ghent University; GitHub `MaritiemUGent/Typhoon`) —
  open-source hydrofoil craft analysis: static forces and moments, Newton-Raphson equilibrium for
  trim and elevation, eigenvalue stability matrix. *(Verified — primary for capabilities)*

- **SU2** (Stanford ADL) — the AIAA papers are the authoritative description of the solver design:
  compressible RANS core with incompressible and artificial-compressibility options, level-set free
  surface, adjoint-based shape optimisation. *(Verified — primary)*

## Seminal / foundational works

- **Savitsky, D. (1964), Hydrodynamic Design of Planing Hulls** — the foundational empirical planing
  method. Lift, drag, wetted area, centre of pressure and porpoising limits as functions of speed,
  trim, deadrise and loading. Still the practitioner default sixty years on. **This is the cheapest
  credible answer to the surfboard half of the brief.**

- **Drela, M. — XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils** — the 2D
  viscous/inviscid coupled panel method whose polars underpin XFLR5 and most low-order foil work.

- **LBM foundations** — the stream-and-collide formulation with BGK collision; Smagorinsky-Lilly for
  subgrid turbulence; VOF+PLIC for free surface; momentum-exchange for force evaluation on curved
  boundaries. These are the specific components any hand-written solver would implement.

## Where the standards bite this project

1. Fluid properties come from ITTC, not from memory or a textbook. Two fluids, one code path.
2. Seawater without a stated salinity is meaningless — carry S_A explicitly.
3. Any GPU kernel targets `sm_120` with CUDA 12.8+, or ships PTX.
4. Any planing claim should be checked against Savitsky before a solver is trusted; any foil claim
   against XFOIL/XFLR5 polars.
