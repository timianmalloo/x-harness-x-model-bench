---
id: kb-cfd-data-and-constants
title: "Domain Data, Constants and Invariants"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [constants, ittc, seawater, reynolds, froude, gpu-budget]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
review-by: 2026-12-04
summary: >-
  Primary-source fluid properties for fresh water and standard seawater from ITTC 7.5-02-01-03, the
  non-dimensional groups that govern this problem, the derived Reynolds envelope for foiling, and
  the computed GPU memory and throughput budget for the target machine.
---

# Domain data, constants & invariants

## Fluid properties — primary source

**Source:** ITTC Recommended Procedures and Guidelines **7.5-02-01-03 Rev 02**, "Fresh Water and
Seawater Properties" (effective 2011). Fresh water from **IAPWS**; seawater from **TEOS-10**.
Standard pressure 0.101325 MPa; temperature scale ITS-90. Standard seawater absolute salinity
**S_A = 35.16504 g/kg**. *(Verified — values read directly from the ITTC tables)*

| Fluid | T (degC) | Density rho (kg/m^3) | Dynamic visc. mu (Pa*s) | Kinematic visc. nu (m^2/s) |
|---|---|---|---|---|
| Fresh water | 15 | 999.1026 | 0.001138 | 1.1386e-6 |
| Fresh water | 20 | 998.2072 | 0.001002 | 1.0034e-6 |
| Standard seawater | 15 | 1026.0210 | 0.001220 | 1.1892e-6 |
| Standard seawater | 20 | 1024.8103 | 0.001077 | 1.0508e-6 |

### The salt-versus-fresh delta (computed from the rows above)

| T (degC) | Delta rho | Delta nu |
|---|---|---|
| 15 | **+2.69%** | **+4.44%** |
| 20 | **+2.67%** | **+4.72%** |

**Design implications, and they are the useful kind:**

- Lift and drag *forces* scale with rho, so **seawater produces ~2.7% more force** at identical
  speed, geometry and angle of attack.
- Reynolds number scales with 1/nu, so at identical speed and chord, **seawater sits ~4.4% lower in
  Re** than fresh water — a shift well inside the scatter of any turbulence model.
- Therefore **salt vs fresh is a two-parameter configuration change, not a physics change.** It must
  never become a solver branch. *(Verified)*
- Vapour pressure is also tabulated and is the input to the **cavitation number**; it matters only
  if cavitation enters scope. Seawater at 15 degC: p_v = 1.6709e-3 MPa. *(Verified)*

## Governing non-dimensional groups

- **Reynolds number** `Re = V*c/nu` — ratio of inertial to viscous forces. Sets boundary-layer
  behaviour and transition. Chord-based here.
- **Froude number** `Fn = V/sqrt(g*L)` — ratio of inertia to gravity. **Governs everything with a
  free surface**: wave-making, planing, ventilation onset. Depth-based Froude number governs
  free-surface interaction for a submerged foil.
- **Cavitation number** `sigma = (p - p_v)/(0.5*rho*V^2)` — onset of vapour cavities.
- **Lift / drag coefficients** `CL = L/(0.5*rho*V^2*A)`, `CD = D/(0.5*rho*V^2*A)`.

**Invariant:** any result reported without the Reynolds *and* Froude number it was computed at is
not interpretable and must not be stored as a bare force value.

## Derived: the foiling Reynolds envelope

Computed at seawater, 15 degC (nu = 1.1892e-6 m^2/s). Speed bands from foiling-community sources;
chord lengths from published experimental hydrofoil studies. *(Inferred — the envelope is assembled
from community and experimental sources, not a standard)*

| Discipline | Speed | Chord | Reynolds |
|---|---|---|---|
| Surf foiling | 8 kn (4.12 m/s) | 0.16 m | **5.5e5** |
| Free ride | 17 kn (8.75 m/s) | 0.16 m | **1.18e6** |
| Racing | 28 kn (14.40 m/s) | 0.13 m | **1.57e6** |
| Racing, small chord | 32 kn (16.46 m/s) | 0.10 m | **1.38e6** |

**Envelope: Re ≈ 5.5e5 to 1.6e6.** Community categorisation independently corroborates this band
(racers ~1e6, free riders ~6.5e5). This is the transitional-to-fully-turbulent regime: laminar
assumptions are invalid, and it sits **at or above where LBM airfoil validation is well
established**. That tension is the central technical risk in this project.

## Target hardware budget — computed, not assumed

**Machine (measured via `nvidia-smi`, 2026-09-05):** NVIDIA GeForce RTX 5090 **Laptop** GPU,
compute capability **12.0**, 24463 MiB VRAM, driver 591.91, CUDA 13.1 capable.
Memory bandwidth **896 GB/s** (256-bit GDDR7). *(Verified for the GPU; bandwidth from vendor
specification sources — Flagged, not read off the device)*

### Memory capacity at LBM cell densities

Assuming 85% of VRAM usable for the lattice:

| Precision scheme | Bytes/cell | Cells | Equivalent cube |
|---|---|---|---|
| FP32/FP32 | 93 | **234 M** | 617^3 |
| FP32/FP16 | 55 | **396 M** | 735^3 |

### Throughput estimate

The published FluidX3D benchmark of **19,141 MLUPs/s** is for the **desktop** RTX 5090 at
1792 GB/s. LBM is bandwidth-bound, so scaling linearly by bandwidth:

**896/1792 = 0.5 → ~9,570 MLUPs/s estimated on this laptop.** *(Inferred — never measured on this
machine. Must be measured before any plan depends on it.)*

| Domain size | Steps/s (est.) | ms/step |
|---|---|---|
| 50 M cells | 191 | 5.2 |
| 100 M cells | 96 | 10.4 |
| 200 M cells | 48 | 20.9 |
| 400 M cells | 24 | 41.8 |

### Resolution budget for a 3D hydrofoil box

Chord 0.16 m, domain 8c x 5c x 5c (1.28 x 0.80 x 0.80 m), uniform Cartesian:

| Cells per chord | dx | Cells | Est. steps/s |
|---|---|---|---|
| 20 | 8.0 mm | 1.6 M | ~6,000 |
| 30 | 5.3 mm | 5.4 M | ~1,780 |
| 40 | 4.0 mm | 12.8 M | ~750 |
| **60** | **2.7 mm** | **43.2 M** | **~220** |

**This is the headline engineering fact of the whole base:** a 60-cells-per-chord 3D hydrofoil
simulation is ~43 M cells and fits comfortably, with throughput to spare for interactivity. The GPU
is not the constraint. *(Inferred, from the Verified memory figures and the Flagged bandwidth scaling)*

**Caveat that limits this:** uniform Cartesian grids have **no adaptive refinement**, so enlarging
the domain or refining the foil raises cost as dx^-3 across the *entire* box. The budget above is
only valid for a tight domain around the foil.

## Toolchain constants

- **CUDA Toolkit 12.8** is the minimum for native `sm_120` cubin generation. Applications built with
  older toolkits run on Blackwell **only if they ship PTX** for JIT recompilation. *(Verified)*
- This machine's driver supports up to CUDA 13.1; **no CUDA Toolkit is currently installed.**
  *(Verified)*
- .NET SDK 10.0.303 with `Microsoft.WindowsDesktop.App` 10.0.11 present. Visual Studio Community
  2026 (18.7) with the MSVC x64 toolset — which is the host compiler `nvcc` requires. *(Verified)*
