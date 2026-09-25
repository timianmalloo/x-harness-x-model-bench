---
id: kb-cfd-watersports-practice
title: "Water-Sports Hydrofoil Design Practice and Geometry Catalog"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [design-practice, aspect-ratio, geometry, surf-foil, downwind, wing-foil, windsurf]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
  - { to: kb-cfd-estimation-methods, rel: depends-on }
  - { to: glossary-cfd-hydrofoil, rel: uses-term }
review-by: 2026-12-04
summary: >-
  Design practice and a geometry catalog for surf, SUP/downwind, wing and windsurf/race foiling —
  aspect-ratio bands with the formula and its measurement ambiguity, planform and thickness
  guidance, stabiliser sizing, and the low-speed-lift versus glide trade-off that separates the
  disciplines.
---

# Water-sports hydrofoil design practice

## The one governing trade-off

Every discipline in this domain is a different answer to the same question:

> **Low-speed lift versus glide efficiency.** A larger area reduces the speed needed for take-off,
> which is what makes a downwind paddle-up possible at all — but the extra lift comes with extra
> drag, which cuts glide. *(Verified — practitioner sources)*

Aspect ratio is the lever:

- **Low AR** — wider, shorter. Strong low-speed lift, early take-off, forgiving when slowing,
  turns tightly. Shorter glide, more drag.
- **High AR** — longer, narrower. Long, relaxed pump cycles, very high efficiency, excellent glide.
  Demands precise control and pumping technique to hold lift.

*(Verified — consistent across multiple independent practitioner sources)*

Riders progress toward higher aspect ratios once take-offs are consistent, at which point efficiency
becomes worth more than lift stability. **This progression is a product requirement, not trivia:**
a design tool for this domain is used to move along that axis, so aspect ratio must be a first-class
input with immediate feedback, which the estimator provides.

## Aspect ratio — definition, and a real measurement problem

```
AR = span^2 / area
```

Worked example: a wing of **90 cm span and 1200 cm² area** gives `(90 × 90) / 1200 = 6.75`.
*(Verified — with the worked example given at source)*

**Bands.** Two independent practitioner sources give overlapping but non-identical conventions:

| Band | Source A | Source B |
|---|---|---|
| Low | up to ~6.0 | 3.5 – 6 |
| Mid | ~6.0 – 8.5 | 6 – 8.5 |
| High | ~8.5 – 10 | 8.5 – 14 |
| Super high | from ~10 | (not distinguished) |

*(Verified that both conventions exist; Flagged that neither is authoritative.)*

**The measurement caveat matters more than the bands.** Manufacturers use varying calculation
methods, so published aspect ratios **are not comparable across brands** — the ambiguity is whether
*area* is projected, developed, or planform, and whether span is tip-to-tip or along a curved
(anhedral) wing. *(Verified)*

*Design implication:* the tool must compute aspect ratio **from its own geometry** under a stated
definition, and must display that definition. Ingesting a manufacturer's published AR as truth
would import an unknown convention — the classic silent unit-class error.

## Geometry catalog by discipline

Areas and aspect ratios below are assembled from practitioner sources; they are **representative
bands, not a standard**. *(Inferred — corroborated across several independent retailer and magazine
sources, but no authoritative dataset exists.)* Span and chord are **derived** from area and AR by
the estimator, not independently sourced.

| Discipline | Front-wing area | Aspect ratio | Derived span | Derived mean chord | Speed range | Character |
|---|---|---|---|---|---|---|
| **Surf foiling** | 1500–2000 cm² | 4–6 | ~95 cm | ~19 cm | 5–13 kn | Early lift, tight turning, forgiving. Wave-riding wings trend to the low end of area for responsiveness |
| **Wing foiling** (freeride) | 1200–1500 cm² | 6–8 | ~99 cm | ~14 cm | 8–20 kn | The broad middle; the largest product category |
| **SUP / downwind** | 900–1200 cm² | 9–12 | ~107 cm | ~10 cm | 8–18 kn | Highest efficiency demand. Long relaxed pump cycles; glide is the whole point |
| **Windsurf / race** | 700–900 cm² | 10–14 | ~98 cm | ~8 cm | 14–30 kn | Speed-oriented; the only discipline where cavitation becomes a live constraint |

**Beginner guidance** is consistent across sources: front-wing area **above 1500 cm²** with aspect
ratio **5–6**, because wider, thicker wings give early lift. High-aspect wings typically carry
**less** area, in the 700–1400 cm² range. *(Verified)*

**Note the spans barely change.** Across a 2.5× range of area and a 3× range of aspect ratio, span
stays near 95–107 cm. That is not a coincidence — it is a practical constraint (a wider foil hits
the water in turns and is unwieldy to transport), and it means **area and aspect ratio are the real
design variables while span is nearly fixed**. A design tool should let the user drive area and AR
and show span as a consequence, not the reverse.

## Sections, thickness and camber in this domain

| Parameter | Practice | Confidence |
|---|---|---|
| Thickness ratio | 10–12% typical; 12–15% more durable and delays stall; 8–10% lower drag but structurally marginal | Flagged — single secondary source with demonstrably garbled tables |
| Maximum practical | ~20% t/c | Flagged |
| Camber | High camber gives strong low-speed lift and pumping efficiency, but a **negative pitching moment** that reads as instability at speed | Flagged — practitioner consensus |
| Profile family | Symmetrical or low-camber profiles favoured for stability and reduced cavitation risk | Flagged — from a source whose adjacent tables were unusable |

The thickness question is genuinely **under-sourced**, and it is load-bearing for a design tool. The
sources that quantify it are retailer blogs; the sources that are authoritative (Eppler's book, the
IHS compilation) discuss pressure distribution rather than thickness bands. **This is the largest
evidence gap in the base** and is recorded in `open-questions.md`.

## Planform, taper, anhedral

- **Taper ratio** = tip chord / root chord. 1.0 is constant-chord; 0.5 is a tip half the root; 0.0
  is triangular. Tapered wings reduce induced drag. *(Verified — general wing design)*
- **Anhedral/dihedral** in the 0–30° range is the general wing-design span; water-sports front
  wings characteristically use **anhedral** (tips below root) for roll stability and to keep tips
  submerged in turns. *(Inferred — the anhedral preference is evident in the product category; the
  0–30° range is from general wing-design sources, not hydrofoil-specific)*
- **Sweep** — swept-back designs are described as improving high-speed stability, but no source
  found quantifies it for this application. *(Flagged)*
- Thickness may taper independently of chord, and linearly varying thickness permits linear spars.
  *(Verified — general)*

## Stabiliser (tail wing) and pitch stability

- The rear wing should be roughly **20–30% of front wing size** for balanced pitch stability.
  *(Flagged — single secondary source)*
- Larger stabilisers give calmer pitch, slower turning, and more drag; smaller give responsive,
  tighter-radius turning. *(Verified — consistent across sources)*
- **Fuselage length is the static-margin lever:** longer fuselages give more pitch stability,
  shorter enable tighter turns. *(Verified)*
- A pitch-stable foil holds an angle of attack and returns to it after a perturbation. *(Verified)*

**This is a two-surface problem, and that is architecturally significant.** Front wing and
stabiliser interact through downwash and the fuselage moment arm; neither can be designed alone.
Any geometry model that cannot express *"front wing, stabiliser, fuselage length, and the incidence
difference between them"* cannot represent the actual design question — which is precisely why the
parametric grammar in `parametric-geometry.md` is multi-surface from the start.

## Discipline notes

**Surf foiling** — lowest speeds, so the highest `CL` demand and the strongest case for camber. Our
estimator puts take-off at `CL ≈ 0.78`, above the typical `0–0.6` section design band.

**SUP / downwind** — the efficiency extreme. Take-off is by paddling, so low-speed lift must be
sufficient *and* glide must be excellent; these conflict, which is why this discipline drove the
move to AR 9–12. Highest L/D in the estimator (22.2 at 10 kn).

**Wing foiling** — the broadest range, and the category where most product variation sits.

**Windsurf / race** — the only discipline where the estimator shows `σ` approaching 1.0. Cavitation
becomes a design constraint here and nowhere else in this domain.
