---
id: review-eval-sec-w1f
title: "Security & Identity review of W1-F: hidden-check runner and property grader (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, security, evaluation-campaign, wave-1, w1-f]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
  - { to: review-eval-sec, rel: refines }
review-by: "2026-10-17"
summary: >-
  Security & Identity gate on W1-F (design/eval-property-grader, 441da4ba and e41289a2) against W0 rev 2.
  Both carried-over conditions are met in the design text; the forged-document fixture is named as a red test but the
  spike scripts are not committed and no positive control is named. PASS WITH CONDITIONS, 8 findings.
---

# Security & Identity review of W1-F (rv-sec-w1f-e1e4)

PERSONA: security-identity-architect · MODE: Adversary · TIER: T2. Severity: blocking / major / minor. Confidence: Verified (observed in a file) / Inferred (reasoned; the confirming check is named).

## W1-F: `docs/design/eval-property-grader.md` (branch `design/eval-property-grader`, 441da4ba, e41289a2)

Trust boundaries named by the design: B7a to B7d and B6. I agree with the set. Dependency additions: none (stdlib and existing modules). No PII.

### W0 rev 2 conditions

| condition | result | evidence |
| --- | --- | --- |
| Forged-document fixture against the probe host committed as a test | Partly met. The test is named and red first (`test_module_body_forgery_in_probe_host_is_refused`, plus `test_check_never_imports_deliverable_code`), with the fixture body described. The spike scripts are not committed and the design does not say they become fixtures. No positive control is named, and the "3 of 3" is not carried into the test. See findings 1. | design s14 table "gate items", s10 row N1, s15 ("not committed") |
| `-S` and ADR-0018 amendment note in the design | Met. s5.3 (`-S`, G12) and s17 ("ADR-0018 amendment needed (RV-SEC F9)") record both the `-S` base interpreter and the one-byte acknowledgement as W0's, not the ADR's, and leave the note to the Coordinator. | design s5.3, s17 |

### Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | s14 gate items; s15 | The F1 spike (forgery accepted 3/3 in-check, no effect 3/3 in a probe host) lives only in the author's scratchpad. The committed test proves the probe host refuses the forgery, but nothing proves the fixture can forge at all. If the fixture rots (a changed argv, a renamed helper), the test goes green vacuously. The 3-trial claim is not a committed assertion. | major | s15 "Scripts are in the session scratchpad ... not committed"; s14 names one test node and no control | Commit the fixture module under `tests/fixtures/` (the exact `sys.stdout.write(forged); sys.stdin.buffer.read(1); os._exit(0)` body). Add a paired control, `test_module_body_forgery_is_accepted_when_imported_in_check`, that imports it into a fixture check and asserts the forged line is accepted (this proves the fixture bites). Run the refusal test 3 times in one node. Add the in-check and probe-host variants of SP-F2 as the D7 pair. | Verified (design text) |
| 2 | s5.7, s5.6 rules 3-4; W0 outcome table | A tampered or sabotaged run is NA, not 0, whenever the hidden tests pass. A deliverable that cannot pass the check can turn a measured 0 into NA by leaving a process the check cannot sweep (exit 4, HB-CHK-002), or by killing the check (exit absent). If NA cells drop out of aggregates, that is a way to dodge a failing score. The design reasons only that forgery cannot raise a score; it does not consider NA as an exit from a known failure. | major | s5.7 last bullet ("Forgery can only aim to raise a score"); F3 "exit 4 ... never a score"; rule 4 | Keep NA for the grader (it cannot know the truth), but make the consumers fail closed: seam request to X-H1 and X-E that any HB-CHK-002 count above zero in a task's cells is a pilot-gate and verdict-validity item, never silently excluded from a rate, and the report shows the NA count beside every property metric. | Inferred (confirm: X-H1's treatment of NA in a denominator) |
| 3 | s5.2 phase 2, s5.3, F14 | The check copy is made from the archive with "symlinks kept as links", and removed in a `finally` with `make_writable`. Windows junctions and reparse points are not named. A junction in the agent's tree can make the copy follow into a large or sensitive directory, or make cleanup or `make_writable` walk into a target outside the copy. W0 rev 2 handled this for `publish_dir` (my earlier finding 10); W1-F does not carry it to the grading copy. | major | s5.2 step 2; F14 test `test_grading_copy_removed_on_every_path`, which only varies rules 1-8 | Copy and remove with reparse points handled by `lstat`: unlink the link, never recurse or chmod through it. Add `test_grading_copy_with_junction_leaves_target_untouched` (a junction in the fixture archive pointing at a sentinel directory outside the tree). | Inferred (confirm: the fixture test) |
| 4 | s5.9, s14 `test_property_check_env_excludes_credentials` | The credential constraint holds by construction: `grading_env` is an allowlist built from `HOST_ENV`, `CELL_ENV` and declared toolchain names; `HB_CLAUDE_OAUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, `GH_TOKEN` and `ANTHROPIC_API_KEY` are not on it (Verified: `profiles.py:35-41`, `correctness.py:96-98`). The test, though, checks four names. A fifth credential name passes. The hidden-test phase and `build()` are covered only by the same shared builder. | minor | s14 row 1; `profiles.DROP_EXACT` | Assert the exact key set instead: every key of the check, probe-host, build and hidden-test environment is in `HOST_ENV + CELL_ENV + the PYTHON* trio + declared names`. Keep the four names as a smoke case. Also assert the grader's own `os.environ` is never forwarded when a credential is set (set all four, run each of the four phases, read each child's environment). | Verified |
| 5 | s5.4 `spawn_deliverable`, s5.9 | `HB_CHECK_*` names are allowed in `cases.yaml env`, and `grading_env(extra)` copies `extra` names from the grader's `os.environ`. The value source for an `HB_CHECK_*` name is not stated: from the operator's environment (an ambient variable reaches the agent code) or from the check's `env_extra`. | minor | s5.9 "must be in TOOLCHAIN_ENV or start with HB_CHECK_"; s5.4 | State that `HB_CHECK_*` values come only from the check's `env_extra`, never from `os.environ`; test it. | Inferred |
| 6 | s5.4 `run_case`, s5.5 | Probe-host exchange is read line by line over a pipe. On Windows a blocking read on a pipe has no timeout in the stdlib, and a response without a newline could grow without bound before the case bound fires. The design says "at most 1 MiB" but not how the check enforces it or the bound while blocked. | minor | s5.5 "Lines (UTF-8, at most 1 MiB)", s5.4 `run_case` "enforces `bound_ms`" | Specify a reader thread with a bounded buffer and a join-with-timeout; on overrun, `sweep()` and take the kind's failing outcome. Add `test_unbounded_probe_response_is_a_failing_outcome`. | Inferred |
| 7 | s10 A13 | `test_e1_check_opens_no_socket` guards the check process only (an audit hook in the fixture check). Agent code in the probe host and the build is not network-confined, and a hostile S1 deliverable can open sockets or fetch packages. The row's "mitigate in E1" reads wider than the control. | minor | s10 A13; W0 rev 2 accepted residual (offline build) | Reword the row: "the check opens no socket; deliverable and build reach is an accepted residual (ADR-0012/0013), declared offline per task by W1-I and W1-L". | Verified (text) |
| 8 | s5.5 residual | The probe host runs agent code in the same grading copy as `check/`, so it can read `check/` and the cases it will be sent. The design hashes `check/` (modification) but does not list the reading as a residual. I accepted this in the W0 rev 2 delta; W1-F should record it in s18. | minor | s18 table has no row | Add RF-8: probe-host code can read the check source and special-case it. Accepted under ADR-0013. | Inferred |

### Checks that held (no finding)

- Credentials never reach a grading or check process: the environment is an allowlist built once in `_env.py` and used by the hidden-test phase, the check, the probe host and the build. `HB_CLAUDE_OAUTH_TOKEN` is on `denied()` and on the existing `DROP_EXACT`. Residual, not new: on a dotnet task `USERPROFILE` and `APPDATA` are in `DOTNET_HOST_ENV`, so same-user agent code can read the operator's credential files by path. That is ADR-0013's accepted same-user model; the check itself is declared with toolchain names only for the tasks that need them.
- Job-alone: the check and `spawn_deliverable` use `sys._base_executable` with `DETACHED_PROCESS`, as `docs/notes/spike-e1-job-alone.md` requires (alone only holds there, Verified in that note). `procs.spawn(console=False)` and `test_spawn_console_false_is_detached_and_job_holds_only_the_child` pin it. The job query failing reads as not alone. The probe host is also spawned through `spawn_deliverable`, so it is swept like any member.
- Hidden-test then check phase order, fresh copy, `check/` copied and hashed last; stdin closed on every path; the closed outcome set; the grader derives every derivable measure.
- STRIDE table: all ADR-0018 rows have a control, a test node and a disposition (A1 to A13), plus N1 to N9 for the reviews. A7 is a named transfer to X-LB, unreachable in E1. A3 and A5 state their residual honestly. The gaps are findings 2, 3 and 7 above (Repudiation and DoS rows show NA outcomes but not the verdict effect).

Seam disagreements: finding 2 (W1-F s5.7 versus W0 outcome table and X-H1 NA handling, a disagreement to resolve at the seam W1-F to X-H1); finding 5 (W1-F s5.9 versus W0 s3 `env`, a wording gap in the same rule). W1-I must set `app:` and offline build per W1-F s16.

Conditions for PASS: (1) finding 1, the committed fixture, positive control and 3-trial assertion; (2) finding 2, the NA-handling seam request to X-H1/X-E; (3) finding 3, the reparse-point test and handling. Findings 4 to 8 are advice for the same revision.

RESIDUAL RISK: in-process injection into the check by deliberate tooling (ADR-0018 s10a, accepted); probe-host code reading the check source (accepted); network reach of the deliverable and build (accepted, offline declared per task). CLEARS-THE-VETO: yes on the conditions above, none of which needs a W0 change.

GATE W1-F · Security & Identity · PASS WITH CONDITIONS · 8 findings (rv-sec-w1f-e1e4, 2026-10-03)
