# P1 estimator, validated

Write the product specification for phase P1, "Estimator, validated", from the primer in this workspace.

The primer is `docs/proposals/build-phasing-plan.html`, section 03, the phase headed "Estimator, validated". Specify that phase. The other phases in the same document are context for what this phase must not foreclose. They are not part of the spec.

Write one specification to `docs/specs/p1-estimator-validated.md`. It is the what and the why. Use these headings, each with a non-empty body:

- `## Part A — Functional specification`
- `## Part B — UX specification`
- `## Part C — UI specification`
- `### Core scenario`
- `### In scope / Out of scope (explicit non-goals)`
- `### User stories & acceptance criteria (testable)`
- `### Non-functional requirements (ISO/IEC 25010 checklist)`

Part A is the functional layer. Name the core scenario. State explicit non-goals. Give user stories with falsifiable Gherkin acceptance criteria (Given / When / Then) for a happy path and an error path. Walk the ISO/IEC 25010 checklist: each attribute is a measurable requirement or an explicit N/A. Where this phase introduces a domain concept, name the bounded context, the ubiquitous language, and each entity or value object with the one invariant it protects. Write that model in domain terms.

Part B is the UX layer and Part C is the UI layer. This phase has no user-facing surface: it is headless on purpose, so the core value is testable without a single pixel and everything downstream consumes it. Mark a layer that does not apply as N/A and give the reason in that layer's body. Do not specify a screen or a dashboard.

State that the section catalog supports both the Selig and the Lednicer aerofoil coordinate formats, detected automatically rather than fixed to one format or left for the caller to specify. State that the estimator is validated against DTIC ADA032272's real towing-tank lift and drag data for the NACA 16-309 and 64A309 sections, not against a synthetic or self-computed reference.

Do not rename the file or the headings above.
