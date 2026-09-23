---
id: threat-model
title: "Threat Model"
type: threat-model
status: draft
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [security, threat-model]
links:
  - { to: arch-harness-bench, rel: documents }
  - { to: design-phase1-walking-skeleton, rel: documents }
  - { to: design-run-lifecycle-model, rel: documents }
  - { to: adr-0012-proportionate-security, rel: depends-on }
review-by: "2027-03-22"
review-suggested: []
summary: >-
  harness-bench is a local benchmark run by one trusted operator (ADR-0012), so security is scoped to
  result validity and accidental damage to the host or the owner's subscription credentials. The
  boundaries that matter are agent ↔ host, agent ↔ hidden oracle and credential ↔ published report;
  third-party task risk and everything outside that scope are accepted by the owner.
---

# Threat Model

*The repo-level rollup of every component's adversarial analysis (STRIDE-lite). **The register in
section 2 is generated**; refresh it with:*

```bash
python3 docs/ai-forward-pack/scripts/docs-graph.py rollup --heading "Adversarial analysis (STRIDE-lite)" --type design
```

*The rollup prints links relative to `docs/`; they are prefixed with `../` when pasted here.*

## 1. System trust-boundary map

One operator, one Windows workstation, Docker Desktop (WSL2). Each cell runs in its own hardened container (ADR-0004).

```mermaid
flowchart LR
  subgraph Host["Host (trusted: the operator)"]
    Engine["bench engine\n(single writer)"]
    Runs["runs/&lt;id&gt;\nledger + archives"]
    Creds["subscription logins\n(harness homes)"]
    Report["report HTML"]
  end
  subgraph Cell["Cell container (less trusted: the agent)"]
    Agent["harness + model"]
    WS["workspace mount"]
  end
  Oracle["hidden tests / oracle"]
  Engine -- "B1 launch, kill" --> Cell
  Creds -- "B1 per-cell copy" --> Cell
  Cell -- "B4 archive" --> Runs
  Oracle -. "B2 never mounted" .- Cell
  Runs --> Report
  Report -- "B5 publish" --> Shared["shared report"]
```

| # | Boundary | Less-trusted side | More-trusted side | Owning design |
| --- | --- | --- | --- | --- |
| B1 | Agent ↔ host | Agent in the cell container | Host files, Docker, credentials | design-phase1-walking-skeleton |
| B2 | Agent ↔ oracle | Agent | Hidden tests and oracle | design-phase1-walking-skeleton |
| B3 | Agent ↔ git remote | Agent | The owner's remotes | design-phase1-walking-skeleton |
| B4 | Cell output ↔ host git | Archived workspace | Host git tooling | design-phase1-walking-skeleton |
| B5 | Credential ↔ published report | Report readers | The owner's tokens | design-phase1-walking-skeleton |
| B6 | TLA+ tools download ↔ CI | GitHub release asset | CI runner, check result | design-run-lifecycle-model |

## 2. Threat register (generated — see command above)

| source | Boundary | Threat | Disposition | Control | Test |
|---| --- | --- | --- | --- | --- |
| [design-phase1-walking-skeleton](../design/phase1-walking-skeleton.md) | Agent ↔ host | E/T: accidental damage to host files or credentials | mitigate | Container: non-root, no Docker socket, exactly two mounts, resource limits | T-HARD-config (`inspect`: User ≠ root, Mounts = {workspace, home}, the home mount's Source is the cell's own copy under the cells root and never the host profile, no socket, limits set, Privileged = false), run on the containers the engine actually launches, cells and grading alike |
| [design-phase1-walking-skeleton](../design/phase1-walking-skeleton.md) | Agent ↔ oracle | I: read hidden tests | mitigate | Allowlisted build context; workspace builder never reads `tests/` or `oracle/` | T-WS-oracle, T-IMG-oracle |
| [design-phase1-walking-skeleton](../design/phase1-walking-skeleton.md) | Agent ↔ git remote | T: push by accident | mitigate | No remote in cell repos; no `gh` in the image | T-WS-noremote |
| [design-phase1-walking-skeleton](../design/phase1-walking-skeleton.md) | Cell output ↔ host git | E: run an agent-written hook | mitigate | `gitsafe.py` flags | T-B6-fsmonitor |
| [design-phase1-walking-skeleton](../design/phase1-walking-skeleton.md) | Credential ↔ published report | I: a token in a shared report | mitigate | Exact-value check before `bench report --publish`. The value set is built at publish time from the host's current credential files and every credential file in the archived cell homes (tokens rotated during a cell), each also in base64 and URL-encoded forms | T-SEC-report (positive controls: a planted host token, and a rotated token present only in an archived home, are both found, and publishing refuses) |
| [design-phase1-walking-skeleton](../design/phase1-walking-skeleton.md) | Everything else in the former analysis | — | accept (owner) | ADR-0012 | — |
| [design-run-lifecycle-model](../design/run-lifecycle-model.md) | The tla2tools.jar download | T: a substituted jar changes check results or runs code in CI | mitigate | Pinned release URL + sha256; delete on mismatch | `test_corrupted_tla_jar_is_deleted_and_refused` |
| [design-run-lifecycle-model](../design/run-lifecycle-model.md) | CI runner executing the jar | E: third-party code in CI | accept (ADR-0012) | Upstream TLA+ tools, pinned by hash; CI job permissions `contents: read` | — |

<!-- rolled up from 2 artifact(s) by docs-graph.py rollup on 2026-09-23 -->

## 3. Accepted-risk register

| Boundary / threat | Accepted by | Rationale | Residual risk | Revisit when |
| --- | --- | --- | --- | --- |
| Third-party task content (hostile repos, prompt injection in task files) | @timianmalloo (ruling, 2026-09-23) | Single trusted operator running chosen tasks locally; ADR-0012 | An agent is steered by task text; contained by B1 | Tasks from sources the owner has not chosen, or the tool gets a second operator |
| Supply-chain provenance (SBOM, image and package allowlists) | @timianmalloo (ADR-0012) | Pinned versions and digests suffice for a local tool | A compromised pinned upstream | The tool is distributed to other users |
| CI executing the pinned TLA+ jar | @timianmalloo (ADR-0012) | Upstream tool, hash-pinned; read-only job token | A compromised upstream release matching the pin is not credible | The pin changes |
| Git as an entry point | @timianmalloo (ruling, 2026-09-23) | Git is a mechanism here, not an entry point | — | The tool accepts runs or tasks from a remote |

## 4. Cross-cutting controls

- **Container hardening profile** (ADR-0004): non-root, no Docker socket, two mounts, resource limits. B1, B2, B3.
- **Per-cell harness homes** (ADR-0005): each cell gets a copy of the subscription login; copies are deleted after use. B1.
- **Exact-value credential check** before publishing. B5.
- **Pinned digests and hashes** for images and tools. B6.

## 5. Gaps and flagged unknowns

- A3: OAuth refresh rotation may invalidate the host login when a cell refreshes a copied token (probe in the phase-1 design).
- Phase-2 designs (the Copilot profile, stop and decisions) have no analysis yet; they add rows when designed.
