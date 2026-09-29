# ai-de Freshness Prober primer

Write the product specification for the Freshness Prober capability of ai-de Core, from the primer in this workspace.

The primer is `docs/architecture.md`: the "Freshness Prober" row of the "Component map and boundaries" table, and the "Silent watcher loss" bullet under "Failure and resilience". Specify that capability. The rest of the document is context for what this capability must not foreclose — the store, extraction and health-incident boundaries it sits beside. They are not part of the spec.

Write one specification to `docs/specs/freshness-prober.md`. It is the what and the why. Use these headings, each with a non-empty body:

- `## Part A — Functional specification`
- `## Part B — UX specification`
- `## Part C — UI specification`
- `### Core scenario`
- `### In scope / Out of scope (explicit non-goals)`
- `### User stories & acceptance criteria (testable)`
- `### Non-functional requirements (ISO/IEC 25010 checklist)`

Part A is the functional layer. Name the core scenario. State explicit non-goals. Give user stories with falsifiable Gherkin acceptance criteria (Given / When / Then) for a happy path and an error path. Walk the ISO/IEC 25010 checklist: each attribute is a measurable requirement or an explicit N/A. Where this capability introduces a domain concept, name the bounded context, the ubiquitous language, and the fact type with the one invariant it protects. Write that model in domain terms.

Part B is the UX layer and Part C is the UI layer. This capability has no user-facing surface. Mark a layer that does not apply as N/A and give the reason in that layer's body. Do not specify a screen.

State that the probe's comparison source is the repository's own observed revision, never the daemon's own last-known-event view, and that a divergence raises exactly one incident per scope and does not itself repair the drift.

Do not rename the file or the headings above.
