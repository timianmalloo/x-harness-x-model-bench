---
id: kb-cfd-foil-sections
title: "Foil Section Catalog and Selection"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [sections, airfoil, eppler, naca, catalog, cavitation, selection]
links:
  - { to: kb-cfd-hydrofoil-simulation, rel: refines }
  - { to: glossary-cfd-hydrofoil, rel: uses-term }
review-by: 2026-12-04
summary: >-
  The 2D section families relevant to water-sports hydrofoils — the Eppler hydrofoil series, the
  NACA 16- and 6-series, and the wider low-Reynolds catalog — with the design criteria that select
  between them, the sources the coordinates come from, and the data model a catalog needs.
---

# Foil section catalog and selection

> **UPDATED by Phase 0 (2026-09-05).** The Eppler set has been **vendored and measured** — see
> [`sections/manifest.md`](sections/manifest.md) for provenance and geometry, and
> [`phase-0-findings.md`](phase-0-findings.md) for computed polars. Two claims below were
> superseded: the thickness guidance is now measured rather than quoted, and the Eppler set is now
> known to split into a **cambered lifting family** and a **symmetric strut family**.

## The design problem, stated by practitioners

The International Hydrofoil Society compilation states **four key problems in subcavitating
hydrofoil section design**, in this order: *(Verified — IHS, Tom Speer)*

1. **Avoid separation** — because separation invites ventilation as well as causing drag.
2. **Avoid cavitation.**
3. **Low drag** — fortunately, what gives a high cavitation speed and avoids separation also
   minimises drag.
4. **Free-surface proximity** modifies the velocity distribution about the foil.

The geometric consequence is specific and directly usable:

> Cavitation begins when the lowest pressure anywhere on the foil drops below vapour pressure, so
> **minimise the maximum velocity — no sharp pressure peaks allowed.** At the same time the
> *average* velocity over the top surface should be as high as possible to produce lift. This drives
> the design toward **long, flat pressure distributions — shaped like a building with a flat
> roof.** *(Verified — IHS)*

That "rooftop" criterion is the single most useful section-selection rule in this domain, and it is
computable: it is a property of the XFOIL pressure distribution, not a matter of taste.

**Typical loading:** `Cl = 0 to 0.6` with a **design `Cl = 0.3`**. *(Verified — IHS)*
Our own estimator (see `estimation-methods.md`) puts a surf foil at `CL ≈ 0.78` at take-off speed —
**above** that band, which is precisely why low-speed foils carry high camber.

## Family A — Eppler hydrofoil sections (the user's stated preference)

Richard Eppler designed sections **specifically as hydrofoils**, using his inverse-design code. The
IHS compilation lists the hydrofoil members explicitly: *(Verified — IHS)*

| Section | Notes |
|---|---|
| **E817** | 10.98% t/c, camber 2.88% far aft at 0.69c. The most commonly cited of the set |

| **E818** | 9.37% t/c. **Best measured cavitation margin of the set** — 42.1 kn vs NACA 4412's 31.4 kn |
| **E874** | 7.90% t/c, the thinnest. Best Eppler section L/D at Re 6e5 |
| **E904** | 9.00% t/c. Best Eppler section L/D at Re 1e6 (63.4) — the ranking is Reynolds-dependent |
| **E908** | 9.00% t/c, camber far aft at 0.66c |
| **E836** | 12.64% t/c, **zero camber — strut family, not a lifting section** |
| **E837** | 16.11% t/c, **zero camber — strut family** |
| **E838** | 18.37% t/c, **zero camber — strut family** |

These are characterised in the hydrofoil literature as **minimum-cavitation, low-drag** sections.
*(Flagged — the characterisation is consistent across secondary sources; the authoritative statement
is Eppler's own book,* Airfoil Design and Data*, which is out of print and was not obtained.)*

**Important caveat on provenance.** Coordinates for E817/E818 are published on
`airfoiltools.com` and the UIUC database. Neither is Eppler's original publication. For a catalog
that claims authority, each section needs a recorded **source and revision**, because
airfoil coordinate sets in circulation differ in point count and trailing-edge treatment, and those
differences change XFOIL results. Treat the coordinate file as data with provenance, not as a
constant.

## Family B — NACA 16-series (the classic marine choice)

The 1-series / 16-series (e.g. `16-012`, `16-510`) was the original propeller-and-hydrofoil family.
`NACA 16-510` was developed for surface-piercing hydrofoils in the 1950s. *(Verified — IHS)*

- **Strength:** a shallow favourable pressure gradient back to **60% chord** — close to the rooftop
  ideal.
- **Weakness, and it is decisive:** a **highly convex pressure recovery**, which is not a good
  characteristic if you want to avoid trailing-edge separation. *(Verified — IHS)*

## Family C — NACA 6-series laminar (what a practitioner actually recommends)

The 6-series (`63-`, `64-`, `65-`, `66-`) was designed for extended laminar runs and produces the
rooftop distribution directly.

> "A comparable 6-series section (say, **66-XXX**) would probably be a better bet than the
> corresponding 16-XXX section." *(Verified — IHS, Tom Speer)*

This is a concrete, citable ranking and the catalog should surface it: **66-series ahead of
16-series for subcavitating hydrofoil use**, on separation grounds.

## Family D — the wider catalog

The **UIUC Airfoil Data Site** holds roughly **1,650 sections** in *Selig format* `.dat` files
(coordinates run from upper-surface trailing edge, around the leading edge, to lower-surface
trailing edge; `#` comment lines are ignored by XFOIL). *(Verified — UIUC)*

| Family | Prefix | Origin / relevance here |
|---|---|---|
| **Eppler** | `E`, `EA`, `EC` | Extensive low-Reynolds designs; includes the hydrofoil set above |
| **Wortmann** | `FX` | High-performance sailplane and turbine sections; well-behaved at our Re |
| **Selig** | `S` | Low-Reynolds high-lift (e.g. `S1223`); relevant to low-speed take-off |
| **Drela** | `AG`, `DAE`, `DAI` | Human-powered aircraft; very low Re, high efficiency |
| **Göttingen** | `GOE` | Large historical collection |
| **Althaus** | `AH` | Sailplane sections |
| **NACA** | `NACA` | 4-digit, 5-digit, 6-series, 16-series |

**NACA 4-digit sections deserve a specific role.** They are defined by **three numbers**
(max camber %, its position in tenths, thickness %) and generated analytically. That makes them the
right **parametric baseline and regression test** for a catalog: any code that ingests sections can
be checked against an exactly-known geometry, and a designer can sweep camber and thickness without
needing a coordinate file at all.

## Selection criteria for water-sports foils

| Criterion | Guidance | Confidence |
|---|---|---|
| Design lift coefficient | `Cl ≈ 0.3`, operating range `0–0.6` | Verified (IHS) |
| Thickness ratio | **Hydrodynamics always prefers thinner — there is no optimum.** Section L/D and cavitation margin both fall monotonically from 6% to 20% t/c. Thickness is a *structural* variable with a measured price: 9%→12% costs ~14% of section L/D and 3.8 kn of cavitation-free speed. See `phase-0-findings.md` | Inferred (measured Phase 0; surrogate-computed) — **supersedes the earlier Flagged retail guidance** |
| Maximum practical thickness | ~20% t/c (general wing design). At 20% the measured section L/D is roughly **half** its 6% value | Flagged for the limit; Inferred for the cost |
| Camber | High camber gives strong low-speed lift and pumping efficiency, at the cost of a **negative pitching moment** that feels unstable at speed | Flagged (practitioner consensus, not measured) |
| Leading edge | Avoid sharp-edged sections that promote **leading-edge separation bubbles** — separation is the trigger condition for ventilation | Verified (IHS) |
| Pressure distribution | Rooftop: flat, no peaks | Verified (IHS) |

## What a catalog needs to store

Declaring the grain first: **one row is exactly one *(section, source revision)* pair** — the
geometry — and a second table holds **one row per *(section, Re, Ncrit, alpha)* polar point**.
Keeping these apart matters because polars are re-derivable and geometry is not.

Per section: identifier, family, human name, coordinate set with **provenance and revision**,
derived `t/c` and its chordwise position, derived camber and its position, trailing-edge thickness,
and a validity note. Derived quantities are **computed from the coordinates, never stored as
independent truth** — two definitions of thickness is the classic defect signature here.

Per polar point: `Re`, `Ncrit` (the e^N transition parameter — a polar without it is not
reproducible), `alpha`, `Cl`, `Cd`, `Cm`, and **`Cp_min`**, which is the input to the cavitation
check and is the one value most airfoil databases omit.

## Where the coordinates come from

- **UIUC Airfoil Data Site** — ~1,650 sections, Selig-format `.dat`, the canonical academic source.
- **airfoiltools.com** — the same sections plus precomputed XFOIL polars at several Reynolds
  numbers; convenient, but derived, and it was unreachable during this research (connection
  refused), which is itself an argument for vendoring the coordinates rather than fetching them.
- **Analytic generation** — NACA 4- and 5-digit sections and any CST-parameterised shape need no
  file at all (see `parametric-geometry.md`).
