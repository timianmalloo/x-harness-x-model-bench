# ai-de Freshness Prober: spec to architecture

Write the architecture for implementing the Freshness Prober capability of ai-de Core, from the
specification in this workspace.

The specification is `docs/specs/freshness-prober.md`: the product spec for this capability —
core scenario, domain model, non-functional requirements, and the explicit non-goals. It is the
what and the why. Design the how: the components, their boundaries, the data this capability
reads and writes, and the operations that implement each user story.

Write one architecture note to `docs/architecture.md`. Use these headings, each with a non-empty
body:

- `## Context`
- `## Components`
- `## Component list`
- `## Data structure`
- `## Operations`
- `## Exception safety`
- `## Complexity`
- `## Decision`

`## Context` states what this capability is for, in architecture terms, and what it does not
own (repair, scheduling cadence, incident display — see the spec's non-goals).

`## Components` names the pieces of the design in prose: the component that orchestrates a probe
run, the boundary it reads the repository through, the boundary it reads the store through, and
the boundary it writes an incident through.

`## Component list` gives that same design as a list: one bullet per component or interface, each
naming what it owns and what it must never do. State plainly, for the component that reads the
scope's current revision, that it reads the repository directly and never substitutes a cached or
daemon-held value for that read — the spec's core reason this capability exists at all. State
plainly, for whichever component is notified of a drift, that the prober itself never repairs,
fixes, or re-extracts to close the drift — that stays another component's job.

`## Data structure` names the drift fact this capability produces (the two revisions it compares
and how), and states the comparison rule.

`## Operations` walks the one operation a probe run performs across a list of scopes, tied to the
user stories in the spec: what happens on agreement, what happens on divergence, and how a
flapping scope avoids a second incident for the same `{class, scope}` pair.

`## Exception safety` states what happens when the repository read fails for one scope: it must
not abort the run for the remaining scopes, and it must never be reported as fresh.

`## Complexity` gives the cost of a probe run in the number of scopes.

`## Decision` states one architecture decision this design makes, in ADR shape: the decision
itself, then an "Alternatives considered" list naming at least one rejected alternative and why it
was rejected.

Do not rename the file or the headings above. Do not specify a UI; this capability has none (the
spec's Part B and Part C already say so).
