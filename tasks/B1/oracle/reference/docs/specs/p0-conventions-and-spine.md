# Spec: P0 conventions and spine

- **Status:** Draft
- **Tier (cost-of-error):** T1
- **Supersedes / related:** cfd-bench phasing plan, phase P0 "Conventions & spine" (revision 2). [Verified against that primer.]

## Part A — Functional specification

This phase specifies the wing definition a later phase can estimate, draw and export. It does not specify a solver, a screen, or a machine tool.

### Problem

A wing definition that does not fix its frame, its signs and its units cannot be tested, and a convention retrofitted after later phases is how a sign error becomes permanent. The phase exists to make one wing definable, and to make span, planform area, aspect ratio and mean chord checkable, before any estimator or screen is built. [Verified: the primer's gate and its "you can" sentence.]

### Conceptual domain model

Bounded context: the wing definition. Estimation, drawing and fabrication are other contexts. They may read this one. They do not redefine it.

Ubiquitous language:

- **Wing** — one lifting surface, the aggregate root.
- **Station** — a section at one spanwise place, carrying chord, anhedral and twist.
- **Loft** — the spline surface through the stations. It is a surface, not a mesh stand-in.
- **Span** — tip-to-tip distance along the spanwise axis after a symmetric wing is mirrored.
- **Planform area** — integral of chord along span, on the plan view, not the wetted area of the loft.
- **Aspect ratio** — span squared divided by planform area.
- **Mean chord** — planform area divided by span.
- **Project document** — the only document this product reads back as a wing.

The Wing aggregate protects one invariant: every stored length is a metre and every stored angle is a degree, and the four derived quantities are functions of the stations under the frame below. A comment is not a unit. The loft does not change those four quantities: they are planform quantities.

Two layers sit inside the aggregate. The station layer is the definition. The loft layer is the spline surface through those stations, and it remains capable of an exact export of its defining stations. Export is a port on the aggregate. The stub behind that port writes nothing.

### Core scenario

An engineer defines a symmetric rectangular wing: root on the centreline, tip half a metre to starboard, chord a tenth of a metre at every station, anhedral zero, twist zero. The product mirrors it and reports span 1 metre, planform area 0.1 square metres, aspect ratio 10 and mean chord 0.1 metres. A test compares those four numbers with the analytic values to a relative tolerance of 1e-12. That path is the phase. If it is wrong, nothing downstream is worth building.

### In scope / Out of scope (explicit non-goals)

- **In:** the frame and the signs; units carried by the quantity rather than by a comment; the station layer and the loft layer; the four planform quantities; a test strategy of an analytic case, a golden master and a tolerance; the project document as the only import; an export port with a stub that does not fabricate.
- **Out (non-goals):** a section polar, an estimator, or a cavitation number; any screen or chart; interactive editing of the outline; a free-surface model; a STEP file, a mould, or any other fabrication artifact; reconstructing stations by fitting an arbitrary CAD body; an imperial quantity inside the definition. Later phases own those. This phase must not make them impossible: the loft stays a spline that an export port can read exactly, and the port stays an interface.

### User stories & acceptance criteria (testable)

**US-1 — As an engineer, I want to define a wing and read its span, planform area, aspect ratio and mean chord, so that I can trust the geometry before any estimate.**

- **Given** a symmetric wing whose stations run from the centreline to half a metre starboard with a constant chord of a tenth of a metre, zero anhedral and zero twist, **When** the four planform quantities are read, **Then** span is 1 metre, planform area is 0.1 square metres, aspect ratio is 10 and mean chord is 0.1 metres, each within a relative tolerance of 1e-12.
- **Given** a wing whose station list is empty, **When** the four quantities are requested, **Then** no number is returned and the failure names the empty definition.

**US-2 — As an engineer, I want the signs of anhedral and twist fixed, so that a positive value means one direction in every later phase.**

- **Given** a wing that is otherwise the rectangle in US-1, **When** anhedral is set positive, **Then** the tip lies below the root along the vertical axis and the planform area is unchanged.
- **Given** the same rectangle, **When** twist is set positive, **Then** the tip section's nose is up relative to the root chord and the four planform quantities are unchanged.

**US-3 — As an engineer, I want to round-trip a wing only through this product's own document, so that a foreign body cannot be mistaken for a definition.**

- **Given** a project document this product wrote for the US-1 wing, **When** it is read back, **Then** the stations and the four quantities match the wing that was written.
- **Given** a document with no format identifier, or a CAD body that is not a project document, **When** import is attempted, **Then** no wing is loaded and the failure says the document is not this product's.

**US-4 — As an engineer, I want export to stay a port, so that fabrication can be added later without replacing the loft.**

- **Given** the US-1 wing and its loft, **When** the export port is called on the stub, **Then** no fabrication file is written, the stations are unchanged, and the result says export is not implemented.

### Non-functional requirements (ISO/IEC 25010 checklist)

| Attribute | Requirement (measurable) |
|---|---|
| Performance efficiency | The four quantities for a wing of at most 64 stations return in under 50 ms. [Inferred host budget.] |
| Reliability | A rejected import leaves no wing loaded. The export stub writes no file. |
| Security | N/A — this phase has no identity, no network and no document but the one it wrote. |
| Usability | N/A — no user-facing surface. See Part B. |
| Compatibility | Only a project document carrying the format identifier and the version is accepted. Any other input is the US-3 error. |
| Maintainability | US-1 is an analytic test at relative tolerance 1e-12. A non-rectangular golden master compares at relative tolerance 1e-9. The export port is an interface, not a writer. |
| Portability | Lengths are metres and angles are degrees inside the definition. No host path is part of the wing. |

### Boundary set

Empty station list. A single station, which cannot produce a span. Chord of zero. The maximum of 64 stations. A missing format identifier. A positive and a negative anhedral of the same magnitude, which must place the tip on opposite sides of the root and leave the planform area equal.

### Comparables & user evidence (sourced)

| Claim | Source | Confidence |
|---|---|---|
| P0 delivers a wing and the four planform quantities, with tests, in 2.5 weeks, and nothing gates its start. | Phasing plan, section 03, "Conventions & spine". | Verified |
| The loft stays a spline that can be exported exactly, and export is an interface with a stub. Fabrication is out of this phase. | Same section, revision-2 addition. | Verified |
| Origin and the signs of anhedral and twist were still open in the plan, and units belong in the type system. | Same plan, section 06, the open GAP-04 item. | Verified |
| Import means a document this product wrote. Fitting stations from an arbitrary body is out of scope. | Standing commitment that the plan's file-format sentence rests on. | Verified |

The frame below is this spec's decision for the gap the plan left open. It is marked as a decision to confirm, not as a fact the plan already contained.

### Conventions this spec decides

[Flagged: confirm before implementation. The primer asks for these signs and does not choose them.]

Right-handed frame. Origin at the leading edge of the root station.

- Positive x runs aft, from leading edge toward trailing edge.
- Positive y runs to starboard.
- Positive z runs up.

Positive anhedral lowers the tip (smaller z). Positive twist rotates the tip nose up relative to the root chord. A symmetric wing is mirrored through the centreline plane before span and area are taken. Span is the y-distance from tip to tip. Planform area integrates chord along that span. Aspect ratio is span squared over that area. Mean chord is that area over span.

### Applicable governance lenses

- [x] Quality attributes / NFRs — the table above.
- [x] Threat model — N/A for this phase: local document, no identity, no irreversible fabrication write (the stub writes nothing).
- [x] Privacy & data governance — the wing document holds geometry only.
- [x] Accessibility — N/A, no surface.
- [x] Performance budget — 50 ms for 64 stations.
- [x] Release / rollback / migration — a document whose version is not the one this spec names is rejected, not half-read.
- [x] Observability — an import rejection and an export-stub call each name their reason. No silent skip.

## Part B — UX specification

N/A — this phase is headless. The primer's first user-facing surface is a later phase ("Read a wing"). There is no information architecture, no flow and no wireframe to specify here. Specifying a screen in this phase would settle a surface the functional layer does not have.

## Part C — UI specification

N/A — this phase has no visual UI. Part C stays unset because Part B does not apply. No archetype, token, screen or motion is specified.

## Flagged risks & residual unknowns

- The frame and the signs above are a decision this spec proposes. The primer left them open. Confirming them is the cheapest probe, and it has to happen before the first geometry code, which is the primer's own warning.
- "Span" is specified as tip-to-tip on the spanwise axis for a mirrored symmetric wing. A one-sided wing that is not mirrored is a different product and is out of this scenario. If a later phase needs a half-model, it must say so against this definition rather than silently halving the area.
- The 50 ms budget is an inference, not a measurement. The analytic tolerances are the requirement that blocks a wrong quantity. The time bound is the requirement that blocks an accidental solver inside this phase.
