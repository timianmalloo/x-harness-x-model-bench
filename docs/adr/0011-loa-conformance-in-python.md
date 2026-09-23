---
id: "adr-0011-loa-python"
title: "ADR-0011: LOA conformance criteria mapped to Python, with a control per criterion"
type: adr
status: draft
owner: "@timianmalloo"
phase: "phase 1 onward"
tags: [benchmark, loa, conformance, testing]
links:
  - { to: arch-harness-bench, rel: refines }
review-by: "2027-09-23"
summary: >-
  The LOA conformance criteria C1–C11 are written for .NET analyzers; this Python codebase meets their
  intent through named lints and tests, one per criterion, run in CI. Two recorded deviations: cells act
  as a benchmark principal (not the requester's), and phase 1's unrestricted network is a time-boxed,
  fail-closed exception.
---

# ADR-0011: LOA conformance criteria mapped to Python, with a control per criterion

- **Status:** Proposed
- **Date:** 2026-09-23
- **Deciders:** @timianmalloo; authored by Claude Code for the architect council (Enterprise Architect item 4, round 1)
- **Context spec/architecture:** `docs/architecture.md` LOA conformance; `layered-optimized-architecture.md` C1–C11

## Context

LOA C1–C11 are phrased as .NET analyzer checks (`[CapabilityTier]`, `BudgetContext`, `ReceiptLedger` …). The bench is Python. LOA requires a deviation to be documented, and a mapping with no control behind it is a memoir.

## Decision

| Criterion | Python control (CI) |
| --- | --- |
| C1 tier annotation | Every gateway method declares its tier in a typed request. A test enumerates gateway call sites and fails on a missing tier. |
| C2 budget propagation | Gateway and driver entry points take a `Budget` argument, checked by a type-checker rule and a test that the run's spend cap stops calls. |
| C3 receipt emission | Every gateway call writes a `model_calls` row with principal `gateway`. A test fails if a call produced none. |
| C4 typed boundaries | `bench status --json` and gateway I/O are validated against schemas. A test plants free text in cell output and asserts it never appears in status (B2). |
| C5 side-effect protection | No model output triggers a side effect in the bench. An import-boundary lint forbids the engine, driver and archiver from importing the gateway. |
| C6 idempotency keys | Launch intents (ADR-0007) and cache keys (ADR-0006). Kill-in-each-state tests assert at-most-once. |
| C7 fallback declaration | The gateway has no fallback (`NOT_RECORDED`, ADR-0009). The egress proxy fails closed from phase 2 (ADR-0005). A test asserts both. |
| C8 pattern naming | Each module's docstring carries `Pattern: <name>`. A test checks the list in `docs/architecture.md` against the modules. |
| C9 anti-pattern absence | Import lint: no model call on the scheduling path, and no free text across B2 (tests for C4 and C5). |
| C10 audit completeness | `bench verify` checks every chain and that every cell has intent, outcome and archive events. |
| C11 principal propagation | Every cell records its credential kind and profile. **Deviation:** cells act as a benchmark principal, not as the requesting principal, which inverts P11 on purpose: a measured agent must not act as the operator. |

**Profile qualification suite.** One versioned suite runs for every harness profile and CLI bump. It combines the follow-ups of ADR-0002, 0003, 0004 and 0008:
- an ACP contract fixture;
- permission refusal (web fetch and an out-of-profile tool refused);
- a native-record reader fixture;
- a served-model check with at least one call;
- a canary per configuration class (US-13).

Any failure blocks the bump.

**Recorded deviation 2:** phase 1 runs cells with an unrestricted network, only for operator-authored tasks (ADR-0005). It expires when phase 2 starts.

## Alternatives considered

- **Port the .NET analyzers:** rejected; there is no Python host for them.
- **Treat the mapping as prose:** rejected; it has no control.

## Consequences

- **Positive:**
  - LOA intent is enforced by CI.
  - Churn in harness builds is caught by one suite.
- **Negative / accepted trade-offs:** the suite needs real credentials for the served-model check, so it runs locally before a profile bump, not in hosted CI.
- **Follow-ups / new risks:** none beyond the phase-1 tests.

## Evidence

- `layered-optimized-architecture.md` C1–C11, P11.
- Enterprise Architect council round 1.
