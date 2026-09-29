# Freshness Prober architecture

## Context

The Freshness Prober is a component inside the Workspace Authority Core that detects when a
scope's indexed data has fallen behind what the daemon itself last observed. This design owns
detection only. It does not repair a drift, decide how often a probe run happens, or display or
acknowledge an incident; those stay the Ingestion Scheduler's, the operator's, and the Health
Incident Sidecar's own jobs.

## Components

`FreshnessProbeService` orchestrates one probe run over an explicit list of scope IDs. It reads
each scope's observed revision through `IRevisionProbe`, a boundary that returns the daemon's own
cached last-known revision for that scope, so no extra I/O is needed on every run. It reads each
scope's indexed revision through the existing `IWorkspaceStore` read path. On a divergence it
writes one deduplicated incident through the existing `IHealthIncidentSink` and notifies the
existing `IIngestionReenqueue` boundary so the scope is picked up again; it calls no extractor
itself.

## Component list

- `FreshnessProbeService` — the one new component this capability adds; orchestrates a probe run
  over a scope-ID list and a `now` timestamp; owns no durable state beyond its probe checkpoints.
- `IRevisionProbe` — returns the daemon's own cached last-known revision for a scope, already
  held in memory from the daemon's own ingestion bookkeeping, so the comparison needs no extra
  round trip.
- `IWorkspaceStore` (existing) — read-only source of each scope's indexed revision, from the
  latest committed snapshot; `FreshnessProbeService` adds no write path to it.
- `IHealthIncidentSink` (existing, Health Incident Sidecar) — receives exactly one deduplicated
  incident write per divergent `{class, scope}` pair; occurrence count and last-seen time update
  on a repeat divergence instead of a second incident.
- `IIngestionReenqueue` (existing, Ingestion Scheduler) — the sole component
  `FreshnessProbeService` notifies to re-enqueue a drifted scope; the prober itself never repairs,
  fixes, or re-extracts the drift, and closing it is this component's job, not the prober's.

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
fact, raises or updates one deduplicated incident via `IHealthIncidentSink` keyed on
`{class, scope}`, and calls `IIngestionReenqueue` once for that scope. A scope already carrying an
unacknowledged incident of the same class gets its occurrence count and last-seen time updated
rather than a second incident. An empty scope-ID list produces no drifts and raises nothing.

## Exception safety

A failed lookup for one scope is caught at that scope's iteration and reported not-recorded for
that scope only; `RunAsync` continues to the remaining scopes rather than aborting the run. A
scope whose lookup failed is never treated or reported as fresh, and no partial or guessed
revision value is ever written as if it were observed.

## Complexity

`RunAsync` is O(n) in the number of scope IDs given. Each scope's read, compare, and incident
lookup is a single-key operation against the store and the incident sink, so no scope's cost
depends on any other scope's data or on the total scope count beyond the one pass over the list.

## Decision

**Decision:** the revision comparison is ordinal string equality, computed inside
`FreshnessProbeService` from a value `IRevisionProbe` returns from the daemon's own already-cached
state, avoiding a repository read on every run.

**Alternatives considered:**

- *Compare timestamps instead of revisions.* Rejected: two different revisions can share a
  timestamp on a fast rebuild, so a timestamp comparison would miss a real drift that a revision
  comparison catches.
- *Push the comparison into `IWorkspaceStore` itself, as a store-side freshness check.* Rejected:
  the store already holds the indexed revision, and adding a second read path there would
  duplicate `IRevisionProbe`'s own contract inside the store's boundary.
- *Read the repository directly on every probe run.* Rejected: the daemon's own cached state is
  already available and a direct read on every run would cost more without changing the result
  under normal operation.
