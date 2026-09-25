---
id: kb-cfd-estimation-methods
title: "Pre-Simulation Estimation Methods"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [estimation, lifting-line, helmbold, ittc, cavitation, xfoil, algorithms]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
  - { to: kb-cfd-foil-sections, rel: depends-on }
  - { to: glossary-cfd-hydrofoil, rel: uses-term }
review-by: 2026-12-04
summary: >-
  The closed-form chain that estimates L/D, Cl/Cd and cavitation margin for a 3D hydrofoil before
  any simulation runs — section polars, Helmbold lift slope, lifting-line induced drag, ITTC skin
  friction with a Hoerner form factor, and the incipient-cavitation critical speed — with every
  formula sourced and the whole chain executed against real water-sports geometry.
---

# Pre-simulation estimation

Every step below is closed-form and runs in **microseconds**. The whole chain is what lets a design
tool answer "what is the L/D of this foil?" while the user drags a slider, with simulation reserved
for what the chain cannot see.

## The chain

### 1. Section data — `Cl`, `Cd`, `Cm`, `Cp_min` at the operating Reynolds number

Source: XFOIL, or precomputed polars from the catalog. XFOIL is an **inviscid linear-vorticity panel
method** coupled to a **two-equation lagged-dissipation integral boundary layer**, with an
**e^N (typically e⁹) amplification formulation** locating transition. *(Verified — Drela)*

It is "especially suitable for rapid analysis of low Reynolds number airfoil flows with transitional
separation bubbles". *(Verified)* Its stated limit matters: the e^N method is only valid where
**2D Tollmien-Schlichting linear instability is the dominant transition mechanism** *(Verified)* —
so it does not cover crossflow transition, roughness-forced transition, or a fouled foil.

**`Cp_min` is the value to capture and the one most databases discard.** It is the sole input to the
cavitation check in step 6.

### 2. Three-dimensional lift-curve slope — Helmbold

For a finite unswept wing in incompressible flow:

```
CL_alpha = 2*pi*AR / (2 + sqrt(AR^2 + 4))            [per radian]
```

Helmbold (1942). *(Verified)* This form is preferred over the classical lifting-line correction
because it **remains valid at low aspect ratio**, and water-sports foils run from AR 4 to AR 12 —
straddling exactly the region where the classical formula degrades.

### 3. Induced drag — lifting line

```
CD_i = CL^2 / (pi * e * AR)
```

where `e` is the span efficiency factor. Oswald efficiency is typically **0.7–0.85** for
conventional moderate-aspect wings; an elliptical distribution gives `e = 1`. *(Verified)*

Induced drag is the dominant term at take-off and the reason aspect ratio governs foiling
performance. Our run below puts it at **77% of total drag** for a surf foil at 7 kn.

### 4. Skin friction — ITTC 1957 correlation line

```
Cf = 0.075 / (log10(Re) - 2)^2
```

The ITTC 1957 model-ship correlation line — a variation of the Kármán friction law adopted by the
International Towing Tank Conference, with the constant rounded from 2.03 to 2.0. *(Verified)*
Using the marine standard rather than a generic flat-plate formula keeps this consistent with the
ITTC fluid properties already in `data-and-constants.md`.

### 5. Form factor — Hoerner

```
(1 + k) = 1 + 2*(t/c) + 60*(t/c)^4
CD_0    = (1 + k) * Cf * (S_wet / S_ref)
```

with `S_wet/S_ref ≈ 2.06` for a thin wing. *(Flagged — the Hoerner form-factor expression is
standard in aircraft and marine drag estimation and is used here as such, but was not read from
Hoerner's own text in this research.)*

### 6. Cavitation margin — the critical speed rule

Cavitation number at depth `h`:

```
sigma = (p0 - pv) / (0.5 * rho * V^2),      p0 = p_atm + rho*g*h
```

Incipient cavitation occurs when the section's minimum pressure coefficient reaches the available
cavitation number: **`sigma_i = -Cp_min`**. *(Verified — IHS)*

The IHS gives the practitioner shortcut for a foil near the surface:

```
V_crit = 14 / sqrt(sigma_i)     [m/s]
```

**This was verified by derivation rather than accepted.** Substituting ITTC seawater at 15 °C
(`rho = 1026.0210`, `pv = 1670.9 Pa`) and `p_atm = 101325 Pa`:

```
sqrt((101325 - 1670.9) / (0.5 * 1026.0210)) = 13.94
```

which reproduces the constant 14. **However, the same IHS passage advises taking `pv = 17000 Pa`
for salt water "to be conservative", and that value does not reproduce the constant — it gives
12.82.** ITTC's primary value for seawater at 15 °C is **1670.9 Pa**, roughly a tenth of 17000.
*(Flagged — the source is internally inconsistent. Use the ITTC value; treat 17000 Pa as either a
deliberate safety margin or an error, and never as a physical property.)*

Depth extends the margin, mildly: at `h = 1.0 m` the constant rises from 13.94 to **14.62**.

### 7. Assemble

```
CD  = CD_0 + CD_i
L/D = CL / CD
```

## The chain executed — real water-sports geometry

Rider plus gear **95 kg**, ITTC seawater at 15 °C, `t/c = 0.11`, `e = 0.85`, foil depth 0.45 m.
Geometry per discipline from `watersports-design-practice.md`.

| Discipline | Area | AR | Span | Chord | Speed | Re | CL | α_eff | CD₀ | CD_i | **L/D** | σ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Surf foiling | 1800 cm² | 5.0 | 95 cm | 19.0 cm | 7 kn | 574,556 | 0.778 | 10.5° | .0134 | .0454 | **13.2** | 15.7 |
| | | | | | 10 kn | 820,795 | 0.381 | 5.1° | .0124 | .0109 | **16.4** | 7.7 |
| | | | | | 13 kn | 1,067,033 | 0.226 | 3.0° | .0117 | .0038 | **14.5** | 4.5 |
| Wing foiling | 1400 cm² | 7.0 | 99 cm | 14.1 cm | 10 kn | 611,784 | 0.490 | 5.9° | .0132 | .0129 | **18.8** | 7.7 |
| | | | | | 15 kn | 917,676 | 0.218 | 2.6° | .0121 | .0025 | **14.9** | 3.4 |
| | | | | | 20 kn | 1,223,568 | 0.123 | 1.5° | .0114 | .0008 | **10.1** | 1.9 |
| SUP / downwind | 1100 cm² | 10.5 | 107 cm | 10.2 cm | 10 kn | 442,777 | 0.624 | 6.9° | .0143 | .0139 | **22.2** | 7.7 |
| | | | | | 14 kn | 619,888 | 0.318 | 3.5° | .0132 | .0036 | **18.9** | 3.9 |
| | | | | | 18 kn | 796,998 | 0.193 | 2.1° | .0125 | .0013 | **14.0** | 2.4 |
| Windsurf / race | 800 cm² | 12.0 | 98 cm | 8.2 cm | 16 kn | 565,142 | 0.335 | 3.6° | .0135 | .0035 | **19.7** | 3.0 |
| | | | | | 22 kn | 777,070 | 0.177 | 1.9° | .0125 | .0010 | **13.1** | 1.6 |
| | | | | | 28 kn | 988,998 | 0.109 | 1.2° | .0119 | .0004 | **8.9** | 1.0 |

### What this output demonstrates

- **The geometry is right.** Spans land at 95–107 cm and chords at 8–19 cm, which match real
  production foils. The estimator was not tuned to produce that — it falls out of the area and
  aspect ratio.
- **The physics behaves.** Induced drag is **77%** of total drag for the surf foil at 7 kn and
  **3%** for the race foil at 28 kn. That crossover from induced-dominated to friction-dominated
  *is* the reason aspect ratio matters for take-off and section drag matters for top speed.
- **Peak L/D sits mid-range in each discipline**, falling at both ends — at low speed from induced
  drag, at high speed because a fixed weight on a fixed area drives `CL` down while `CD₀` stays put.
  Every foil is over-winged at its top speed.
- **Cavitation is not a water-sports problem except at race speed.** `σ` stays above 3 everywhere
  until 22 kn and only reaches **1.0 at 28 kn**. Since a well-behaved section has `σ_i` of roughly
  0.5–1.0, cavitation simply does not bind below about 25 kn. It can be a **check**, not a driver.
- **Take-off asks more of the section than the design point does.** The surf foil needs `CL = 0.78`
  at 7 kn, above the `0–0.6` band the IHS quotes as typical. That is a real finding: it explains
  high-camber low-speed sections directly.

## What this estimate deliberately does not include

**This is a wing-only estimate.** The strut and fuselage are excluded, and in a real foil the strut
is a substantial fraction of total drag. Quoted L/D therefore **overstates whole-craft L/D**, and
the tool must say so at the point of display rather than in documentation. Adding a strut drag
term is a known, bounded extension: the strut is itself a low-aspect surface-piercing foil and the
same chain applies to it.

Also absent: free-surface lift loss with shallow submergence, spray drag, junction interference at
the wing-strut-fuselage intersection, unsteady effects during pumping, and any 3D stall behaviour.
Each of these is a reason the simulation tier exists.

## Consequences for the architecture

1. **The estimator is the product's inner loop**, not a preliminary. Microsecond cost means live
   response to a dragged slider.
2. **It is exactly testable.** Every step is a published closed form, so each gets a unit test
   against a hand-worked value — Helmbold at AR→∞ must approach 2π, `CD_i` must match the elliptical
   result at `e = 1`, ITTC `Cf` must match published table values.
3. **It defines the validity envelope the tool must enforce.** Attached flow, small α, high Re. The
   surf-foil take-off row at α_eff = 10.5° is already near the edge of linear behaviour, and the
   tool should say so rather than print a confident number.
4. **It generates the training corpus** for any future surrogate, and the comparison baseline for
   the simulation tier. When LBM and the estimator disagree, that disagreement is the finding.
