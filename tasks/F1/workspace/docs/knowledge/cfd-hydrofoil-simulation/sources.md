---
id: kb-cfd-sources
title: "Sources"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [sources, citations, provenance]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
review-by: 2026-12-04
summary: >-
  Full source list with access dates and the specific claim each supports, so every confidence label
  in this knowledge base is traceable to the evidence that produced it.
---

# Sources

All accessed **2026-09-05**.

| # | Title / source | Type | URL | Used for |
|---|---|---|---|---|
| 1 | ITTC 7.5-02-01-03 Rev 02, Fresh Water and Seawater Properties | standard (primary) | https://www.ittc.info/media/9585/75-02-01-03.pdf | All density / viscosity / vapour-pressure values; standard salinity 35.16504 g/kg; IAPWS + TEOS-10 basis. Tables read directly from the PDF |
| 2 | FluidX3D (ProjectPhysX) | primary repo | https://github.com/ProjectPhysX/FluidX3D | 93 and 55 B/cell; 19,141 MLUPs/s desktop RTX 5090; OpenCL not CUDA; no AMR; free-surface VOF+PLIC; Smagorinsky-Lilly; force/torque extraction; non-commercial licence |
| 3 | ILGPU | primary repo + releases | https://github.com/m4rs-mt/ILGPU/releases | v1.5.3 (July 2024) is current; no sm_120/Blackwell mention; NCSA licence; .NET 6.0 / VS2022 toolchain |
| 4 | NVIDIA Blackwell Compatibility Guide | vendor standard | https://docs.nvidia.com/cuda/blackwell-compatibility-guide/ | CUDA 12.8 minimum for native sm_120; PTX forward-compatibility rule |
| 5 | Typhoon (Ghent University) | primary | https://typhoon.ugent.be/ | Static forces/moments; Newton-Raphson equilibrium; eigenvalue stability; open source. Numerical method not documented |
| 6 | SU2 AIAA papers (Stanford ADL) | primary | https://su2code.github.io/documents/SU2_AIAA_SciTech2014.pdf | Compressible RANS core; incompressible/artificial compressibility; level-set free surface; adjoint optimisation focus |
| 7 | Free surface flows around shallowly submerged hydrofoil by OpenFOAM | secondary (peer-reviewed) | https://www.sciencedirect.com/science/article/abs/pii/S0029801815001365 | interFoam applied to submerged hydrofoils |
| 8 | Beyond VoF: alternative OpenFOAM solvers for numerical wave tanks | secondary (peer-reviewed) | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7608737/ | interFoam free-surface wiggles, light-phase acceleration, VOF sub-cycling; VOF resolution and time-step cost |
| 9 | Vortex Lattice Method for sailing yacht foil design vs RANS | secondary (peer-reviewed) | https://link.springer.com/article/10.1007/s12008-025-02378-4 | VLM meshes surfaces only; orders of magnitude faster than RANS; validity limited to small alpha, attached flow, high Re |
| 10 | A new non-linear vortex lattice method | secondary (peer-reviewed) | https://www.sciencedirect.com/science/article/pii/S1000936116300954 | Non-linear VLM at ~1% of CFD execution time |
| 11 | XFLR5 project discussions and analysis guide | secondary (practitioner) | https://sourceforge.net/p/xflr5/discussion/679396/ | VLM/panel methods are linear; stall not represented; XFOIL polar interpolation assumes infinite-wing behaviour; convergence issues |
| 12 | On the ventilation of surface-piercing hydrofoils under steady-state conditions | primary (JFM) | https://arxiv.org/pdf/2503.18015 | FW/PV/FV regimes and stability regions; ventilation onset requires air ingress into separated sub-atmospheric flow; washout via re-entrant jet |
| 13 | Ventilated cavities on a surface-piercing hydrofoil at moderate Froude numbers | primary (JFM) | https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/abs/ventilated-cavities-on-a-surfacepiercing-hydrofoil-at-moderate-froude-numbers/3A3C55533CD1A36BAA53B4AA2102C068 | Froude-number thresholds for tail ventilation; free-surface drawdown of about c/2 |
| 14 | Savitsky method literature (optimum trim, planing prediction) | secondary (peer-reviewed) | https://www.researchgate.net/publication/357321148 | Savitsky 1964 basis; prismatic hulls, deadrise, trim, L/B; ignores lateral wave-making and spray; calm-water steady-state limits |
| 15 | RANS Simulation of Dynamic Trim and Sinkage of a Planing Hull | secondary (peer-reviewed) | https://pubs.sciepub.com/amp/1/1/2/index.html | RANS+VOF with SST k-omega and overset for free trim/sinkage; divergence beyond V/sqrt(L) greater than 2.79 |
| 16 | Physics-informed data-driven near-wall modelling for LBM at high Re | primary (Nature Comms Physics) | https://www.nature.com/articles/s42005-024-01832-1 | Bounce-back mispredicts wall shear on coarse grids at high Re; data-driven near-wall models to friction-Re 1e6 |
| 17 | A wall function approach in lattice Boltzmann method | primary (arXiv) | https://arxiv.org/pdf/2009.04352 | Wall-function bounce-back (WFB); BGK collision operator limits high-Re application |
| 18 | Lattice Boltzmann wall boundary conditions for RANS | primary (arXiv) | https://arxiv.org/pdf/2506.03905 | RANS-coupled LBM wall treatment; cost of resolving wall layers at high Re |
| 19 | Deep neural operators as accurate surrogates for shape optimization | primary (arXiv) | https://arxiv.org/pdf/2302.00807 | DeepONet generalisation; orders-of-magnitude online speedup with little accuracy loss |
| 20 | Airfoil aerodynamic performance prediction using ML and surrogate modeling | secondary (peer-reviewed) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11024608/ | Surrogate accuracy degrades for high-drag samples; training-distribution dependence |
| 21 | NVIDIA GeForce RTX 5090 Laptop GPU specifications | vendor/secondary | https://laptopmedia.com/video-card/nvidia-geforce-rtx-5090-laptop/ | 24 GB GDDR7, 256-bit, 896 GB/s — the bandwidth used to scale the throughput estimate (Flagged: not read from the device) |
| 22 | FoilBoard and community foil tools | secondary (practitioner) | https://github.com/dmitrynizh/foilboard | Band C prior art; FoilBoard real-time-feedback positioning; WingHopper XFLR5 XML export |
| 23 | Kiteboarding hydrofoil design Reynolds discussion | secondary (practitioner) | https://www.boatdesign.net/threads/kiteboarding-hydrofoil-design-for-reynolds-600k-1-5mm.59452/ | Foiling speed bands: racers 22-35 kn (~1e6 Re), free riders 12-22 kn (~6.5e5), surfers 5-12 kn |
| 24 | Local machine probe (nvidia-smi, dotnet --list-sdks, vswhere) | primary (direct measurement) | n/a — this machine, 2026-09-05 | RTX 5090 Laptop GPU, compute cap 12.0, 24463 MiB, driver 591.91, CUDA 13.1 capable; .NET SDK 10.0.303; WindowsDesktop 10.0.11; VS Community 2026 18.7 with MSVC x64; no CUDA Toolkit installed |

## Source-quality note

Findings 1, 4 and 24 rest on **primary** sources (a standard, a vendor compatibility guide, and
direct measurement) and are the most reliable in this base. The performance estimate depends on
source 21, a **secondary vendor-spec aggregator**, which is why the throughput figure is labelled
Inferred and carries an instruction to measure rather than trust it.

---

## v2 sources (accessed 2026-09-05)

| # | Title / source | Type | URL | Used for |
|---|---|---|---|---|
| 25 | International Hydrofoil Society — Hydrofoil, Rudder, and Strut Design Issues | primary (practitioner compilation; Tom Speer, Martin Grimm, Nat Kobitz, Malin Dixon) | https://foils.org/wp-content/uploads/2017/09/Hydrofoil-Rudder-and-Strut-Design-Issues.pdf | The four key section-design problems; rooftop pressure criterion; 66-series preferred over 16-series; Eppler hydrofoil list E817/818/836/837/838/874/904/908; design Cl 0.3 in a 0-0.6 range; four necessary conditions for ventilation; cavitation number definition and worked example; sigma_i = -Cp_min; V_crit = 14/sqrt(sigma_i); strut fences. Text extracted from the PDF with pypdf. See the internal inconsistency recorded in estimation-methods.md |
| 26 | UIUC Airfoil Data Site (M. Selig) | primary (academic database) | https://m-selig.ae.illinois.edu/ads/coord_database.html | ~1,650 sections; Selig coordinate format; families present (Eppler, Wortmann FX, Drela AG/DAE/DAI, Gottingen, Selig S, Althaus AH, NACA) |
| 27 | NASA OpenVSP — Wings and Wing Section API | primary (agency documentation) | https://www.nasa.gov/reference/openvsp-wings/ | Wings built from stacked parallel sections; tails/fins/strakes/blends created from the same wing object; linear/spline/Bezier cross-section curves; AVL export with Sref/Cref/Bref |
| 28 | OpenVSP Ground School — CST Airfoil | primary (agency training material) | https://vspu.larc.nasa.gov/training-content/chapter-1-vspfundamentals/cross-section-details/cst-airfoil/ | CST class function psi^N1(1-psi)^N2; N1=0.5, N2=1 gives round LE / sharp TE; Bernstein shape function and CST coefficients |
| 29 | Creating Exact Bezier Representations of CST Shapes | secondary (peer-reviewed) | https://www.researchgate.net/publication/269047382 | NACA 4-series, CST and PARSEC are all exactly equivalent to Bezier curves; 4 of Kulfan's 7 shape classes have exact Bezier form |
| 30 | Bezier-PARSEC: An optimized aerofoil parameterization for design | secondary (peer-reviewed) | https://www.sciencedirect.com/science/article/abs/pii/S0965997810000529 | PARSEC/Bezier parameterisation lineage |
| 31 | ERAU — Lifting Line and Finite Wing Theory | secondary (open textbook) | https://eaglepubs.erau.edu/introductiontoaerospaceflightvehicles/chapter/lifting-line-theory/ | CD_i = CL^2/(pi e AR); lifting-line formulation; Helmbold (1942) low-AR lift-curve slope |
| 32 | Oswald efficiency number | secondary (reference) | https://en.wikipedia.org/wiki/Oswald_efficiency_number | Oswald efficiency typically 0.7-0.85 for moderate aspect and sweep |
| 33 | ITTC 1957 model-ship correlation line | standard (via secondary) | https://ittc.info/media/2031/75-02-03-011.pdf | Cf = 0.075/(log Re - 2)^2; form factor (1+k); Karman friction law with constant rounded 2.03 to 2.0 |
| 34 | XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils (Drela) | primary (seminal paper) | https://archive.aoe.vt.edu/mason/Mason_f/XFOILman.pdf | Inviscid linear-vorticity panel method; two-equation lagged dissipation integral BL; e^9 transition; suitability for transitional separation bubbles; e^N valid only where 2D Tollmien-Schlichting instability dominates |
| 35 | SURF Magazin — High, Mid and Low Aspect | secondary (practitioner magazine) | https://www.surf-magazin.de/en/wingsurfing/foils/high-mid-and-low-aspect-what-the-aspect-ratio-means-for-foils-and-how-it-is-calculated/ | AR = span^2/area with worked example (90 cm, 1200 cm2 gives 6.75); bands low <=6 / mid 6-8.5 / high 8.5-10 / super-high >=10; manufacturers use varying calculation methods so ratios are not comparable |
| 36 | Unifoil, Phantom and AFS foiling guides | secondary (manufacturer/practitioner) | https://uni-foil.com/blogs/knowledge-base/understanding-aspect-ratio | Low-AR early lift and forgiveness vs high-AR glide and long pump cycles; rider progression toward higher AR; high camber gives low-speed lift and pumping but a destabilising negative pitching moment |
| 37 | Windance / MACkite / Sport in Tribe foil sizing guides | secondary (retailer) | https://www.windance.com/blogs/news/foil-aspect-ratio-everything-you-need-to-know | AR bands 3.5-6 / 6-8.5 / 8.5-14; beginner front wing >1500 cm2 at AR 5-6; high-AR wings 700-1400 cm2; stabiliser behaviour and fuselage length effects |
| 38 | airfoiltools.com (Eppler E817/E818 pages) | secondary (derived database) | http://airfoiltools.com/airfoil/details?airfoil=e818-il | Intended for section geometry and polars. Connection refused during this research — recorded because the failure is itself an argument for vendoring coordinates rather than fetching them |
| 39 | hydrofoiling.org — Hydrofoil Wing Design guide | secondary (blog) | https://www.hydrofoiling.org/hydrofoil-wing-design/ | Source of the 10-12% thickness, 20-30% stabiliser ratio and Re 280k-650k claims. QUALITY WARNING: its discipline table extracted as aspect ratios of 80-120, which are physically impossible. All numbers from this source are Flagged and none is load-bearing without corroboration |
| 40 | Local computation (this session) | primary (direct derivation) | n/a — scratchpad scripts, 2026-09-05 | Verification that V_crit = 14/sqrt(sigma_i) derives from ITTC pv=1670.9 Pa and not the 17000 Pa the same source quotes; the full estimation chain executed across four disciplines; Reynolds envelope; GPU memory and throughput budget |

## v2 source-quality note

The v2 research leaned harder on practitioner sources than v1, because water-sports foil design
practice is not published as a standard — it lives in manufacturer guides, magazines and forum
compilations. That is a real limitation and it shapes the confidence labels: the **physics** here is
Verified from primary sources (ITTC, IHS, Drela, Kulfan, NASA), the **design practice** is mostly
Inferred from corroborating secondary sources, and the **quantitative geometry guidance** is Flagged
wherever a single retailer source is all that exists.

Source 39 was retained rather than dropped specifically so that the quality warning travels with the
claims it produced.

---

## Phase 0 sources (measurement pass, 2026-09-05)

| # | Title / source | Type | URL | Used for |
|---|---|---|---|---|
| 41 | UIUC Airfoil Data Site — coordinate files | primary (data) | https://m-selig.ae.illinois.edu/ads/coord/ | The 11 vendored section coordinate sets. Files stored verbatim in `sections/` with SHA-256 hashes and retrieval date; see `sections/manifest.md` |
| 42 | Typhoon `fLattice_setup2.m` source header | primary (source code) | https://raw.githubusercontent.com/MaritiemUGent/Typhoon/master/fLattice_setup2.m | Verbatim: "This file is part of Tornado", Tomas Melin, copyright 1999/2007, GNU GPL v2 or later. Closes the Typhoon method question |
| 43 | Typhoon repository file listing | primary (GitHub API) | https://api.github.com/repos/MaritiemUGent/Typhoon/git/trees/master | 61 files; `solver10.m`, `setboundary5.m`, `lgwt.m`, `visc_corr.m`, `aeropolar.m` — consistent with a Tornado-derived VLM plus viscous correction. README is effectively empty |
| 44 | NeuralFoil 0.3.3 (Sharpe) | primary (software) | https://pypi.org/project/neuralfoil/ | Section polars. A neural surrogate trained on XFOIL; pure Python/NumPy, no native dependency. Returns CL/CD/CM/Xtr and 32 boundary-layer edge-velocity stations per surface, but **no Cp_min field** |
| 45 | Local computation — Phase 0 (this session) | primary (direct measurement) | n/a — scratchpad `foil.py`, 2026-09-05 | Coordinate parser with Selig/Lednicer detection, validated against analytic NACA truth; measured geometry for all 11 sections; thickness sweep 6–20% t/c at Re 6e5 and 1e6; Eppler set solved head-to-head at CL 0.30; `Cp_min` derived as `1 − max(u_e/V∞)²` |

## Phase 0 method note — and its two caveats

The section results are **computed with a surrogate, not XFOIL**. NeuralFoil was validated against
analytic truth before use (NACA 0012: CL exactly 0 at zero incidence, dCL/dα = 0.1066/deg against a
theoretical 0.1097, CD 0.00551), and reports its own `analysis_confidence` (0.80–0.98 across these
runs). **Trends and rankings are reliable; absolute drag carries surrogate error.**

`Cp_min` is **derived**, not returned: `Cp = 1 − (u_e/V∞)²` over the 32 stations per surface. A
suction peak *between* stations is invisible, so **the reported cavitation-free speed is
optimistic** — the wrong direction to err for a safety-relevant check. Both caveats are recorded in
`phase-0-findings.md` and carried in the proposal.
