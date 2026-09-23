---
id: "adr-0012-proportionate-security"
title: "ADR-0012: Proportionate security for a single-operator local benchmark tool"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, security, owner-ruling]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: adr-0001-cell-containers, rel: refines }
  - { to: adr-0003-harness-profile, rel: refines }
  - { to: adr-0005-egress-control, rel: refines }
  - { to: adr-0010-untrusted-cell-output, rel: refines }
  - { to: spec-harness-bench, rel: refines }
review-by: "2027-09-23"
summary: >-
  Owner ruling: harness-bench is a local tool run by one trusted operator on their own machine; git
  is a mechanism, not an entry point. The only adversary is the agent under test, and security controls
  are kept where they protect result validity or keep an agent from damaging the machine by accident.
  Provenance checks, the egress proxy requirement, SBOM/CVE gates and most negative security tests are
  dropped or made optional; third-party tasks may run on the operator's subscription logins.
review-suggested: []
---

# ADR-0012: Proportionate security for a single-operator local benchmark tool

- **Status:** Proposed. **Owner ruling, 2026-09-23.** It supersedes the parts of ADR-0001, ADR-0003, ADR-0005 and ADR-0010 listed below.
- **Amended by ADR-0013 (2026-09-23):**
  - the kept container controls ("Cells in containers…", "Grading runs in the task's container image", and the container-configuration test for US-48 and US-49) are dropped: each cell works in its own working copy, and nothing more (owner ruling, ADR-0013);
  - goal 2, "the machine", becomes acceptance with detection. Owner: "that's a risk that I am not worried about."
- **Deciders:** @timianmalloo.
- **Context:** the spec's and architecture's security requirements were written as if the tool served untrusted users or untrusted task sources. The owner ruled otherwise:
  - "security needs to be reduced in weight. This is a benchmark tool to be run locally on a machine by ME; git is just a mechanism here, not an entry point."
  - "third party task risk is not a high risk: I am willing to accept such a risk."

## Threat model (the ruling)

- **Operator:** one person, trusted, on their own workstation. Git, the task folders, the plan and the CLI are the operator's own tools, not attack surfaces.
- **Adversary:** the agent under test. It is not malicious, but it can do surprising things: write anywhere it can reach, run commands, edit tests, rewrite its own records.
- **What matters:**
  1. Result validity: no agent can see hidden tests, reach another cell, or be scored against the wrong model or build.
  2. The machine: no agent can damage the operator's files, credentials or other repos by accident.
  3. Nothing sensitive in anything the operator shares (a published report).

## Decision

**Kept** (validity, or accidental damage):

| Control | Why kept |
| --- | --- |
| Cells in containers with only the workspace and harness home mounted, non-root, no Docker socket (ADR-0001 core) | Symmetric containment is a validity requirement (US-14). No user config enters cells (US-13). The operator's files are safe from accidental writes. |
| Hidden tests and oracles never in the workspace, the git objects, or the image build context | Validity (US-3, US-8) |
| Pinned CLI builds, adapter lockfile, image digests (US-12, US-50 pins) | Reproducibility |
| Cell repos have no git remote; no `gh` in the image | Stops an agent pushing by accident; costs nothing |
| Static symmetric permission profile, no model approvals (ADR-0004) | Validity (US-14) |
| Grading runs in the task's container image | The graders need the task environment anyway (the build and tests run there) |
| Host git runs with `-c core.fsmonitor=false -c core.hooksPath=<empty>` | One line; avoids running an agent-written hook by accident |
| Credential exact-value check on a **published** report and on anything sent to a judge vendor | Nothing sensitive leaves the machine by accident (US-47, reduced scope) |
| Typed `bench status --json` | Good design and a stable skill contract; strictness tests reduced |

**Dropped or made optional:**

| Item | Now |
| --- | --- |
| Operator-authored provenance, git-author checks, the task allowlist (ADR-0003 credential-kind rule; phase-1 design T-PROV) | Dropped. Any task may run on the operator's subscription logins (owner accepts third-party task risk). The report header still names the credential kind. |
| Egress proxy as a requirement (ADR-0005 cell network) | Optional hardening. Cells use a per-cell Docker network with normal outbound access. Network mode is recorded per cell. Package installs are still avoided by restoring dependencies before the clock (a validity rule, ADR-0004). |
| Hostile-fixture tests (US-48, US-49 negative tests), canary exfiltration tests | Dropped as gates. US-48 and US-49 become design properties of the container (no mounts, no remote), checked by one container-configuration test. |
| SBOM and CVE scanning gate (ADR-0001) | Optional; not a gate. |
| Read-only root filesystem, seccomp tuning, per-cell disk quota enforcement, TCP-daemon check | Optional. The kept core (non-root, no socket, two mounts, resource limits) is enough for accidental damage. |
| Exact-value scan of every fact row, log, status and in-process string (design-gate item) | Reduced to published reports and judge payloads |
| "Bench-minted ids only" status enforcement (design-gate item) | Dropped; the typed schema is kept |
| Native records as hostile input | Accepted: an agent could corrupt its own records. The effect is on that cell's validity, which the served-model and at-least-one-call checks catch in the common cases. Parsers are still bounded so a bad record cannot crash grading. |

## Consequences

- **Positive:**
  - Phase 1 and phase 2 lose most of their security machinery and tests, and focus on validity.
  - The third-party smoke tasks (A1, C1, E1) can run on subscriptions.
- **Negative / accepted (owner):**
  - An agent under test can reach the internet and could send data out, including the subscription token in its own home.
  - A third-party task's content runs with the operator's subscription.
  - Both are accepted by the owner. The report header states the credential kind and network mode.
- **Spec amendments:**
  - US-47: scope reduced to published reports and judge payloads.
  - US-48 and US-49: satisfied by container configuration, without hostile-fixture tests.
  - US-50: SBOM/CVE optional; pins kept.
  - The ADR-0003 rule "operator subscription only for operator-authored tasks" is withdrawn.

## Evidence

The owner's messages of 2026-09-23 (quoted above).
