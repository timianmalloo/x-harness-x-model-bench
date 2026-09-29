# Spec: P1 — Estimator, validated

- **Status:** Draft
- **Tier (cost-of-error):** T1
- **Related:** cfd-bench `docs/proposals/build-phasing-plan.html`, section 03, phase P1 ("Estimator, validated"). Gate to start: P0 complete. [Verified against that primer.]

## Part A — Functional specification

This phase specifies a headless, scriptable performance estimator for a wing definition, built from a vendored section catalog and a closed-form aerodynamic chain, and validated against real experimental data before anything downstream is allowed to consume its numbers.

### Core scenario

An operator (or an upstream phase's code) hands the estimator a wing definition built to P0's conventions. The estimator resolves each station's aerofoil section from the section catalog — 11 sections already vendored with content hashes and measured geometry, stored in the Selig coordinate format only; the caller must pre-convert a section supplied in another layout to Selig before the catalog accepts it — and reads each section's polar, retaining `Cp_min` and `Ncrit`. It runs the closed-form chain (Helmbold lift, lifting-line induced drag, ITTC flat-plate friction, Hoerner form factor, cavitation critical speed) and returns L/D, Cl/Cd, the required angle of attack, and the cavitation margin for the given operating point. Before this phase's "you can" claim holds, the chain is validated against DTIC ADA032272's real towing-tank lift and drag data for the NACA 16-309 and 64A309 sections: the estimator's predicted L/D and drag are compared to that experimental record, not to a CFD-computed or self-consistency reference, and the comparison is checked to be within the phase's stated tolerance. The whole path is headless and scriptable: no UI renders any part of it, so the numbers are testable and checked against experiment before four phases of UI are ever built on top of them.

### In scope / Out of scope (explicit non-goals)

- **In scope:**
  - The 11-section catalog, vendored with content hashes and measured geometry, in Selig format only.
  - Section polars retaining `Cp_min` and `Ncrit`.
  - The closed-form chain: Helmbold lift, lifting-line induced drag, ITTC friction, Hoerner form factor, cavitation critical speed.
  - Validating the chain's output against DTIC ADA032272's real towing-tank lift and drag data for the NACA 16-309 and 64A309 sections.
  - A headless, scriptable API returning L/D, Cl/Cd, required angle of attack, and cavitation margin for a given wing definition and operating point.
- **Out of scope (explicit non-goals):**
  - Any UI, dashboard, or plot rendering the estimator's output; this phase delivers a headless library, not a viewer. A later phase, not this one, may build a screen on top of it.
  - Validating the chain against a synthetic, CFD-computed, or self-consistency reference; the validation case is the real experimental dataset named above, not a number the chain produces about itself.
  - Accepting a section coordinate file in any layout other than Selig; a section supplied in another layout is out of scope until the caller pre-converts it.
  - Fabrication, export, or any geometry mutation; this phase only estimates performance for a wing definition that P0 already produced.
  - Section catalog entries beyond the 11 already vendored; adding sections is a later phase's concern.

### User stories & acceptance criteria (testable)

**US-1 — Estimate performance for a wing definition**
- **Given** a valid wing definition and an operating point,
- **When** the estimator runs the closed-form chain against it,
- **Then** it returns L/D, Cl/Cd, the required angle of attack, and the cavitation margin, with no UI involved at any step.

**US-2 — Read a section stored in Selig format**
- **Given** a catalog section stored in Selig coordinate order,
- **When** the estimator loads that section,
- **Then** it reads it correctly.

**US-3 — Validate against real experimental data**
- **Given** the closed-form chain configured for the NACA 16-309 and 64A309 sections,
- **When** the validation case runs,
- **Then** the chain's predicted L/D and drag are compared against DTIC ADA032272's towing-tank data, not against a CFD-computed or self-referential value, and the comparison is reported within the stated tolerance.

**US-4 — Reject a section not in Selig format**
- **Given** a section file that does not match the Selig coordinate layout,
- **When** the estimator attempts to load it,
- **Then** it reports the format as unsupported and asks the caller to pre-convert it, rather than guessing a layout and silently mis-reading the coordinates.

### Non-functional requirements (ISO/IEC 25010 checklist)

| Attribute | Requirement |
|---|---|
| Performance efficiency | A single-point estimate (one wing definition, one operating point) completes in well under a second on the closed-form chain alone; no numerical solve is iterative beyond the chain's own closed-form terms. |
| Reliability | An unrecognized section format or a missing catalog entry is reported as such, never silently defaulted to one format or approximated. |
| Security | N/A — no network call, no external input beyond the vendored catalog and the caller's wing definition. |
| Usability | N/A — no user-facing surface; see Part B. |
| Compatibility | Reads the Selig coordinate convention the vendored catalog uses, on any host the closed-form chain runs on. |
| Maintainability | The closed-form chain's five terms (Helmbold, lifting-line induced drag, ITTC friction, Hoerner form factor, cavitation critical speed) are independently testable units; the validation case is a fixed, versioned fixture, not a moving target. |
| Portability | The estimator is a pure computation over the wing definition and the catalog; it makes no OS- or filesystem-path-specific assumption beyond reading vendored section files. |

### Conceptual domain model

Bounded context: Wing Performance Estimation, downstream of P0's Wing Geometry context and upstream of every later phase that consumes a validated number.

Ubiquitous language:

- **Section Catalog** — the 11 vendored aerofoil sections, each with a content hash, measured geometry, and a polar retaining `Cp_min` and `Ncrit`.
- **Coordinate Format** — Selig, the one layout the catalog accepts; a section in another layout must be pre-converted by the caller before it is a usable catalog member.
- **Estimate** — the value object returned for one wing definition at one operating point: L/D, Cl/Cd, required angle of attack, cavitation margin.
- **Validation Case** — the fixed DTIC ADA032272 experimental record for the NACA 16-309 and 64A309 sections, against which the closed-form chain's predictions are compared.

The Section Catalog is the aggregate root; its invariant is that every entry is stored in Selig coordinate order with a measured-geometry hash before it can be used by the closed-form chain — an entry supplied in another layout is not a usable catalog member until the caller pre-converts it. The Estimate is a value object: it is recomputed from a wing definition and an operating point, never mutated or stored as the source of truth for a later recomputation.

## Part B — UX specification

N/A — this phase is headless on purpose. It has no user-facing surface of its own; a downstream phase may build a viewer over its output, but that viewer is out of scope here.

## Part C — UI specification

N/A — no visual UI is specified in this phase, because Part B does not apply. No screen, dashboard, or plot is part of this phase's deliverable.
