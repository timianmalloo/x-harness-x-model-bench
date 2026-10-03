---
id: review-eval-sec
title: "Security & Identity lens review: Evaluation Campaign design slices (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, security, evaluation-campaign, wave-1]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  The Security & Identity lens's findings on the Evaluation Campaign designs, one section per slice, appended per batch.
  Each section ends with one gate line. Findings only: no design is edited here.
---

# Security & Identity review (rv-sec-e1e4)

PERSONA: security-identity-architect · MODE: Adversary · TIER: T2. Severity: blocking / major / minor. Confidence: Verified (observed in a file) / Inferred (reasoned; the confirming check is named).

## W0: `docs/design/eval-seam-contracts.md` (main, 5092455c, incl. R-90)

Trust boundaries named: B7 (agent-written deliverable vs the hidden check and the grader), the grader-to-check result pipe, `bench/campaigns` and `bench/discrimination` (committed records beside hostile code), the grading environment (credentials), the identity manifest (committed, content-addressed). W0 adds no dependency (stdlib throughout; `uv.lock` is an identity component). No PII.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | W0 s3 `interface: in-process`; ADR-0018 s2 | "In-process" probes import the deliverable into the check process. Agent code then runs inside the process that holds the in-memory outcomes, the result pipe and the stdin ack. Import-time code can write a schema-valid document, read the ack byte and exit 0, or patch `bench_check`. Every s10a defence (check alone in the job, one document, exit after document) assumes the agent code is a different process; none applies. ADR-0018's residual calls tampering "undetected" only for deliberate injection tooling. Here it is one line at module top level. E1 admits in-process only, so S1, the primary security signal (`exploit_probes_blocked`, `property_check_pass`), is forgeable for the whole of E1. W0 s3 also says the check "calls only `spawn_deliverable` and `write_result`", which contradicts importing the deliverable. | blocking | W0 `:97-98` ("E1: in-process only"), `:115`; ADR-0018 s2 ("probes call it in process: no socket at all") and s10a(a)-(b). Exploit that confirms: a fixture deliverable whose module body does `import sys, os; sys.stdout.write(<forged blocked document>); sys.stdin.buffer.read(1); os._exit(0)`. Expect `invalid (check tampered)`; today nothing in W0 produces it. | Define `in-process` in W0 as "in a bench-provided probe-host child, spawned by `spawn_deliverable`, that imports the app and answers probes over files or a pipe the check owns". The check process never imports agent code. Add the fixture above as a red-first test beside `test_forged_result_via_duplicated_handle_is_tampered`. Rename the value (`import-host`) if "in-process" is kept for the old meaning. | Inferred (exploit named; one fixture run confirms) |
| 2 | W0 s3 `cases.yaml: env: []` | "Extra variable names the check may pass, beyond HOST_ENV" is open-ended and its values have no stated source. ADR-0018 s9 allows only the toolchain variables and the check's own host, port and seed. A task author could list `GH_TOKEN` or `HB_CLAUDE_OAUTH_TOKEN` and the value would come from `os.environ`. `profiles.py` already holds the credential denylist (`DROP_EXACT`, `DROP_PREFIXES`). | major | W0 `:102`; ADR-0018 s9; `src/harness_bench/profiles.py` (`DROP_EXACT`, `DROP_PREFIXES`). | Narrow `env` to names from a fixed toolchain list plus `HB_CHECK_*`. Readiness rejects any other name with HB-RDY-005, and rejects any name matching the profiles denylist. `spawn_deliverable(argv, env_extra)` rejects keys outside the declared `env` and `HB_CHECK_*`. | Verified |
| 3 | W0 s3 invocation, R-90 condition 2 | The property grader runs two agent-code phases on one deliverable: `correctness.grade()` (hidden tests) and the check. R-90 says "in its own grading copy", which can mean one shared copy. Agent code run by the tests, or a process that survived them, can leave files in `check/` or `deliverable/` before the check starts. The check-tree hash (ADR-0018 summary and STRIDE row) would be taken after the poison, so "before and after" passes. | major | R-90 condition 2; W0 s3 "builds a grading copy ... holding `deliverable/`, `check/`". | Order the phases: tests first in their own sub-copy, job confirmed empty, then a fresh copy for the check, with `check/` copied in last and hashed at that moment. State this in W0 s3. | Inferred (confirm: a fixture test that writes into the next phase's directory) |
| 4 | W0 s3 "Grader outcomes" table | The ADR-0018 control "check tree hashed before and after; a mismatch is NOT_RECORDED `check tampered`" is in the ADR's STRIDE table and summary but is not a row in W0's closed outcome vocabulary, and HB-CHK-002 is defined only by s10a(b). A slice that builds from W0 alone omits it. | major | ADR-0018 STRIDE row "Tampering (the deliverable alters the check or its result)"; W0 `:127-135`. | Add a row: check-tree hash differs before and after, `invalid (check tampered)`, HB-CHK-002. Name the hashed set (`check/`, `bench_check.py`, `cases.yaml`). | Verified |
| 5 | W0 s3 `measures` | The check self-reports `measures` that its own `cases` determine (for example `exploit_probes_blocked` is blocked probes over probes). That is two definitions of one quantity, and the grader trusts the check's value. W0 does not say the grader rejects a key outside the task's narrowed metric set (R-90 condition 1). | minor | W0 `:125`; R-90 condition 1. | The grader recomputes every derivable measure from `cases` and treats a mismatch, or an unknown or out-of-set key, as `check output invalid` (HB-CHK-001). | Inferred |
| 6 | W0 s10 G4, ADR-0018 s9 | G4 greps the token `HOST_ENV =`. Verified: `DOTNET_HOST_ENV = (` in `correctness.py:49` and `mutation.py:39` contains that substring, so either G4 is red at the join or the allowlist is widened silently. More important, the token guards the constant's definition, not the invariant "no inherited `os.environ`". `os.environ.copy()`, `{**os.environ}` or `env=None` in `property.py` or `bench_check.py` passes G4. ADR-0018 s9's runtime test `test_property_check_env_excludes_credentials` is not carried into W0. | major | `src/harness_bench/grade/correctness.py:49,97`; `mutation.py:38-39`; W0 `:341`. | G4 tokens: word-boundary `\bHOST_ENV\s*=`, and add `os.environ` appearances in `grade/property.py`, `grade/bench_check.py` and `grade/_env.py` outside `_env.py`'s allowlist build. Quote the runtime test in the "not scan-shaped" list. | Verified (substring), Inferred (join effect) |
| 7 | W0 s3 deliverable `build` | W0 says only `start` goes through `spawn_deliverable`. The `build` argv runs agent-controlled build scripts (setup hooks, package installs). If it uses a bare subprocess it inherits the check's handles and `os.environ`, and may reach the network. | major | W0 `:99-100`; ADR-0018 s10 ("The check never spawns the deliverable directly"). | `build` also runs through `spawn_deliverable` (same env, handle list, job). Readiness rejects a `build` that needs a package index; state the dependency pinning source. | Inferred |
| 8 | W0 s3 `--evidence <abs evidence dir>` | The directory is not placed. Evidence holds deliverable stdio and probe details and is later read by the judge, reports and the egress scanner. If it is inside the grading copy, the deliverable can write or replace it. | minor | W0 `:110`; `grade/__init__.py:57` (`out_dir` is "the only place a grader writes its evidence"). | Fix it as `out_dir/evidence` (outside the grading copy). Say the evidence is egress-scanned (US-47) and that canaries are class `task canary` (R-E9) before any judge or report read. | Verified |
| 9 | W0 s3 vs ADR-0018 s1; spike E1-S3 | Two seam differences. (a) W0 runs the entry under `sys._base_executable`; ADR s1 says "the task's pinned interpreter". The base interpreter carries the operator's global site-packages. (b) The one-byte stdin ack is W0's (from spike E1-S3), not in the ADR. Authority order says the ADR wins, so the ADR needs an amendment or W0 a note. | minor | W0 `:97,126`; ADR-0018 s1, s10a(b); `docs/notes/spike-e1-job-alone.md:21,56`. | Record both in an ADR-0018 amendment note. For (a) run with `-s` and an empty `PYTHONPATH`, or name the pin. | Verified |
| 10 | W0 s4 `publish_dir` | `tmp = final.with_name(f"{final.name}.tmp-{os.getpid()}")` is predictable and fill uses it with no stated exclusive create. A same-user cell running in parallel can pre-create it, even as a junction, so the copy lands elsewhere. `stale_temps` deletes by glob and does not say it refuses reparse points. A crashed pid reused after restart collides with its own leftover. | minor | W0 `:147-153`. | `fill` gets a tmp that `mkdir` creates exclusively (a collision raises); `stale_temps` and the resume sweep `lstat` first and refuse reparse points (unlink the link, never recurse). The sweep logs each deletion. | Inferred |
| 11 | W0 s6 identity components | `platform` is unspecified. If it carries hostname, user or paths, it lands in committed content-addressed files that are public in the repo. | minor | W0 `:219`. | Define it as OS, version and architecture only. A test asserts no `os.environ` value and no path appears in a manifest. | Inferred |
| 12 | W0 s9 | `bench_check.py` is copied into the grading copy and runs beside agent code, yet the table classes it as an ordinary lint-set module. If it imports `harness_bench`, it will fail in the copy or pull bench code onto the agent-adjacent path. | minor | W0 `:322`. | Add to G3: `bench_check.py` imports stdlib only (no `harness_bench`). | Inferred |

Seam disagreements: finding 9 (W0 vs ADR-0018 s1 and s10a(b)); finding 4 (W0 s3 vs ADR-0018 STRIDE row). R-90 condition 2 and W0 s3 are not yet jointly specified for sequencing (finding 3). No disagreement between two designs yet; the Wave 1 designs W1-F and W1-I must not widen s3.

Controls confirmed sound (no finding): result is a closed schema with case ids only from `cases.yaml` and no free text in the ledger; seed derivation is deterministic and recorded; the measured-0 versus NA split keeps timeouts and tampering out of scores; `create_once` and the campaign chain give tamper-evidence for committed records (detected, not prevented, as ADR-0018 s11 states); no new dependency and no network use in W0, so no supply-chain exposure; the windows branch of `publish_dir` is evidence-based (spike E1-NTFS).

RESIDUAL RISK: a same-user deliverable can still inject into the check or edit committed records (accepted, ADR-0012, ADR-0013, ADR-0018 s10a and s11). A deliverable that binds `0.0.0.0` is LAN-reachable during a check (accepted, follow-up HB-CHK-005 in E4). CLEARS-THE-VETO: no, until finding 1 is resolved in W0 text. Findings 2 to 4, 6 and 7 are conditions.

GATE w0-seam-contracts · Security & Identity · BLOCK · 12 findings (rv-sec-e1e4, 2026-10-03)

## W0 rev 2 re-review (delta only), 2026-10-03: `docs/design/eval-seam-contracts.md` on main 3c1c9827

Scope: the 12 findings above against rev 2's section 3, section 10 (G4, G5) and the Review disposition table. Nothing else re-read.

| finding | rev 2 result | evidence |
| --- | --- | --- |
| F1 (blocking) | Resolved. The check never imports agent code. A probe host is spawned through `spawn_deliverable` with only its own stdio handles; the check classifies the raw response. The red-first forgery test is named. W1-F reports 3/3 forged-document trials succeeding against the old model and 3/3 defeated by the probe host (reported by the Leader; the evidence is in W1-F's design and I did not review it). | rev 2 s3 "in-process, redefined" |
| F2 | Resolved: `env` is limited to `TOOLCHAIN_ENV` plus `HB_CHECK_*`, the profiles denylist is refused (HB-RDY-005), and `spawn_deliverable` raises on other keys. | s3 `env` |
| F3 | Resolved: tests phase first, job confirmed empty, then a fresh `check-run/` copy with `check/` copied last. | s3 Invocation |
| F4 | Resolved: outcome row 3 is the `check/` hash mismatch (HB-CHK-002), and the row order is explicit. | s3 outcome table |
| F5 | Resolved: derivable measures are computed by the grader; unknown keys are `check output invalid`. | s3 `measures` |
| F6 | Resolved: word-bounded G4 token and G5 for `os.environ` use (per the disposition table; I read the disposition rows, not the G4/G5 text). | disposition TA 2, SEC 6, SEC 12 |
| F7 | Accepted in part, and I agree with the reasoning. `build` goes through `spawn_deliverable`. Rejecting "readiness rejects a build that needs a package index" is right: readiness cannot observe a build's network reach. | disposition SEC 7 |
| F8, F9, F10, F11, F12 | Resolved as dispositioned. F9's `-S` choice (not `-I`, which would drop the script folder from `sys.path`) is sound. | disposition rows |

New findings from the delta:

| location | finding | severity | fix | confidence |
| --- | --- | --- | --- | --- |
| s3 SEC 7 residual | An offline build is a task declaration that nothing enforces. A build step can still fetch packages (supply chain) and run install hooks as the operator. | minor | W1-I and W1-L must state the offline build and the pinned inputs per task; the security reviewer of each checks it. Keep it in the accepted residual list. | Inferred |
| s3 probe host | The probe host runs agent code in the same grading copy as `check/`, so agent code can read the check source and the probe payloads and special-case them. Row 3 detects modification, not reading. | minor | Accept as a residual of ADR-0013 (same user). Optionally keep payloads out of `check/` until sent (the probe host receives them one at a time over the pipe, as rev 2 already does). | Inferred |

Conditions for the slices that build on this: (1) W1-F carries the red-first forged-document fixture against the probe host and the 3-trial result as a committed test; (2) the `-S` and amendment note lands in W1-F's design; (3) W1-I and W1-L declare offline builds.

GATE w0-seam-contracts rev 2 · Security & Identity · PASS WITH CONDITIONS · 2 findings (rv-sec-e1e4, 2026-10-03)


## W0 rev 3 section 3 delta, 2026-10-03

Scope: the owed delta check of section 3 only (wsgi kind per ruling C-1, frame field names, the `factory` / `paths` / `args` / `{state_dir}` keys, app-output routing, the start bound `bounds_ms[interface]`), read from `docs/design/eval-seam-contracts.md` on main and compared with W1-F rev 3 section 5.5 (`design/eval-property-grader-r3`, f125430a). The boundary analysis is in `docs/design/reviews/eval-review-sec-w1f.md` ("W1-F rev 3 delta"). The two documents agree on frames, keys, the start bound and output routing: no seam disagreement.

| location | finding | severity | fix | confidence |
| --- | --- | --- | --- | --- |
| s3 `{state_dir}` | "A per-case empty folder" does not say it is created fresh and reparse-safe. An earlier case's host can pre-seed or junction the next path. | minor | Add: created with no pre-existing entry; a reparse point is unlinked, never entered. | Inferred |
| s3 cases, `{state_dir}`, app output | The case id is used as a path segment (`state/<case id>/`, `host/<case id>.log`) and its charset is fixed nowhere. | minor | Fix a charset in s3 and refuse others with HB-RDY-005, as for `paths`. | Inferred |
| s3 app output | "The check may scan it for a canary" reads as a complete leak probe. The scan sees the host's fds 1 and 2 only; a child process or the app's own file is outside it. | minor | Add one sentence: the scan measures accidental logging only. | Verified (text) |

Held: `wsgi` is a closed `kind` value beside `callable`; `paths` and `{state_dir}` are task-authored and hashed, not agent input; `args` substitution is done by the check; the start bound ends in row 6, never a score; the protocol-channel rule (private duplicates, fds 1 and 2 moved before the import) is sufficient against import-time forgery and leaves section 10a as the stated limit.

GATE w0-seam-contracts rev 3 section 3 · Security & Identity · PASS · 3 findings (rv-sec-f3-e1e4, 2026-10-03)
