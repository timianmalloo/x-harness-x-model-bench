---
id: "adr-0005-egress-control"
title: "ADR-0005: Cells reach only model APIs; benchmark model calls pass one egress gate"
type: adr
status: draft
owner: "@timianmalloo"
phase: "phase 2 onward (recorded, not enforced, in phase 1)"
tags: [benchmark, security, network, privacy]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
review-by: "2027-09-23"
summary: >-
  Cell containers sit on an internal Docker network whose only way out is an allowlisting egress proxy
  for the vendor model and auth hosts. Every call the benchmark itself makes to a vendor (judges,
  summaries, matcher) and every report publication passes one egress gate that scans for secrets and
  personal data first.
---

# ADR-0005: Cells reach only model APIs; benchmark model calls pass one egress gate

- **Status:** Proposed
- **Amended by ADR-0013 (2026-09-23):** the per-cell Docker network and egress proxy are superseded for authored tasks: cells use the host network (already optional under ADR-0012). The scan-before-egress rule for the benchmark's own sends (US-47) is unchanged.
- **Date:** 2026-09-23 (revised after council round 1)
- **Deciders:** @timianmalloo; authored by Claude Code for the architect council
- **Context spec/architecture:** `docs/specs/harness-bench.md` US-47, US-48, US-49, C9

## Context

A cell must reach its model API and nothing else: no package registries (ADR-0004), no git remotes or `gh` (US-49), and no exfiltration target (US-48). The benchmark itself sends artifacts to judge and summary vendors, and those payloads can carry agent-written text, the operator's email (spike 1.5) or secrets. US-47 requires one scan before every egress. Nothing here has been spiked: containers so far used Docker's default network.

## Decision

- **Cell network.** Each cell has its own internal Docker network with no default route (ADR-0001). The only way out is an off-the-shelf allowlisting proxy (tinyproxy or squid, configured only, no bench code; the Egress Gateway pattern). It forwards only to the harness profile's vendor model API and auth hosts, and refuses private, link-local and host addresses after DNS resolution. IPv6 is off. Name resolution from the cell happens only through the proxy, so DNS lookups of other names fail. Every cell records its network mode, and the proxy's per-cell connection log is archived.
- **Phase rule (fail closed).** Phase 1 may run `unrestricted` only for operator-authored tasks and no hostile fixture; `bench run` refuses `unrestricted` for anything else. From phase 2, a missing or failing proxy ends the cell `blocked (network)`. It never falls back to `unrestricted`.
- **Egress gate.** Every outbound call the bench makes goes through one module, `egress`, and no other code path may open a vendor connection (checked by an import lint). It:
  - scans the payload for key patterns, token prefixes, the operator's email, username and home path, and the configured canaries;
  - quarantines on a hit and returns NOT_RECORDED (`withheld: sensitive content`);
  - records the payload hash and the destination.

  The same gate runs before a report is published (phase 4, when the complete report exists). A local report file is not egress (spec NG2). Credential exact-value hits (ADR-0003) quarantine the whole cell.

## Alternatives considered

- **Default Docker network:** rejected as the end state. It gives cells the whole internet (registries, remotes, exfiltration). Accepted only for phase 1, and recorded.
- **`--network none`:** rejected. Cells need their model API.
- **Per-call scanning inside each grader:** rejected. Several code paths each re-implementing a scan will drift. One gate, one test.

## Consequences

- **Positive:**
  - US-47, US-48 and US-49 hold by network construction plus one audited gate.
  - The proxy log is evidence of what each cell contacted.
- **Negative / accepted trade-offs:**
  - Allowlists must track vendor host changes. A missing host blocks a cell, which fails loudly as `blocked (network)`.
  - TLS is not intercepted, so the proxy sees hosts, not payloads.
- **Residual (accepted in writing):** an agent could send data through an allowlisted vendor host using a key of its own. Only TLS interception could close that, and it is out of scope. A revocable, spend-capped benchmark credential (ADR-0003) is what makes this acceptable.
- **Follow-ups / new risks:**
  - Spike (phase 2 gate): each harness through the proxy inside Docker Desktop. Auth refresh and model calls pass. These fail: `git push`, a package install, a lookup of an arbitrary DNS name, a connection to `host.docker.internal`, and one to a private address.

## Evidence

- No spike yet [Flagged].
- The spec's hostile-fixture criteria (US-48, US-49) are the acceptance tests.
