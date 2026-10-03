---
id: "adr-0016-campaign-record"
title: "ADR-0016: The Evaluation Campaign is a committed, hash-chained ledger over unchanged runs, with content-addressed records"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation E1 onward"
tags: [benchmark, data-model, grain, campaign, discrimination, ring, persistence]
links:
  - { to: arch-evaluation-campaign, rel: refines }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: adr-0006-results-data-model, rel: depends-on }
review-by: "2027-10-03"
summary: >-
  The Evaluation Campaign context keeps one append-only, hash-chained ledger per campaign under
  bench/campaigns/<id>/ (committed, single writer `bench campaign`), plus immutable content-addressed files for
  engine identities, pre-registrations and power-analysis inputs. Discrimination records are create-only files
  keyed by (task version, engine identity, platform), produced by synthetic cells through the engine. Rings are
  committed matrix templates identified by content hash. The campaign references runs by id and never copies
  their facts; eligibility, gate results, power outputs and verdicts are derived.
---

# ADR-0016: The Evaluation Campaign is a committed, hash-chained ledger over unchanged runs

- **Status:** Proposed
- **Date:** 2026-10-03
- **Deciders:** @timianmalloo; authored by Claude Code with the Data & Persistence Architect lens (DM1-DM13)
- **Context spec/architecture:** `docs/specs/enterprise-evaluation.md` (domain model; EV-7, EV-12..EV-16, EV-20); `docs/architecture-evaluation-campaign.md`.

## Context

The spec adds a Campaign aggregate (states `draft` → `baselined` → `piloted` → `registered` → `measuring` → `concluded` | `abandoned`), a Discrimination record aggregate, and value objects (engine baseline, pre-registration, power analysis by input hash, ring as a hashed matrix template). A campaign spans days and several runs. ADR-0006 already gives the repo one durable model: append-only, hash-chained JSON Lines with declared grains, immutable content-addressed dimensions, derived views. `runs/` is gitignored and local; a pre-registration benefits from a witness the operator cannot quietly rewrite. The task version hash covers every file in `tasks/<ID>/` (`plan.task_version_hash`), so nothing produced *about* a task may live inside its folder.

## Decision

**1. One ledger per campaign, committed.** `bench/campaigns/<campaign_id>/ledger.jsonl` follows ADR-0006's physical rules exactly (canonical form, `seq`/`prev_hash`/`hash`, fsync per line, owner-only tail repair, `bench verify --campaign`). Single writer: the `bench campaign` command, under `bench/campaigns/<id>/campaign.lock` (existing `oslock`). The operator (or the skill) commits the folder; git history is the witness.

**Grain:** one row is exactly one state transition or one recorded decision of one campaign. Key `(campaign_id, seq)`. Row kinds (closed enum): `campaign.created{question}`, `baseline.recorded{identity_hash}`, `defect_fix.admitted{defect_class, commit, changes, scope}`, `power.recorded{role: prior|final, input_hash}`, `ring_run.attached{tag, ring_hash, run_id}`, `pilot.passed{run_id, grading_id, gate_input_hash}`, `admission.decided{task, admitted, reason}`, `registered{prereg_hash}`, `grid.attached{run_id}`, `concluded`, `abandoned{reason}`. No measures; no free text except `question` and `reason`, which never cross B2.

**Current state** is derived: the last transition row (DM7). Each command **first acquires `campaign.lock`, then reads the state** and decides (council D6: no check-then-lock window): the same content again is a no-op success; different content in a state that forbids it is refused, naming the item and an action (EVX-4). Every admission and refusal check (defect fix before-hash, registration preconditions, pilot coverage) runs inside the lock.

**2. Immutable, content-addressed campaign files** (each file name is its sha256; a test asserts it). Grains in full (council P3):
- `identity/<hash>.json` — one file is exactly one engine identity manifest, identified by `identity_hash`, recorded when a baseline is taken or a run is planned for the campaign (ADR-0017);
- `prereg/<hash>.json` — one file is exactly one pre-registration statement (EV-13 fields), identified by `prereg_hash` (sha256 of its canonical form), recorded when P1 confirms it in state `piloted`; the `registered` ledger row names which one is in force;
- `power/<input_hash>.json` — one file is exactly one set of power-analysis **inputs** (population, source run ids, rates, discordance, SDs, α, power, MDE, correction, `assumed` labels), identified by `input_hash`, recorded when `bench campaign power` runs; the `power.recorded{role}` row says whether it is the `prior` or `final` analysis. Outputs are a pure function of the inputs (ADR-0020), recomputed on read, never stored as truth.

**2a. One create-once primitive (councils D3 and Simplifier).** Every create-only file in this ADR — content-addressed campaign files and discrimination records — is written through one helper, `create_once(path, data)`: write a temporary file in the same folder, fsync and close it, `os.link(tmp, final)` (which fails atomically if `final` exists), then unlink the temporary. A reader of the final path only ever sees complete content. If `final` exists, the helper compares its bytes with `data`: equal is a no-op success, different is refused as a determinism defect (never overwritten). The same compare-and-refuse rule is the idempotency rule of the ledger commands (§1), so there is one definition of "already done". Hard links on NTFS through `os.link` [Inferred: documented stdlib behaviour; the helper's own test proves "exists → refuse" and "crash before link → no final file"].

**3. Pre-registration freeze.** `registered` names one prereg hash. Re-registering a different hash is allowed only while no attached grid run has a `cell.launch_intent` in its `events` (read from `runs/`; an absent run directory counts as not started). After that, any change is refused; the operator can only `abandon` (EV-13).

**4. Discrimination records: create-only files outside the task folder.** `bench/discrimination/<task>/<task_version[:16]>-<identity_hash[:16]>-<platform>.json`, committed. **Grain:** one file is exactly one discrimination trial of one task version under one engine identity on one platform. It holds the full task version hash, identity hash and platform, the synthetic run id and grading id, both score sets (metric → value or NOT_RECORDED reason), the declared expected values, and the readiness items that failed (if any). Written with `create_once` (§2a); a second production at the same key is compared with the stored one, and a difference is reported as a determinism defect, never overwritten.
- **Why the record copies score sets (council P1).** `runs/` is gitignored and local, so on a fresh clone the referenced run does not exist, and `bench validate` must still decide readiness. The copy is a snapshot of the scores the referenced grading pass recorded, identified by `(run_id, grading_id)`.
- **Read-time reconciliation (council P1).** When the referenced run exists locally, `bench validate` recomputes the record's score sets from that run's **current** grading pass (ADR-0006's latest-pass rule) and diffs them with the copy. A difference — for example after a re-grade under a fixed grader — fails readiness with `discrimination record stale: <metric> copy <a>, run <b>`, so the copy can never be silently out of date; a new record at the new identity is the fix.

**5. Synthetic cells through the engine (EV-7).** `bench discriminate <task>` plans a run of kind `discrimination` with two cells: combos `synthetic-reference` and `synthetic-naive` (harness `synthetic`, arm `off`, rep 1). The `synthetic` harness profile is a Strategy in the existing profile port: its "driver" copies `tasks/<ID>/oracle/solutions/<reference|naive>/` (per turn for multi-turn tasks) into the working copy and ends the turn. Everything else is the engine's own path: `workspace.task_source`, `workspace.cell_working_copy`, the archiver, the grading pass in a grading copy under `cells_root`. The solution trees are oracle files (B3): never in a measured cell's tree or history.

**6. Rings are committed `bench-matrix/2` files (council Simplifier, adopted).** `bench/rings/<name>.yaml` is an ordinary `bench-matrix/2` file (ADR-0014) with one extra field, `ring: {tag}`, `tag` ∈ {`pilot`, `pack-regression`, `comparison`}, and arms declared by role without a pack (`{id: incumbent}`, `{id: candidate}`, `{id: off}`). There is no separate ring schema. Identity: `tree_hash` of the file (the R-59 c1 recipe). `bench plan --matrix <ring file> --arm <role>=<source>@<commit>…` binds every role to a pack revision (an unbound role is refused) and records `ring: {tag, hash}` in the plan. Results from two ring hashes are never compared (EV-15).

**7. The campaign references, never copies (B8).** Runs, grading passes, ring templates and discrimination records are referenced by id and hash. Gate results, admission inputs, eligibility, power outputs and verdicts are recomputed from the runs on read. The `pilot.passed` row records the decision and the hash of the gate's inputs (the pilot's score-set segment heads), so the decision can be re-verified. `registered` is refused unless the passing pilot covered every (task, combo, harness) of the grid the pre-registration names (council SRE minor).

**8. Hostile code and these records (council S3).** During a hidden check (ADR-0018), agent-written code runs with the operator's rights while these committed records exist on disk; create-only and append-only are application conventions, not OS permissions. Residual, accepted (ADR-0012, ADR-0013). Mitigations: no campaign write is open during a grading pass, and `bench campaign verify` (hash chain, content-address names, `git status` of `bench/campaigns` and `bench/discrimination`) runs after every grading pass of a campaign run and before every campaign command (ADR-0018 §11).

## Alternatives considered

- **Campaign state inside `runs/` (gitignored):** rejected; a campaign outlives and spans runs, and the pre-registration loses its witness.
- **Campaign fields inside each run's plan:** rejected; the pre-registration must exist before the grid's plan, and the campaign spans several plans. The grid plan instead *references* `campaign_id`, `prereg_hash` and `identity_hash`.
- **A SQLite or DuckDB campaign store:** rejected for ADR-0006's reasons (mutable, a second source of truth).
- **Discrimination records inside `tasks/<ID>/`:** rejected; they would change the task version hash they describe.
- **Discrimination by a separate harness-free grader call:** rejected; EV-7 requires the engine's own working-copy and grading path, which is where ORCL-A, HASH-A and SCAN-A lived.
- **A Ring aggregate:** rejected at the specify gate (S-8a); a ring is a tagged matrix template.
- **A separate `bench-ring/1` schema:** rejected at the architecture council (Simplifier); a ring is a `bench-matrix/2` file with a `ring.tag` and role-named arms.
- **`open("x")` for create-only files:** rejected (council D3); a crash mid-write leaves a partial file under the final name.

## Consequences

- **Positive:** one durable model for the whole repo; campaign records are small, reviewable diffs; discrimination reuses the production path, so a grader defect fails readiness rather than a grid.
- **Negative / accepted trade-offs:** current state is "last row" (cheap at tens of rows); the hash chain is tamper-evident, not tamper-proof (single operator, ADR-0012); committed campaign files mean the operator commits after each step (the skill does it).
- **Follow-ups / new risks:** the `synthetic` profile must be excluded from every harness leaderboard and from the profile qualification suite's measured set; `bench status --json` gains a schema-bound campaign view (B2).

## Evidence

- ADR-0006 (physical rules) [Verified]; `plan.task_version_hash` and `tree_hash` (`plan.py:85-112`) [Verified]; `oslock.py` exists [Verified, file listing].
- Spec domain model, aggregates, policies (gate-cleared 2026-10-03).
