---
id: kb-cfd-parametric-geometry
title: "Parametric Multi-Surface Foil Geometry"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [parametric, cst, kulfan, geometry, grammar, loft, openvsp, avl]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
  - { to: kb-cfd-foil-sections, rel: depends-on }
  - { to: glossary-cfd-hydrofoil, rel: uses-term }
review-by: 2026-12-04
summary: >-
  How to describe a complete 3D hydrofoil assembly parametrically — CST section parameterisation,
  a four-concept station-and-loft grammar covering front wing, stabiliser and strut alike, and a
  two-layer split between a small generative design vector and explicit geometry.
---

# Parametric multi-surface foil geometry

## Section parameterisation: CST (Kulfan)

The **Class-Shape Transformation** represents an airfoil as a *class function* times a *shape
function*:

```
class:  C(psi) = psi^N1 * (1 - psi)^N2
```

with `psi` the non-dimensional chordwise coordinate. **`N1 = 0.5, N2 = 1.0` gives the airfoil
class** — rounded leading edge, sharp trailing edge. The shape function is a polynomial (Bernstein
basis) whose coefficients are the **CST coefficients**, and it carries the individual shape.
*(Verified — Kulfan; NASA OpenVSP documentation)*

Three properties make this the right choice:

1. **Round leading edge and sharp trailing edge come from the class function**, so every shape in
   the family is automatically a valid airfoil. A parameterisation that can emit invalid geometry
   pushes validation downstream into the solver, where failures are expensive and obscure.
2. **Order is adjustable.** More Bernstein terms give finer control; the design vector length is a
   dial, not a fixed cost.
3. **It unifies the alternatives.** NACA 4-series airfoils, the CST parameterisation and the PARSEC
   method **are all exactly equivalent to Bézier curves**, and four of Kulfan's seven standard shape
   classes — airfoils among them — have exact Bézier representations. *(Verified)*

That last point resolves the "which parameterisation?" question rather than answering it: CST,
PARSEC, NACA 4-digit and Bézier are the *same underlying object* in different clothes. **Pick CST
because its class/shape split is the most direct, and treat the others as conversions**, not as
competing systems requiring separate code paths.

**Practical consequence:** a section is either a *catalog reference* (`E817`, with provenance) or a
*CST vector*. A catalog section can be fitted to CST coefficients to enter the continuous design
space; a CST vector can always be evaluated to coordinates for XFOIL. One conversion each way, and
the rest of the system only ever sees coordinates.

## The 3D grammar: four concepts, nothing more

A complete hydrofoil assembly needs exactly four ideas. This is the whole grammar.

| Concept | Definition |
|---|---|
| **Assembly** | An ordered set of surfaces, plus the fluid and the operating point |
| **Surface** | An ordered list of stations, a spanwise axis, a loft rule, and an optional mirror |
| **Station** | A point on the span carrying: position `(x, y, z)`, chord, incidence, and a section |
| **Loft rule** | How geometry interpolates between adjacent stations — linear or spline |

Everything in the domain falls out of these:

- A **front wing** is a surface with a spanwise `y` axis, anhedral expressed as `z` varying with
  `y`, taper as chord varying with `y`, and washout as incidence varying with `y`.
- A **stabiliser** is the same thing at a different `x`, with its own incidence — and the
  **difference between front-wing and stabiliser incidence is decalage**, which falls out of the
  representation rather than needing a special field.
- A **strut** is a surface whose span axis is `z` instead of `y`. No new concept; a surface-piercing
  strut is just one whose top station is above the waterline.
- A **fuselage** is the `x` separation between surfaces — a consequence of station positions, not a
  stored quantity.

This mirrors how the established tools work, which is corroboration rather than coincidence: OpenVSP
builds wings from *"stacked, parallel sections"* and explicitly notes that tails, fins, strakes and
blends *"may be created from a wing"* — the same object serving every role. Its cross-sections use
linear, spline and Bézier curve types, and it converts to **AVL**, which has been a compact
station-based text format for decades. *(Verified — NASA OpenVSP)*

### Sketch of the concrete syntax

```
assembly "Downwind 1100" {
  fluid    seawater @ 15C
  operate  speed 12kn  mass 95kg  depth 0.45m

  surface front {
    axis    y
    mirror  true                        # define one half, mirror it
    loft    spline
    station y=0.000  chord=0.130  inc=+1.5  section=E817
    station y=0.300  chord=0.108  inc=+1.0  section=E817
    station y=0.535  chord=0.045  inc=+0.2  section=E818   z=-0.075
  }

  surface stab {
    axis    y
    mirror  true
    loft    linear
    station y=0.000  chord=0.075  inc=-1.0  section=naca:0010  x=0.620
    station y=0.180  chord=0.040  inc=-1.0  section=naca:0010  x=0.620
  }

  surface strut {
    axis    z                            # the only difference from a wing
    loft    linear
    station z=0.000  chord=0.140  inc=0  section=naca:0012
    station z=0.750  chord=0.120  inc=0  section=naca:0012
  }
}
```

Readable without a manual, diffable in git, and every line is one station. The grain is explicit:
**one row is exactly one station on one surface.**

## Two layers: generative parameters above, explicit stations below

The grammar above is *explicit* — full control, verbose. Designers and optimisers do not want to
move eleven numbers to try a higher aspect ratio. So put a **generative layer** above it:

```
surface front from planform {
  area      1100cm2
  aspect    10.5
  taper     0.35
  sweep     4deg
  anhedral  8deg
  washout   1.3deg
  section   E817
}
```

which **emits** the explicit stations. Two layers, one direction of flow:

- **The generative layer is the design vector** — roughly 6–8 numbers per surface plus the CST
  coefficients. That is what an optimiser searches and what a surrogate model would be trained on.
  Small enough to explore, expressive enough to matter.
- **The explicit layer is the geometry of record.** Everything downstream — estimator, mesher,
  solver, export — reads only explicit stations and never needs to know whether a human or a
  generator wrote them.
- **Generation is one-way.** A generated surface can be "burst" to explicit stations for hand
  editing, but explicit stations are never back-fitted to planform parameters. Two-way sync between
  a parametric description and its output is a well-known source of silent divergence, and one
  direction removes the whole class.

## Derive, never store

Area, aspect ratio, span, mean chord, wetted area and volume are **all computed from stations**.
None is stored.

This is not fastidiousness. The domain evidence shows manufacturers publish aspect ratios computed
by inconsistent conventions, so the same wing carries different published numbers. If the tool
stored an area alongside the geometry that implies it, the two would drift and there would be no
way to say which was right — the two-definitions-of-one-quantity defect signature. **Computing from
stations under one stated convention is what makes the tool's numbers comparable when the market's
are not.**

The single exception is a **catalog section's coordinate file**, which is stored with provenance
because it is a measurement, not a derivation.

## History and reproducibility

A design session is a sequence of edits, and the interesting question is usually "what changed
between the version that worked and this one?" That argues for treating the assembly as an
**append-only sequence of versions** rather than a mutable record, with each analysis result
referencing the exact assembly version and section revisions that produced it. A stored L/D that
cannot name the geometry it came from is not a result.

## What this enables

1. **Live estimation.** The estimator consumes explicit stations directly — area, AR and chord
   distribution are all it needs.
2. **Meshing for the simulation tier.** Lofted stations give a watertight surface for either an
   immersed-boundary voxelisation or a panel discretisation.
3. **Optimisation.** A small, continuous, always-valid design vector is exactly the input a
   gradient or surrogate method requires.
4. **Interoperability.** AVL export is nearly free given a station model, and STL/STEP export from
   the loft opens the path to CAD and manufacture.

## Open risk

The loft rule between stations is where a simple grammar can silently produce a bad surface —
spline interpolation through sparse stations can introduce curvature reversals that are
hydrodynamically real and visually invisible. *(Inferred — this is a general lofting hazard, not
something measured for this application.)* The mitigation is a curvature check on the generated
surface, surfaced in the UI, rather than trusting the interpolation.
