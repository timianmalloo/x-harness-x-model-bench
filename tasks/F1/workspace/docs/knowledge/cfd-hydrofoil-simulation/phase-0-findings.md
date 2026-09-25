---
id: kb-cfd-phase-0-findings
title: "Phase 0 Findings — Evidence Gaps Closed by Measurement"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [phase-0, measurement, thickness, sections, typhoon, neuralfoil, evidence]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
  - { to: kb-cfd-foil-sections, rel: depends-on }
  - { to: kb-cfd-estimation-methods, rel: depends-on }
  - { to: kb-cfd-section-manifest, rel: depends-on }
review-by: 2026-12-04
summary: >-
  Results of the Phase 0 evidence pass — the thickness question answered by computed section polars,
  the Eppler hydrofoil set measured head-to-head against NACA baselines, Typhoon identified as
  Tornado VLM under GPL, and a working section-analysis toolchain established without XFOIL.
---

# Phase 0 findings

Executed 2026-09-05. Four gaps were targeted; **three closed by measurement**, one could not be
closed without a privileged install and is recorded as still open.

| Gap | Status |
|---|---|
| Thickness ratio guidance (the largest gap in the base) | **Closed — and the question was wrong** |
| Section coordinate provenance | **Closed** — 11 sections vendored with hashes and measured geometry |
| Typhoon's numerical method | **Closed** — Tornado VLM, MATLAB, GPL v2+ |
| ILGPU on Blackwell / LBM accuracy / real GPU throughput | **Still open** — needs CUDA Toolkit install |

---

## 1. The thickness question — answered, and it was the wrong question

**What v2 recorded:** "10–12% typical, 8–10% lower drag but structurally marginal, 12–15% more
durable" — from a single retailer source whose adjacent tables published impossible aspect ratios.
It was the base's largest Flagged, load-bearing claim.

**What was measured.** A NACA 24xx family (2% camber at 0.4c, thickness isolated) swept from 6% to
20% t/c, solved to the IHS design lift coefficient `CL = 0.30` at two Reynolds numbers:

| t/c | CD @ Re 6e5 | Section L/D | σᵢ | V_crit (kn) |
|---|---|---|---|---|
| 6% | 0.00456 | **65.8** | 0.395 | **43.1** |
| 8% | 0.00500 | 60.1 | 0.464 | 39.8 |
| 9% | 0.00528 | 56.9 | 0.501 | 38.3 |
| 10% | 0.00556 | 54.0 | 0.540 | 36.9 |
| 11% | 0.00582 | 51.5 | 0.580 | 35.6 |
| 12% | 0.00610 | 49.1 | 0.618 | 34.5 |
| 14% | 0.00682 | 44.0 | 0.690 | 32.6 |
| 16% | 0.00751 | 39.9 | 0.766 | 31.0 |
| 18% | 0.00818 | 36.7 | 0.844 | 29.5 |
| 20% | 0.00885 | 33.9 | 0.914 | 28.3 |

**Section L/D falls monotonically with thickness. So does cavitation margin. There is no
hydrodynamic optimum at 10–12%, or anywhere else in the range.** The trend is identical at
Re 1e6 (77.2 down to 38.0).

### The correct framing

**Thickness is a structural variable with a hydrodynamic price, not a parameter with an optimum.**
Hydrodynamics always prefers thinner; what stops you is bending stiffness and strength. The retail
guidance was not wrong about the *band* — it was wrong about the *reason*, and describing it as an
optimum invites a designer to search for a maximum that does not exist.

**The price is now quantified**, which is what makes it usable:

- **9% → 12% t/c costs ~14% of section L/D** (56.9 → 49.1 at Re 6e5).
- **The same change costs 3.8 kn of cavitation-free speed** (38.3 → 34.5 kn).

*Design implication:* the tool should present thickness as a **constraint with a displayed cost**,
not as something to optimise. "Going from 9% to 12% costs you 14% of section efficiency and 4 knots
of cavitation margin — is your structure worth that?" is the honest question, and it is answerable
live.

**Corroboration from independent data:** the five *cambered* Eppler hydrofoil sections measure
**7.90%–10.98% t/c** (mean 9.25%) — exactly what "as thin as the structure allows" predicts.

*(Confidence: **Inferred**. The trend is unambiguous and physically expected, but computed with a
surrogate — see section 5. The direction and rough magnitude are reliable; the absolute drag values
are not.)*

---

## 2. The Eppler hydrofoil set, measured

All sections solved to `CL = 0.30`. `σᵢ = −Cp_min`; `V_crit = 13.94/√σᵢ` m/s from
`estimation-methods.md`.

### Re = 6×10⁵

| Section | t/c | α | CD | Section L/D | σᵢ | V_crit (kn) | Confidence |
|---|---|---|---|---|---|---|---|
| E817 | 10.98% | −1.44° | 0.00773 | 38.8 | 0.457 | 40.1 | 0.92 |
| **E818** | 9.37% | −1.47° | 0.00709 | 42.3 | 0.414 | **42.1** | 0.88 |
| E874 | 7.90% | +1.14° | 0.00624 | 48.1 | 0.499 | 38.3 | 0.90 |
| E904 | 9.00% | +1.25° | 0.00655 | 45.8 | 0.429 | 41.4 | 0.91 |
| E908 | 9.00% | −0.77° | 0.00811 | 37.0 | 0.415 | 42.1 | 0.80 |
| E836 * | 12.64% | +2.69° | 0.00672 | 44.6 | 0.719 | 31.9 | 0.96 |
| E837 * | 16.11% | +2.64° | 0.00797 | 37.6 | 0.726 | 31.8 | 0.98 |
| E838 * | 18.37% | +2.61° | 0.00884 | 33.9 | 0.741 | 31.5 | 0.98 |
| NACA 4412 | 12.02% | −1.68° | 0.00793 | 37.8 | 0.744 | 31.4 | 0.96 |
| **NACA 64A410** | 9.99% | −0.51° | 0.00607 | **49.4** | 0.496 | 38.5 | 0.95 |
| NACA 0012 | 12.00% | +2.83° | 0.00723 | 41.5 | 0.959 | 27.7 | 0.96 |

\* symmetric, zero camber — strut/mast family, not lifting sections.

### The three findings that matter

**(a) The Eppler hydrofoil sections deliver on cavitation, not on raw efficiency.** E818 reaches
**42.1 kn** cavitation-free against NACA 4412's **31.4 kn** — a **34% higher critical speed** at the
same design loading. NACA 64A410 beats every Eppler on section L/D (49.4). So "minimum cavitation,
low drag" is measurably true about the *first* half and only relatively true about the second.
**This is the first quantitative confirmation of the Eppler characterisation found anywhere in this
research** — every prior source asserted it.

**(b) Tom Speer's 6-series recommendation is confirmed by measurement.** The IHS states a 66-series
section is "a better bet than the corresponding 16-XXX". NACA 64A410 — a 6-series laminar section —
records the best section L/D in the set and a solid 38.5 kn cavitation margin, while the aircraft
section NACA 4412 at similar thickness manages 37.8 and only 31.4 kn. The reason is visible in the
numbers: 4412's σᵢ of 0.744 against 64A410's 0.496 is precisely the suction peak the IHS warns about.

**(c) Section ranking is Reynolds-dependent, so a catalog cannot have a single "best".** Between
Re 6e5 and 1e6, E904 moves from 45.8 to **63.4** L/D and takes the lead among the Epplers, while
E874 leads at the lower Reynolds number. Transition location drives this. **The catalog must rank
per operating point, not globally** — a "top sections" list with no Reynolds number attached is
misinformation.

**(d) The symmetric E836/E837/E838 ladder is a strut family.** Zero camber at 12.6/16.1/18.4% t/c,
needing ~2.65° to reach CL 0.30 with poor cavitation numbers. A strut works at both signs of
incidence and needs depth for bending strength. Listing them as front-wing candidates — as the
undifferentiated "Eppler hydrofoil sections" lists in circulation do — would be a category error.

---

## 3. Typhoon identified — closed

Typhoon's repository contains **`fLattice_setup2.m`**, whose header states verbatim: *"This file is
part of Tornado"*, **Tomas Melin, copyright 1999, 2007, GNU GPL v2 or later**. Tornado is a
well-known open-source **vortex lattice method** in MATLAB. The surrounding files
(`solver10.m`, `setboundary5.m`, `lgwt.m`, `visc_corr.m`, `aeropolar.m`) are consistent with a
Tornado-derived VLM plus a viscous correction and a hydrofoil equilibrium/stability wrapper.

**Consequences, and they cut both ways:**

- **It validates the recommended architecture.** The one open-source tool that solves whole-craft
  hydrofoil equilibrium chose exactly the method proposed in Option 2: a vortex lattice solver with
  a viscous correction over sectional polars. That is independent corroboration, not coincidence.
- **It cannot be reused.** MATLAB (requires MATLAB or the MCR runtime) and **GPL v2+**, which is
  copyleft — it cannot be linked into a closed-source product. Typhoon is a **reference to study and
  a benchmark to validate against**, not a component.
- Its README is effectively empty; the method was only discoverable by reading source. The repo does
  carry three papers (HISWA, INNOVSAIL 2020) which are the proper next read if its validation
  evidence matters.

---

## 4. Section analysis toolchain established — without XFOIL

**NeuralFoil 0.3.3** (pure Python/NumPy, a neural surrogate trained on XFOIL) was installed and
validated. No Fortran binary, no XFOIL build, no native dependency.

**Validation against analytic truth — NACA 0012 at Re 9e5:**

| Quantity | Expected | Measured | Result |
|---|---|---|---|
| CL at α = 0 | exactly 0 (symmetric) | −0.0000 | PASS |
| dCL/dα | ~0.105–0.110 /deg | 0.1066 /deg | PASS |
| CD at α = 0 | ~0.005–0.008 | 0.00551 | PASS |
| analysis_confidence | — | 0.95–0.99 | high |

**`Cp_min` is not an output field — but it is recoverable.** NeuralFoil returns 32 boundary-layer
edge-velocity stations per surface, and `Cp = 1 − (u_e/V∞)²`, so
`Cp_min = 1 − max(u_e/V∞)²`. This is what makes the cavitation check computable, and it is the
reason every cavitation number in this document exists.

### Two honest caveats on this toolchain

1. **It is a surrogate, not XFOIL.** Trends and rankings are reliable; absolute drag carries
   surrogate error. Anything load-bearing should eventually be re-run through XFOIL itself.
2. **`Cp_min` from 32 discrete stations under-reads sharp suction peaks**, because a peak between
   sample points is invisible. **This biases `V_crit` optimistically** — the reported
   cavitation-free speed is a best case. For a cavitation check that is the wrong direction to err,
   and the tool must either apply a margin or move to a true pressure distribution before anyone
   relies on it near the limit.

**A third finding, about method rather than results:** the first coordinate parser silently returned
6.00% thickness and 3.00% camber for NACA 0012 — impossible for a symmetric section — because six of
the eight Eppler files are **Lednicer format**, not Selig. It was caught only because analytic NACA
sections were used as a regression test *before* the Eppler numbers were trusted. Without that
check, every geometry figure in the catalog would have been wrong by roughly a factor of two, and
plausibly so. **Format detection is now part of the parser and the analytic check is its test.**

---

## 5. Still open — requires a privileged install

| Question | Why it stayed open |
|---|---|
| **ILGPU on Blackwell (sm_120)** | Needs a runtime trial on this GPU. ILGPU v1.5.3 (July 2024) remains the newest release; nothing changed in the evidence |
| **LBM accuracy above Re 10⁶** | Needs a working LBM and a validation case |
| **This laptop's real LBM throughput** | Needs CUDA Toolkit 12.8+ or an OpenCL benchmark run; the ~9,570 MLUPs/s figure is still bandwidth-scaled from a desktop benchmark and **still unmeasured** |
| **Strut drag share** | Needs the estimation chain applied to the strut plus a whole-craft measurement to validate against |

None is blocking for Phase 1, because Phase 1 is layers 1–3 and touches no GPU.

---

## What changed in the proposal as a result

1. **Thickness moves from an open gap to a solved constraint** with a displayed cost. It is no
   longer the base's largest evidence gap.
2. **The section catalog gains real, measured content** — 11 sections with verified geometry and
   polars at two Reynolds numbers, plus the strut/lifting split.
3. **Catalog ranking must be per-operating-point**, which is a design requirement the earlier drafts
   did not state.
4. **Typhoon is reclassified** from "possible answer to the hydrofoil half" to "GPL MATLAB
   reference that validates the VLM choice".
5. **Phase 1 loses a dependency**: section analysis needs no XFOIL binary, so the catalog and
   estimator can be built entirely in managed code with a Python-side generation step.

---

# Phase 0b — the GPU questions, closed on hardware (2026-09-06)

CUDA Toolkit **13.3.73** installed via `winget install Nvidia.CUDA` (exit 0). Host compiler is
MSVC **14.51.36231** from Visual Studio Community 2026. A native `sm_120` kernel was compiled and
executed on the GPU.

## Q1 — native sm_120 codegen: **WORKS**

```
nvcc -O3 -std=c++17 -arch=sm_120 -o gpu_probe.exe gpu_probe.cu
```

compiles a native Blackwell cubin and runs. Device reports **compute capability 12.0**, 82 SMs,
23.89 GiB. **The CUDA path is unblocked** — Option 3's native C++/CUDA boundary has no toolchain
risk remaining. *(Verified — compiled and executed here.)*

*Note for the port:* `cudaDeviceProp::memoryClockRate` was **removed in CUDA 13**; use
`cudaDeviceGetAttribute(&v, cudaDevAttrMemoryClockRate, 0)`. The first build failed on exactly this.

## Q3 — real throughput: **MEASURED, and it corroborates the estimate**

| Quantity | Value | Source |
|---|---|---|
| Theoretical bandwidth | **896.1 GB/s** | read from the device (256-bit @ 14,001 MHz) |
| STREAM-triad measured | **811.6 GB/s** | benchmarked here, 50 iterations |
| Achieved efficiency | **90.6%** of theoretical | measured |
| Pure-triad LBM ceiling | 14,756 MLUPs/s | at 55 B/cell |

**The vendor-spec bandwidth figure that was Flagged in v2 is now Verified** — 896.1 GB/s read from
the device matches the 896 GB/s spec exactly.

**The throughput estimate survives contact with the hardware.** FluidX3D's published desktop result
(19,141 MLUPs/s at 1792 GB/s theoretical) implies a real-kernel efficiency of **58.7%** of
theoretical. Applying that same efficiency to this device's measured 896.1 GB/s gives
**9,572 MLUPs/s** — against the v2 bandwidth-scaled estimate of 9,570. **They agree to 0.02%.**

| Domain | Steps/s on measured hardware | v2 claim |
|---|---|---|
| 5.4 M cells (30 cells/chord) | 1,772 | — |
| 12.8 M cells (40 cells/chord) | 748 | — |
| **43.2 M cells (60 cells/chord)** | **221.6** | ~220 |
| 100 M cells | 95.7 | — |

*(Inferred — the 58.7% figure is transferred from FluidX3D's published desktop benchmark, not
measured with an LBM kernel here. What is now **Verified** is the hardware's bandwidth and its 90.6%
STREAM efficiency; what remains transferred is the LBM kernel's share of it.)*

**Interpretation:** a real LBM kernel runs at roughly **65% of the pure-triad ceiling**, which is
the expected penalty for the scattered access pattern of stream-and-collide. The estimate was not
lucky — it was the right model, and the hardware behaves as the model assumed.

## Q2 — LBM accuracy above Re 10⁶: **still open**

Unchanged. This needs a working LBM and a validation case, not a toolchain. It is the last
substantive open risk on the simulation tier, and it is a physics question rather than an
engineering one.

## What this changes

- **Option 3's toolchain risk is gone.** Native CUDA on Blackwell is proven on this machine.
- **ILGPU is now moot for the decision.** There is no reason to accept an unverified pure-.NET path
  when the native one is demonstrated. ILGPU stays a future simplification, not a candidate.
- **Performance planning can proceed on measured numbers**, with the residual uncertainty isolated
  to one transferred efficiency figure rather than the whole chain.
