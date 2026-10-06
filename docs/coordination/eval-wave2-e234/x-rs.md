---
id: brief-eval-x-rs
title: "Brief X-RS: resilience tasks RS1, RS2 (E4) - waits on SP-LB's result; ready after X-LB"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-property-tasks, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-RS authors tasks/RS1 and tasks/RS2 to W1-L section 9 (provisional on SP-LB and X-LB) with Erratum 1, on Claude Sonnet. Starts when SP-LB's operator run has passed and merged; ready after X-LB."
---

# X-RS: resilience tasks RS1, RS2

> **WAITS** on SP-LB's operator run (`docs/notes/spike-s-lb-loopback.md`: not run). W1-L §9 is provisional on it; start only when its result has passed and merged. Until X-LB lands, develop `check.py` against a stand-in listener (W1-L §4 seam 3).
>
> **Unblocked (Coordinator #44, 2026-10-06):** the operator accepted SP-LB for this host ("B-2 / SP-LB closed: accepted for this host"; ADR-0018 Amendment 2). Authoring may start once `coord/eval-c44-p4b` is merged; the `ready` flips still wait for X-LB1's join. Compile `al-01M48WS6GT9JB35Z2K8XBQ8DFP` (session `x-rs-e1e4`, skill `new-bench-task`).

**Harness** Claude Code sub-agent · `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **session** `x-rs-e1e4` · **branch** `build/eval-x-rs` · **budget** 200 calls · 200k · 3 h per task · **skill** `/new-bench-task`.

**Design:** W1-L §2, §3, §5, §9 (9.1 check shape, 9.2 RS1 prometheus_client, 9.3 RS2 structlog), §15, **Erratum 1**; W0 rev 6.6 §2, §3 (the `PropertyCheck` contract, the E4 listener on `127.0.0.1` with `SO_EXCLUSIVEADDRUSE`), §11 (HB-CHK-005).

## Owned paths
`tasks/RS1/**`, `tasks/RS2/**` (including `oracle/check/{check.py,cases.yaml}`), and their `bench/bom.yaml` entries only.

## Acceptance items (RV-TA W1-L rev 2; W1-L Erratum 1)
1. **First commit, R2-5:** state the isolation of RS1's hidden tests and cases (a fresh process per hidden test and per case, or a `cacheerror` flag that H-3/H-4 cannot set) in `task.yaml` or `oracle/evidence.md`. The first variant run is the measurement: `cacheerror` must pass the hidden tests and flip only the `result` clause; record the measured outcome.
2. **First commit, R2-6:** write `g-ordering`'s fault schedule (for example three 503s) and re-trace all seven RS2 variant rows against it.
3. **R2-1:** names to the charset (`noretry`, `notimeout`, `retry5`, `retry4xx`, `retryforever`, `nokey`, `keyperattempt`, `batchidattempt`, `clearearly`, `requeuetail`, `attempt3s`, `cacheerror`); one `VARIANTS` literal; check-based, so `flips` and `clauses` hold case ids. A test loads each `variants.py` through W1-E's reader (in this session if X-E has joined, else in the `ready` follow-on).
4. **R2-7:** one sentinel stub per task and `test_<id>_stub_fails_every_hidden_test`.
5. **R2-4:** RS needs no new discriminate code; the `ready` follow-on runs `bench discriminate` through X-LB's loopback check. If it cannot, that is a request to the Coordinator, not a local workaround.
6. W1-L assume A3 (hidden tests may use loopback sockets in the grading copy) is confirmed by a stub-and-reference run under the real `correctness.grade`, or the hidden tests move to `unittest.mock`.

## Exit
E1 README §3 join gate. Report per E1 README §4 plus the per-task state.
