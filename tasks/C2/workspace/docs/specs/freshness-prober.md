# Spec: Freshness Prober

- **Status:** Draft
- **Tier (cost-of-error):** T1
- **Supersedes / related:** ai-de `docs/architecture.md`, "Component map and boundaries" (Freshness Prober row) and "Failure and resilience" (silent watcher loss bullet). [Verified against that primer.]

## Part A — Functional specification

This capability specifies how ai-de Core detects that a scope's indexed data has gone stale relative to its repository, without trusting any signal the daemon itself produced. It does not specify how a stale scope is repaired, how incidents are displayed, or how often the probe runs.

### Problem

The obvious staleness metric — "does the graph look fresh to the daemon that built it?" — is self-referential: a watcher that silently stopped delivering events still has a daemon that believes its own last-known state is current, so the graph rots while every internal signal reads green. The capability exists to give freshness one measurement that does not share a failure mode with the thing it is measuring: an independent comparison against the repository itself. [Verified: primer, "Silent watcher loss is caught by the Freshness Prober comparing repository-observed to indexed revision, not by the daemon's own last-event view (which would read fresh while the graph rots)."]

### Conceptual domain model

Bounded context: workspace freshness, a supporting concern inside the Workspace Authority Core. Extraction (which produces the indexed revision) and the Health Incident Sidecar (which durably records the incident) are neighboring contexts. This capability reads from the first and writes to the second; it owns neither.

Ubiquitous language:

- **Scope** — one unit the ingestion scheduler tracks and extracts; the freshness comparison is per scope.
- **Observed revision** — the scope's current revision as read directly from the repository, independent of the watcher.
- **Indexed revision** — the artifact revision recorded on the scope's latest committed snapshot in the fact store.
- **Freshness drift** — the fact that observed revision and indexed revision disagree for a scope, at one probe run.
- **Health incident** — the durable, deduplicated record a drift raises in the Health Incident Sidecar.

The one fact type this capability produces is the freshness drift. Its invariant: a drift fact exists for a scope only when the observed and indexed revisions are unequal at the moment of comparison; agreement produces no fact and no incident. The drift's existence — not a "still fresh" flag — is the record; silence is not itself evidence of freshness because the probe records only divergence, so the absence of a drift on one scope means only that this scope was not found stale on this run, not that the workspace as a whole was checked.

### Core scenario

The probe runs against a set of scope IDs. For each scope, it reads the observed revision from the repository directly (not from the daemon's own last-known state) and compares it, by ordinal equality, to the indexed revision recorded on that scope's latest committed snapshot. When they disagree, the probe records one freshness drift fact and raises exactly one health incident for that scope, deduplicated against any existing unacknowledged incident of the same class and scope rather than appending a new one per divergence. The comparison never repairs the drift itself, and never removes or supersedes indexed data; a later, independent extraction run is what closes the drift, not this probe.

### In scope / Out of scope (explicit non-goals)

- **In:** comparing one scope's repository-observed revision to its indexed revision; recording a freshness-drift fact per divergence; raising exactly one deduplicated health incident per `{class, scope}`; running the comparison independently of the daemon's own last-known/last-event state; re-enqueuing a drifted scope so extraction can catch it up.
- **Out (non-goals):** repairing, re-extracting, or otherwise correcting the drift (that is the ingestion scheduler and extractor adapters' job, triggered separately); deciding *when* or how often the probe runs (a scheduling policy, not this capability); displaying, acknowledging or evicting incidents (the Health Incident Sidecar's contract); any user-facing surface; any statement about *why* a scope diverged (network partition, crash, permission change) — the probe reports that it diverged, not why.

### User stories & acceptance criteria (testable)

**US-1 — As the workspace operator, I want a scope's freshness checked against the repository itself, so that a dead watcher cannot look healthy.**

- **Given** a scope whose repository-observed revision differs from its indexed revision, **When** the probe runs against that scope, **Then** the probe returns a freshness drift for that scope and one health incident is raised, dated to the probe run.
- **Given** a scope whose repository-observed revision equals its indexed revision, **When** the probe runs against that scope, **Then** the probe returns no drift for that scope and no incident is raised.

**US-2 — As the workspace operator, I want a drift never blamed on the source it is comparing against, so that the check is trustworthy.**

- **Given** the comparison for one scope, **When** the probe reads the observed side, **Then** it reads the repository directly and never substitutes the daemon's own last-known state for that read.

**US-3 — As the workspace operator, I want a flapping scope to raise one incident, not a flood, so that the incident channel still names the thing that matters.**

- **Given** a scope already carrying an unacknowledged `freshness.drift` incident, **When** the probe finds the same scope still diverged on a later run, **Then** the existing incident's occurrence count and last-seen time update; no second incident for that `{class, scope}` pair is created.
- **Given** a scope whose incident was acknowledged, **When** the probe finds it diverged again, **Then** a new incident is created for that scope.

**US-4 — As the workspace operator, I want the probe to detect and report only, so that repair stays the extractor's responsibility.**

- **Given** a scope with a recorded freshness drift, **When** no other action is taken, **Then** the indexed revision on that scope is unchanged and no extraction is triggered by the probe itself; the drift is closed only by a later, independent snapshot commit that makes the two revisions agree again.

### Non-functional requirements (ISO/IEC 25010 checklist)

| Attribute | Requirement (measurable) |
|---|---|
| Performance efficiency | Probing 1,000 scopes completes in under 2 s against a warm store read. [Inferred host budget.] |
| Reliability | A read failure on one scope's repository probe does not abort the run for the remaining scopes; that scope is reported as not-recorded, never as "fresh". |
| Security | N/A — this capability reads workspace-local repository and store state only; it makes no network call and exposes no MCP surface of its own. |
| Usability | N/A — no user-facing surface. See Part B. |
| Compatibility | Revision comparison is ordinal string equality; it makes no assumption about the extractor's revision format beyond that it is a comparable string. |
| Maintainability | Each drift and each incident emission is independently testable: agreement → no fact, no incident; disagreement → one fact, one deduplicated incident. |
| Portability | The probe depends only on `IRevisionProbe` and the store's latest committed snapshot; it carries no OS- or filesystem-path-specific behaviour of its own. |

### Boundary set

No scopes supplied (probe returns no drifts and raises nothing). A scope with no committed snapshot yet (indexed revision is absent; a non-empty observed revision is a drift; two absent values are not compared as equal, per the guard against reporting permanent drift on every workspace). A scope whose observed revision briefly disagrees then agrees again on the very next run (drift recorded once, no incident survives past acknowledgement policy, which is the sidecar's contract, not this one). Two scopes that diverge simultaneously and share no incident class or scope key with each other (independent incidents).

### Comparables & user evidence (sourced)

| Claim | Source | Confidence |
|---|---|---|
| The prober exists because the daemon's own staleness signal is self-referential and reads fresh while the graph rots. | `docs/architecture.md`, "Failure and resilience", "Silent watcher loss…" bullet. | Verified |
| The comparison is `scope.observed_revision` vs `scope.indexed_revision`; divergence raises a health incident and re-enqueues the scope. | `docs/architecture.md`, "Component map and boundaries", Freshness Prober row. | Verified |
| Incidents dedup on `{class, scope}` with an occurrence count; unacknowledged incidents evict last. | `docs/architecture.md`, Health Incident Sidecar row and Observability section. | Verified |

### Conventions this spec decides

[Flagged: confirm before implementation. The primer names the comparison and the incident but does not fix these operational details.]

Revision equality is ordinal string comparison. Two absent revisions (no observed value and no committed snapshot) are not treated as a drift — only a present value disagreeing with another value, or a present value against an absent one, counts. A probe run takes an explicit scope-ID list and an explicit `now` timestamp rather than discovering scopes or the clock itself, so a run is reproducible from its inputs.

### Applicable governance lenses

- [x] Quality attributes / NFRs — the table above.
- [x] Threat model — N/A: no network call, no new MCP surface, reads only workspace-local state already governed by the store and extractor boundaries.
- [x] Privacy & data governance — the probe reads and emits revision identifiers only, never artifact content.
- [x] Accessibility — N/A, no surface.
- [x] Performance budget — 2 s for 1,000 scopes.
- [x] Release / rollback / migration — no store schema change; the probe is a reader plus one incident write.
- [x] Observability — `aide.freshness.probe` span with a `freshness.drift_count` tag; a read failure is reported not-recorded, never fabricated as fresh.

## Part B — UX specification

N/A — this capability has no user-facing surface of its own. It writes to the Health Incident Sidecar, which a later workspace-health view reads; specifying that view is out of scope here (it belongs to the sidecar's and the health view's own specs, not this one).

## Part C — UI specification

N/A — this capability has no visual UI. Part C stays unset because Part B does not apply. No archetype, token, screen or motion is specified.

## Flagged risks & residual unknowns

- The primer names re-enqueuing the scope as part of what divergence does; this spec keeps that as an in-scope outcome of a drift but does not fix the scheduling contract (priority, coalescing) that re-enqueue uses — that is the Ingestion Scheduler's own spec.
- The primer does not say how often the probe runs. This spec deliberately leaves cadence as a residual unknown rather than inventing a number the primer does not support.
- The 2 s / 1,000-scope budget is an inference, not a measurement. The correctness requirement (agreement → nothing, disagreement → one deduplicated incident) is what blocks a wrong answer; the time bound only blocks an accidental unbounded scan.
