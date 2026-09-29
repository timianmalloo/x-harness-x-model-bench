# Freshness Prober architecture

## Context

The Freshness Prober is a component inside the Workspace Authority Core that detects and closes a
gap when a scope's indexed data has fallen behind its repository. It exists because the obvious
staleness signal — does the graph look fresh to the daemon that built it — is self-referential: a
watcher that silently stopped delivering events still has a daemon whose own last-known state
reads fresh. This design owns detection and immediate remediation together, so a drift is never
left open. It does not decide how often a probe run happens, or display or acknowledge an
incident; those stay the operator's and the Health Incident Sidecar's own jobs.

## Components

`FreshnessProbeService` orchestrates one probe run over an explicit list of scope IDs. It reads
each scope's observed revision through `IRevisionProbe`, a boundary implemented against the same
repository-reading layer the Extractor Adapters already use — never against a value the daemon
cached from its own last-known state. It reads each scope's indexed revision through the existing
`IWorkspaceStore` read path. On a divergence it re-runs extraction for that scope itself, through
the existing `IExtractorAdapter` boundary, to bring the index back in sync, and then writes one
deduplicated incident through the existing `IHealthIncidentSink` recording that it happened.

## Component list

- `FreshnessProbeService` — the one new component this capability adds; orchestrates a probe run
  over a scope-ID list and a `now` timestamp, and on a divergence re-runs extraction for that
  scope itself before raising an incident; owns no durable state beyond its probe checkpoints.
- `IRevisionProbe` — reads a scope's observed revision directly from the repository; the read is
  never taken from the daemon's own last-known state, which is why the comparison catches what
  that state cannot.
- `IWorkspaceStore` (existing) — read-only source of each scope's indexed revision, from the
  latest committed snapshot; `FreshnessProbeService` adds no write path to it.
- `IExtractorAdapter` (existing) — invoked directly by `FreshnessProbeService` on a divergence, to
  re-extract the drifted scope and close the gap before the incident is raised.
- `IHealthIncidentSink` (existing, Health Incident Sidecar) — receives exactly one deduplicated
  incident write per divergent `{class, scope}` pair, recording that the prober already corrected
  it; occurrence count and last-seen time update on a repeat divergence instead of a second
  incident.

## Data structure

A probe run produces zero or more `FreshnessDrift` facts, one per scope whose comparison
disagrees: `{ScopeId, ObservedRevision, IndexedRevision, ProbedAt}`. The comparison is ordinal
string equality between the observed and indexed revisions; two absent revisions are not treated
as a drift, and the fact exists only when a present value disagrees with another present or absent
value. Agreement produces no fact and no incident.

## Operations

`RunAsync(scopeIds, now)` iterates the given scope IDs. For each scope it reads the observed
revision via `IRevisionProbe` and the indexed revision via `IWorkspaceStore`, compares them, and:
on agreement, does nothing further for that scope; on divergence, records one `FreshnessDrift`
fact, invokes `IExtractorAdapter` to re-extract that scope immediately, and then raises or updates
one deduplicated incident via `IHealthIncidentSink` keyed on `{class, scope}`. A scope already
carrying an unacknowledged incident of the same class gets its occurrence count and last-seen time
updated rather than a second incident. An empty scope-ID list produces no drifts and raises
nothing.

## Exception safety

A failed repository read for one scope is caught at that scope's iteration and reported
not-recorded for that scope only; `RunAsync` continues to the remaining scopes rather than
aborting the run. A scope whose read failed is never treated or reported as fresh, and no partial
or guessed revision value is ever written as if it were observed.

## Complexity

`RunAsync` is O(n) in the number of scope IDs given. Each scope's read, compare, re-extraction,
and incident lookup is a single-key operation against the store and the incident sink, so no
scope's cost depends on any other scope's data or on the total scope count beyond the one pass
over the list.

## Decision

**Decision:** the revision comparison is ordinal string equality, computed inside
`FreshnessProbeService` from a value `IRevisionProbe` reads fresh from the repository on every
run, never a value cached by the daemon or pushed into `IWorkspaceStore` itself.

**Alternatives considered:**

- *Compare timestamps instead of revisions.* Rejected: two different revisions can share a
  timestamp on a fast rebuild, so a timestamp comparison would miss a real drift that a revision
  comparison catches.
- *Push the comparison into `IWorkspaceStore` itself, as a store-side freshness check.* Rejected:
  the store has no repository access, and adding one there would duplicate the extractor's own
  repository-reading contract inside the store's boundary instead of reusing it through
  `IRevisionProbe`.
- *Report a divergence without re-extracting it.* Rejected: leaving a known-bad scope divergent
  until a separate scheduler notices it wastes the round trip this design already made to find
  the drift; closing it inline is one fewer moving part.
