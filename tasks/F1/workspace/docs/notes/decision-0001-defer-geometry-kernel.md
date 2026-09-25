---
id: decision-0001-geometry-kernel
title: "Defer OCCT; Take the Permissive Geometry Path"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [licensing, geometry, occt, rhino3dm, stepcode, step-export]
links:
  - { to: kb-cad-ux-geometry, rel: depends-on }
  - { to: kb-fabrication-interop, rel: depends-on }
review-by: 2027-03-06
summary: >-
  OCCT is deferred and probably permanently avoidable. LGPL-2.1 section 6 obligations are the taint
  the user wants to escape, and a fully permissive path exists — rhino3dm under MIT for NURBS, and
  STEPcode under BSD (or a bounded own implementation) for STEP export, which OpenVSP already proves
  works for exactly our one surface type.
---

# Decision — defer OCCT, take the permissive path

**Date:** 2026-09-06 · **Driver:** the user wants to avoid LGPL-style licensing entirely, including
for a non-commercial project, on grounds of "taint" rather than commercial necessity.

## What OCCT would actually require

OCCT 6.7.0 and later are under **LGPL-2.1 with the Open CASCADE Exception 1.0**. The exception is
narrower than it sounds: it permits *object code of a work that uses the Library to incorporate
material from a Library header file*, distributed under terms of your choice. It does **not** lift
the linking obligations.

Under **LGPL section 6** an application linking OCCT must:

- carry a notice in an About box or documentation, with the LGPL text accessible to the user;
- **make the OCCT sources used by the application available to its users**; and
- **ensure the user can run the application against a modified version of OCCT** (i.e. relinking must
  be possible).

*(Verified — Open CASCADE licensing pages and the SPDX entry for OCCT-exception-1.0.)*

**That third obligation is the real cost.** It shapes how the application is built and shipped, not
just what is written in a README. It is exactly the entanglement the user asked to avoid, and it
applies regardless of whether the project is sold.

## The permissive alternatives, and they are good

| Component | Library | Licence | What it gives |
|---|---|---|---|
| NURBS curves and surfaces, B-Reps, meshes, extrusions, SubDs | **rhino3dm** (McNeel, `mcneel/rhino3dm`) | **MIT** | .NET bindings via NuGet on Windows/macOS/Linux. The openNURBS grant is MIT verbatim — *"free of charge… without restriction, including… to sublicense and/or sell"* — and McNeel state that **commercial use is encouraged** |
| STEP AP203/AP242 read and write | **STEPcode** | **BSD** | EXPRESS schema parser, SDAI classes, Part 21 read/write. Used by BRL-CAD, SCView, and **OpenVSP** |

*(Both Verified.)*

**The decisive precedent:** *OpenVSP uses STEPcode to write AP203 files that currently contain only
`B_SPLINE_SURFACE_WITH_KNOTS` entities.* *(Verified)*

That is **precisely our case**. OpenVSP is a parametric aircraft-geometry tool emitting lofted
B-spline surfaces to STEP, permissively licensed, and it needs no B-Rep kernel to do it.

## Why we may not need a kernel at all

A geometry kernel earns its keep on **booleans, filleting and topological repair**. Walk our actual
requirements:

| Requirement | Needs a kernel? |
|---|---|
| Loft stations into a surface | **No** — we generate it from our own curves |
| Evaluate the surface for meshing, area, wetted area | **No** — our own maths |
| Export a mesh (STL/3MF) for printing and `snappyHexMesh` | **No** |
| Export an exact surface as STEP for CAM | **No** — one entity type, and OpenVSP proves it |
| **Subtract the wing from a mold block** | **Yes** — but `kb-fabrication-interop` already
  concluded **"export STEP and stop"**; the mold is made in a CAM/CAD system |
| Import an arbitrary third-party B-Rep | **Yes** — but see below, this is now out of scope |

**Every remaining requirement is met without a B-Rep kernel.** The two that need one were already
scoped out on independent grounds — molds belong in CAM, and import is now our own format.

## Decision

1. **Defer OCCT indefinitely.** Not "not yet" — *probably never*, on this scope.
2. **Prefer own implementation for the geometry we generate.** Lofting, evaluation, curvature and
   tessellation are our own maths over our own model, and writing them keeps the model honest.
3. **Take rhino3dm (MIT) if and when NURBS surface maths gets hard**, or if 3DM interchange with
   Rhino becomes valuable. It is a drop-in, permissive, .NET-native option with no obligations.
4. **STEP export: STEPcode (BSD) or a bounded own writer.** Emitting `B_SPLINE_SURFACE_WITH_KNOTS`
   in a Part 21 file is a serialisation task with a published schema and a working precedent, not a
   kernel problem. **Prefer our own writer** if it stays under a few hundred lines; fall back to
   STEPcode otherwise.
5. **Revisit only if** mold-block generation or arbitrary B-Rep import re-enters scope. Both are
   currently out, and both have non-kernel workarounds.

## Consequence for the CAD proposal

The `cad-modelling-experience` proposal listed OCCT as a "buy" layer with the note that it was
deferrable. **That is now a decision rather than an option**, and the build/buy table changes: the
kernel row moves from *buy* to *not required*, and STEP export moves from *needs OCCT* to *own
writer or STEPcode*.

## Residual risk

- **rhino3dm cannot read or write STEP or IGES** — only 3DM. *(Verified.)* So it is a geometry
  library, not an interchange one; STEP still needs STEPcode or our own writer.
- **Our own STEP writer is unvalidated until a CAM system opens the file.** The acceptance test is
  not "it writes a file" but **"Fusion/Mastercam opens it and the surface is smooth"**.
- **We take on the maths we would have bought.** Lofting a fair surface through stations with
  controlled continuity is real work, and the curvature-comb requirement exists precisely because it
  can go subtly wrong.
