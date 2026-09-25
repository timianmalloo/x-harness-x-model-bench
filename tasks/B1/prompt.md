# P0 conventions and spine

Write the product specification for phase P0, "Conventions & spine", from the primer in this workspace.

The primer is `docs/proposals/build-phasing-plan.html`, section 03, the phase headed "Conventions & spine". Specify that phase. Later phases in the same document are context for what this phase must not foreclose. They are not part of the spec.

Write one specification to `docs/specs/p0-conventions-and-spine.md`. It is the what and the why. Use these headings, each with a non-empty body:

- `## Part A — Functional specification`
- `## Part B — UX specification`
- `## Part C — UI specification`
- `### Core scenario`
- `### In scope / Out of scope (explicit non-goals)`
- `### User stories & acceptance criteria (testable)`
- `### Non-functional requirements (ISO/IEC 25010 checklist)`

Part A is the functional layer. Name the core scenario. State explicit non-goals. Give user stories with falsifiable Gherkin acceptance criteria (Given / When / Then) for a happy path and an error path. Walk the ISO/IEC 25010 checklist: each attribute is a measurable requirement or an explicit N/A. Where this phase introduces a domain concept, name the bounded context, the ubiquitous language, and each aggregate with its root and the one invariant it protects. Write that model in domain terms.

Part B is the UX layer and Part C is the UI layer. This phase has no user-facing surface. Mark a layer that does not apply as N/A and give the reason in that layer's body. Do not specify a screen.

State the coordinate frame, the sign of anhedral and of twist, and that units live in the type system rather than in comments. State that the wing's own document is the only import path. Keep the loft a real spline surface that can be exported exactly, and keep export as an interface with no fabrication implementation behind it.

Do not rename the file or the headings above.
