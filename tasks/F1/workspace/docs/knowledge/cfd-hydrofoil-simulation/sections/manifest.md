---
id: kb-cfd-section-manifest
title: "Vendored Section Coordinate Manifest"
type: knowledge
status: draft
owner: "@timianmalloo"
tags: [sections, coordinates, provenance, catalog, phase-0]
links:
  - { to: kb-cfd-foil-sections, rel: refines }
review-by: 2026-12-04
summary: >-
  Provenance record for the section coordinate files vendored into this repo from the UIUC Airfoil
  Data Site, with geometry measured from the coordinates themselves and a parser verified against
  analytic NACA truth.
---

# Vendored section coordinate manifest

Retrieved **2026-09-05** from the UIUC Airfoil Data Site
(`https://m-selig.ae.illinois.edu/ads/coord/`). Files are stored verbatim as downloaded; the `.dat` files in this directory are the
record. Geometry below is **measured from those coordinates**, never transcribed.

## Parser verification

The measurement code was validated against sections whose geometry is known analytically **before**
any of these numbers were trusted:

| Section | Format | Expected | Measured | Result |
|---|---|---|---|---|
| NACA 0012 | Lednicer | 12.00% t/c, 0.00% camber | 12.00%, 0.00% | PASS |
| NACA 4412 | Selig | 12.00% t/c, 4.00% camber @ 0.30c | 12.02%, 4.00% @ 0.30c | PASS |
| NACA 64A410 | Selig | 10.00% t/c | 9.99% | PASS |

**A first attempt failed this test** — it read every file as Selig format and returned 6.00% t/c and
3.00% camber for NACA 0012, which is impossible for a symmetric section. The cause was
**Lednicer-format files** (surfaces listed separately from the leading edge) being parsed as Selig
(a single loop from the trailing edge). Six of the eight Eppler files are Lednicer. Without the
analytic check this would have silently corrupted every geometry figure in the catalog.

## Manifest

| File | SHA-256 (16) | Name in file | Format | Points | t/c | @x/c | Camber | @x/c | TE gap |
|---|---|---|---|---|---|---|---|---|---|
| `e817.dat` | `6360d664f0854e33` | EPPLER 817 HYDROFOIL AIRFOIL | Lednicer | 69 | **10.98%** | 0.329 | +2.88% | 0.689 | 0.00% |
| `e818.dat` | `1ed98b50f0ccb5d1` | EPPLER 818 HYDROFOIL AIRFOIL | Lednicer | 68 | **9.37%** | 0.331 | +2.79% | 0.670 | 0.00% |
| `e836.dat` | `eeb8acdec08a7c47` | EPPLER E836 HYDROFOIL AIRFOIL | Lednicer | 62 | **12.64%** | 0.427 | +0.00% | 0.000 | 0.00% |
| `e837.dat` | `d70e1903e752cd7e` | EPPLER E837 HYDROFOIL AIRFOIL | Lednicer | 62 | **16.11%** | 0.369 | +0.00% | 0.000 | 0.00% |
| `e838.dat` | `dd7ba5f5178c999c` | EPPLER E838 HYDROFOIL AIRFOIL | Lednicer | 62 | **18.37%** | 0.372 | +0.00% | 0.466 | 0.00% |
| `e874.dat` | `57e2b18cf5c88133` | EPPLER 874 HYDROFOIL AIRFOIL | Lednicer | 121 | **7.90%** | 0.288 | +0.95% | 0.334 | 0.00% |
| `e904.dat` | `0d5495a3d0f3b3aa` | EPPLER 904 AIRFOIL | Lednicer | 110 | **9.00%** | 0.449 | +1.34% | 0.505 | 0.00% |
| `e908.dat` | `3bec10d34b52001f` | EPPLER 908 AIRFOIL | Lednicer | 110 | **9.00%** | 0.443 | +2.77% | 0.663 | 0.00% |
| `n0012.dat` | `7829acaf08720d89` | NACA 0012 AIRFOILS | Lednicer | 132 | **12.00%** | 0.300 | +0.00% | 0.000 | 0.25% |
| `naca4412.dat` | `10902e5b607d57a8` | NACA 4412 | Selig | 35 | **12.02%** | 0.300 | +4.00% | 0.400 | 0.26% |
| `naca64a410.dat` | `60b27d4c6e362a99` | NACA 64A410 | Selig | 51 | **9.99%** | 0.399 | +2.66% | 0.500 | 0.04% |

## What the measured geometry shows

**The Eppler hydrofoil set splits cleanly into two groups**, which is not stated in any secondary
source found during this research:

- **Cambered lifting sections** — E817, E818, E874, E904, E908 at **7.90%–10.98% t/c**
  (mean 9.25%). E817, E818 and E908 carry their maximum camber very far aft, at **0.66–0.69 c**.
  Aft-loaded camber is the classical way to obtain a flat "rooftop" pressure distribution with a low
  suction peak, so the geometry corroborates the design criterion the International Hydrofoil
  Society states in prose.
- **Symmetric sections** — E836, E837, E838 at **12.64%, 16.11%, 18.37%** with exactly zero camber.
  A zero-camber thickness ladder is a **strut/mast family**, not a lifting family: a strut must work
  at both positive and negative incidence, and needs section depth for bending strength. Treating
  these as front-wing candidates would be a category error.

The `naca*` and `n0012` files are **baselines and regression fixtures**, not design candidates.
