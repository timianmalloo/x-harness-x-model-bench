---
id: "adr-0018-hidden-check-harness"
title: "ADR-0018: Property hidden checks run in the grading copy's Job Object, loopback-only, with a schema-bound result on their own pipe"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation E1 (in-process probes), E4 (loopback fault fakes)"
tags: [benchmark, grading, security, trust-boundary, resilience, hidden-check]
links:
  - { to: arch-evaluation-campaign, rel: refines }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: adr-0010-untrusted-cell-output, rel: refines }
  - { to: adr-0012-proportionate-security, rel: depends-on }
  - { to: adr-0013-native-cells, rel: depends-on }
review-by: "2027-10-03"
summary: >-
  One generic property grader runs a task's hidden check (attack probes, fault fakes, diff statistics) inside a
  grading copy under cells_root, in its own Job Object with per-case and outer bounds. Probes prefer in-process
  calls; a listener binds the literal 127.0.0.1 on an OS-assigned port. The check's result comes back only on
  its own stdout pipe in a closed schema, the check tree is hashed before and after, planted secrets are
  synthetic canaries with a scanner-named shape, and seeds derive from (task version, cell, metric) so a
  re-grade reproduces exactly. Boundary B7.
---

# ADR-0018: Property hidden checks run in the grading copy's Job Object, loopback-only, with a schema-bound result

- **Status:** Proposed
- **Date:** 2026-10-03
- **Deciders:** @timianmalloo; authored by Claude Code with the **Security & Identity Architect in Peer Mode from the start**, and the Distributed Systems and SRE lenses
- **Context spec/architecture:** `docs/specs/enterprise-evaluation.md` (EV-2, EV-3, EV-5, EV-6, NFR Security, the STRIDE table, R-E9); ADR-0010 (cell output untrusted on the host), ADR-0012 (proportionate security), ADR-0013 Am. 2 (grading copies under `cells_root`).

## Context

Security tasks attack the agent's deliverable with injection, authorization-bypass and secret-leakage probes; resilience tasks drive it against a fake dependency with a seeded fault schedule. That is agent-written code executed on the host **on purpose**, with hostile inputs, during grading. Today the oracle step already runs agent code natively in a grading copy, in a Job Object with a deadline (ADR-0010 as amended by ADR-0013), so the class of risk is not new. The new parts are: a listener on the host, hostile payloads, planted secrets, a result that must not be forgeable by the deliverable, and parallel checks that must not see each other's traffic (EV-3).

**Trust boundary B7 (STRIDE, Security & Identity Peer Mode):**

| Threat | Control in this ADR | Residual |
| --- | --- | --- |
| Credential exposure to agent code | check and deliverable environments built from the `HOST_ENV` allowlist, never `os.environ` (§9) | — |
| Result forgery through an inherited or duplicated handle | explicit handle list (§10); the check writes once, after the job holds it alone; the grader accepts exactly one document from a live, lone check that then exits cleanly, else `invalid (check tampered)` (§10a) | code injection into the check, directly or through another same-user process: **undetected**, accepted (ADR-0012/0013) |
| Tampering with campaign records during a check | no campaign write open during a check; verify after every pass; git status check (§11) | edits are detected, not prevented |
| Spoofing (another process answers as the fake) | fake binds literal `127.0.0.1`, port 0, asserted with `getsockname`; the deliverable is given that exact URL | a local process could race the port; single-operator host, accepted |
| Tampering (the deliverable alters the check or its result) | result only on the check's own stdout pipe; deliverable stdio redirected to files; the check tree hashed before and after; a mismatch is NOT_RECORDED `check tampered` | the deliverable has the operator's rights and could, in principle, defeat both (accepted, ADR-0013 A10) |
| Repudiation | per-case outcomes and durations in the grading evidence; seeds recorded | — |
| Information disclosure | planted secrets are synthetic canaries `BENCHCANARY-<task>-<hex>`, registered in the egress scanner as class `task canary` (R-E9); never real credentials | none beyond today's |
| Denial of service | per-case wall bound inside the check; outer bound = `grading_step_timeout`, then `TerminateJobObject` | — |
| Elevation of privilege | none added: the deliverable runs as the operator, as the cell did (owner ruling, ADR-0013) | accepted |
| Network reach (spec *assume:*) | no probe or fake addresses anything but the in-process app or `127.0.0.1`; the check declares no other host | a deliverable that binds `0.0.0.0` is LAN-reachable for the check's duration (accepted; detection is a follow-up) |

## Decision

**1. One generic runner, task-authored checks.** A property task's oracle holds `oracle/check/` with an entry point and a declared case list (ids, property, kind: probe | fault | static). The `property` grader copies the archived final tree (or a named snapshot, ADR-0015) and the check into a grading copy under `cells_root/grading/<gid>/<cid>/property/` (ADR-0013 Am. 2), then runs the entry point under the task's pinned interpreter, in a new Job Object with the outer deadline. The check starts the deliverable as its own child (so it is in the same job), only through `bench_check.spawn_deliverable` (§9, §10), with stdio redirected to files in the copy.

**2. In-process first.** Where the deliverable exposes an importable application (for example a WSGI/ASGI app or a function), probes call it in process: no socket at all. A listener is used only when the deliverable's interface is a process (resilience fakes always are).

**3. Loopback by construction.** Every listener a check opens binds `("127.0.0.1", 0)` and asserts `getsockname()[0] == "127.0.0.1"`; the OS-assigned port goes to the deliverable through its declared configuration (environment or argument, fixed by the task contract). Parallel checks therefore never share a port (EV-3), with no port allocator. A deliverable that must listen is told `127.0.0.1` and a port, also through its declared configuration.
- *assume:* binding `127.0.0.1` raises no Windows Defender Firewall prompt and loopback traffic is not filtered. **Confirm:** spike S-LB (procedure in `docs/architecture-evaluation-campaign.md`). **Breaks if false:** an unattended grading pass shows a modal dialog (the bind still succeeds); mitigation: a pre-created allow rule for the pinned interpreter, checked in preflight. Until S-LB passes, only in-process probes are admitted (phase E1).

**4. Result channel, schema-bound.** The check writes exactly one JSON document to its stdout: `{schema, cases: [{id, outcome, duration_ms}], measures: {<metric>: <int or decimal string>}}`, with `outcome` ∈ {`blocked`, `exploited`, `passed`, `failed`, `timeout`} and case ids from the declared list only. The grader validates it; a malformed document is NOT_RECORDED `check output invalid` (a grading-environment failure, caught by the pilot gate, EV-14). A document that breaks the write-sequencing and single-document rules of §10a is NOT_RECORDED `invalid (check tampered)`, never a score. No response bodies or free text reach the ledger; per-case details go to the grading evidence file, egress-scanned before any judge or report use (US-47).

**5. Bounds.** Each case has a declared wall bound inside the check: a deliverable that hangs is a **measured** failure (`timeout`), recorded by the check (EV-3). If the outer bound fires, the check itself failed to bound: the job is terminated and the metric is NOT_RECORDED `check exceeded its bound` — never a 0 (IO1).

**6. Determinism (US-26, EV-2).** Probe payloads are fixed sets; fault schedules are driven by `seed = int(sha256(task_version | cell_id | metric_id)[:16], 16)`, recorded in the evidence. A re-grade of one archive reproduces every case outcome; a test grades one archive twice and compares.

**7. A deliverable that does not build or start** yields the primary metric 0 with reason `deliverable did not build` (EV-1), decided by the check's declared build/start step, not by the outer bound.

**8. Toolchain and platform (council E1).** Checks are Python stdlib plus the task's own pinned toolchain; a declared container runtime or Linux-only tool fails `bench validate` (EV-7, EN1). Check *content* is written to run on Windows and macOS (the task contract, ADR-0013 Am. 1), but the **runner is Windows-only today**: it relies on a Win32 Job Object for the outer bound and on the Win32 handle list (§10). The macOS primitive — a process group with confirmed termination, and POSIX `close_fds` — is an explicit follow-up with the engine's macOS port, as in ADR-0013 §5.

**9. Environment allowlist for the check and the deliverable (council S1, Security hard veto).** The check process **and** the deliverable child it spawns get an environment built from the same explicit allowlist every grading step already uses — `HOST_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP")` (`grade/correctness.py:48`, built at `:97`; the same tuple in `grade/mutation.py:38`, built at `:195`), plus the task's declared toolchain variables (`DOTNET_HOST_ENV`-style, `correctness.py:49`) and the check's own declared variables (host, port, seed). Never inherited `os.environ`. So `HB_CLAUDE_OAUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, `GH_TOKEN` and any `ANTHROPIC_*` value cannot reach agent-written code. The allowlist is one constant moved to a shared grading module so the three graders cannot drift (DM7). **Test (red first):** `test_property_check_env_excludes_credentials` sets those four names in the grader's environment, runs a fixture check whose fixture deliverable writes its own `os.environ` keys to its evidence file, and asserts that neither the check's nor the deliverable's environment contains any of them.

**10. The deliverable cannot inherit the result pipe (council S2, Security hard veto).** The check never spawns the deliverable directly. It calls a bench-provided stdlib helper, `bench_check.spawn_deliverable` (copied into the grading copy beside the check), which creates the child with an **explicit, non-inheritable handle list** containing only the child's own three stdio handles, redirected to files in the copy — the same discipline as ADR-0013's adapter spawn (suspended, explicit handle list, then resumed inside the job). On Windows it uses `subprocess.Popen(close_fds=True, startupinfo=…lpAttributeList={"handle_list": [...]})`, and the check's stdout handle is never in the list. The helper also applies §9's environment, so a task author cannot get either wrong. **Test (red first):** `test_deliverable_cannot_write_result_pipe`: a fixture deliverable that tries every inherited handle it can enumerate, and any handle value passed to it, to write a forged result; the grader's parsed result must equal the honest check's result, and the fixture must record that no write succeeded.

**10a. Write sequencing and single-document acceptance (council S2 re-check).** The handle list stops *inheritance* only. A same-user deliverable can still `OpenProcess` the check and `DuplicateHandle` its stdout — no privilege and no file write, so the check-tree hash never sees it — and write a schema-valid document that flips `blocked` to `exploited` or back, the security task's primary signal. Closing that window needs no new primitive:
- **(a) The check writes once, last.** The check keeps every outcome in memory. It performs its **one** result write only after the deliverable and every job-tracked descendant have exited, confirmed by the grading Job Object's process list holding the check alone (`QueryInformationJobObject`, the primitive spike N2 already uses for the active-process count). `bench_check.write_result` enforces this; a check never writes to stdout otherwise.
- **(b) The grader accepts exactly one document, written by a live, lone check.** The grader owns the job handle and the check's process handle. It accepts the result only if **all** hold: the pipe carried exactly one JSON document and no trailing bytes; when that document's first byte arrived, the grader's immediate job query showed the check alive and alone in the job; the check then exited by itself with the expected exit code, after the document arrived (the check's kernel-recorded exit time from `GetProcessTimes` on the grader's own handle, which the deliverable cannot rewrite); and the outer bound did not fire. Anything else — a second document, a document that arrived while another process was in the job or after the check had exited, a killed or abnormally exited check, trailing bytes — is classified `invalid (check tampered)`: the metric is NOT_RECORDED with that reason, never a score, and the pilot gate names it (EV-14).
- **Why this closes the forgery:** to write, a forger must be alive, so a forged document arriving while it runs fails the "alone" test. If it writes and exits first, the honest check later writes its own document, so there are two documents. If it kills the check and then writes, the document arrives after the check's exit time. If it kills the check before the check writes, the exit is abnormal, or the expected code has no document after it.
- **Tests (red first):** `test_forged_result_via_duplicated_handle_is_tampered`: a fake deliverable duplicates the check's stdout handle and writes a forged schema-valid `blocked` document; the cell must record `invalid (check tampered)`, never `blocked`. `test_check_killed_before_write_is_tampered`: a fake deliverable terminates the check, with the check's expected exit code, before its write; same result. Two more variants in the same file: forge, then exit before the check writes (two documents); forge, then kill the check (document while not alone, or after exit). `test_forged_write_racing_deliverable_exit_yields_two_documents`: a forger writes and exits so fast the job query could see the check alone; the check's own later write makes a second document and the grader records `invalid (check tampered)` -- the race defence is asserted, not left emergent (Security round-3 nit).
- **Residual, stated honestly.** Killing the check and faking its exit code is **distinguishable**: the grader sees the exit on its own process handle, and an exit that precedes the document, or a document that arrived while the forger was in the job, is refused, so faking the code alone does not help. What remains **undetected** is in-process tampering: a same-user deliverable that injects code into the check itself (for example `CreateRemoteThread` or memory writes into the check) can change the outcomes the check holds in memory before its single honest-looking write, and can do it from a process outside the job if it first injects into another of the operator's processes (breakaway is never allowed, so it cannot simply leave the job). That requires deliberate process-injection tooling aimed at this bench. It is accepted under ADR-0012 and ADR-0013 (an agent runs with the operator's rights), and it is **undetected**, not merely unprevented. Upgrade if ever suspected: run the check as a different, low-rights local user, which `OpenProcess` across users would refuse.

**11. Hostile code beside durable records (council S3).** While a check runs, agent-written code runs with the operator's rights while `bench/campaigns/` and `bench/discrimination/` exist on disk. "Create-only" and "append-only" are application conventions, not OS permissions: the deliverable *could* edit them. Residual, accepted (ADR-0012, ADR-0013). Cheap mitigations, adopted: (a) a grading pass never runs while `campaign.lock` is held, and `bench campaign` refuses while a campaign run's `grade.lock` is held, so no campaign write is open during a check; (b) after every grading pass of a campaign run, and before every `bench campaign` command, `bench campaign verify` checks the campaign ledger's hash chain, that every content-addressed file's name equals its hash, and `git status --porcelain bench/campaigns bench/discrimination` (a committed file changed outside a campaign command is refused, naming the file); (c) the git history of these committed records is the witness of last resort.

**12. Bounds per adapter, and host sleep (councils Patterns, R3).** Per-case wall bounds are declared per (task, interface): `in-process` and `loopback` cases have separate declared bounds, because loopback adds process start and socket latency. The outer bound is `grading_step_timeout`. A grading step whose wall clock contains a host suspend gap (the `SleepDetector` rule of `docs/notes/spike-a9-host-sleep.md`, applied to the grading step) is NOT_RECORDED `host suspended` and re-run by the next grading pass, never scored as a timeout; a seeded-suspend test covers it.

## Alternatives considered

- **Run probes from the bench process against the deliverable:** rejected; the bench process would hold a socket to untrusted code and would need the task's toolchain.
- **A fixed port range per grading slot:** rejected; port 0 gives isolation by construction with no allocator.
- **Read the result from a file in the grading copy:** rejected; the deliverable can write it.
- **A container or VM for checks:** rejected (EN1, ADR-0013 Am. 1).
- **Detect `0.0.0.0` binds by enumerating listening sockets:** deferred; not stdlib on Windows (needs `netstat` parsing or a dependency); recorded as the upgrade if a LAN exposure is ever observed.

## Consequences

- **Positive:** one runner for every property; checks are reproducible and bounded; a result written through an inherited or duplicated handle, or after the check was killed, is refused as `invalid (check tampered)` (§10a); parallel checks are isolated by the OS.
- **Negative / accepted trade-offs:** the deliverable still runs with the operator's rights and could defeat tamper detection or edit the campaign records (§10, §11: detected, not prevented); task authors must expose a configuration point for host and port; the runner is Windows-only until the port (§8).
- **Follow-ups / new risks:** spike S-LB; probe N4 (grandchildren stay in the job); the egress scanner's `task canary` class; the task contract fields in `tasks/README.md` (design-slice); the macOS runner primitive; the two red-first tests of §9 and §10 gate phase E1.

## Evidence

- ADR-0010, ADR-0012, ADR-0013 Am. 2 [Verified, read 2026-10-03]; `tests/fixtures/acp/scripted-user/probe_server.py:140` bound `127.0.0.1` on this host (S-04b) [Verified that it binds; no firewall observation recorded].
