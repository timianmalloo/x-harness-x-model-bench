---
id: review-eval-sec-w1e
title: "Security & Identity review of W1-E: discriminate, the synthetic profile and readiness (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, security, evaluation-campaign, wave-1, w1-e]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
  - { to: review-eval-sec, rel: refines }
review-by: "2026-10-17"
summary: >-
  Security & Identity gate on W1-E (design/eval-discriminate, 549f7bc4) judged against W0 rev 5 and R-98. Variants are
  data-only and the overlay is mostly safe, but the overlay misses destination links and Windows name forms, the
  variant edits have no path containment, the synthetic environment is a denylist that contradicts itself, and the
  attach path does not refuse a discrimination run. PASS WITH CONDITIONS, 10 findings.
---

# Security & Identity review of W1-E (rv-sec-w1e-e1e4)

PERSONA: security-identity-architect · MODE: Adversary · TIER: T2. Date 2026-10-03. Design read from `git show 549f7bc4:docs/design/eval-discriminate.md` (base `b88746d9`, written before W0 rev 5 and R-98). Severity: blocking / major / minor. Confidence: Verified / Inferred.

## Answers to the brief's questions

| question | answer |
| --- | --- |
| Can the synthetic agent be confused with a real harness? | Only through bookkeeping. It is `sys.executable synthetic_agent.py`, hash-frozen by `check_build`, with no profile file. A real `bench run` fails closed (`profiles.load` raises for `synthetic`, `cli.py:165`). The gaps are F1 and F2. |
| Can a real cell be scored as synthetic, or the reverse? | Grading does not branch on harness, so only the run's `plan.kind` separates them. Nothing in W0 s6 or the design refuses attaching a discrimination run (F1). |
| Is the solutions overlay safe? | Not yet: F3, F4. |
| Does `oracle/variants.py` stay unimported? | Yes. `ast.literal_eval` only, matches W0 rev 5 s2; T-E21 proves it. F5 adds hardening. |
| Can a record be forged or replayed? | Under R-98 (body without ids): a replay equal to the stored record is a no-op, a differing one is HB-RDY-010 and the file is untouched. A hand-written record on a fresh clone still passes (design F11, accepted; the pilot ring is the second measurement, Inferred). F6, F7. |
| Do credentials stay out of every phase? | Grading, record and link: yes. Engine phase: no, F8. |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | s5.4, T-E20, T-E35 | Exclusion is "structural". `config.HARNESSES` gains `synthetic`, so `validate_matrix` accepts it (`config.py:117`) and only `build_plan` refuses. No design text makes `attach`, `pilot attach` or `run_side_check` refuse a discrimination run. | major | W0 s6 rev 4 and rev 5 text; design s5.4 | Add the refusal (see the W0 section, row on attach). Add: `bench run` refuses `kind != "measurement"` with a named code, not the `ValueError` from `profiles.load`. Keep `synthetic` out of `config.HARNESSES` if a validator argument is smaller. Test with a real discrimination run folder. | Verified |
| F2 | s5.1 vs s17.2 E2 | s5.1 says `argv_env` returns `os.environ` plus `HB_SYNTH_OVERLAY`. s17.2 says it uses the profile denylist. T-E36 describes the skeleton as unfiltered. Both cannot be the design. | major | design lines 146, 432, 370 | State one rule (F8). | Verified |
| F3 | s6 rule 4 | The refusal list checks the overlay tree only. The agent writes into the working copy; a link in the base tree (a pinned third-party repo can hold symlinks) makes `a/b.py` write outside the cell. | major | design s6; no destination fixture in T-E3 | The agent `lstat`s each destination parent and the destination; refuses a link, reparse point or non-regular file. Add a destination-link param to T-E3 and T-E4. | Inferred (exploit); Verified (gap in text) |
| F4 | s6 rule 4, W0 s2 overlay | Windows forms are missing: `:` in a component (stream), trailing dot or space, device names (`aux.py`, `nul`). Case-fold collisions are covered; Unicode normalisation is not. The check exists twice (readiness and the stdlib agent). | minor | design s6.4 | Use the shared segment validator from the W0 section. Add a differential test: the same trees through both implementations give the same verdict. | Inferred |
| F5 | s7 | `edits[].file` has no containment rule. The operator process opens `<run>/variants/<name>/<file>` and writes the edit, so `..` or a rooted path writes outside. Also: one `VARIANTS` assignment only, a size cap, and syntax/recursion errors as HB-RDY-005. `clauses.json`: size cap, and the record copies the declared clause text only. | major | design s7; W0 s2 | Same path rules as the overlay on `edits[].file`, checked before the first read. T-E21 gains a `..` param. | Verified (gap in text) |
| F6 | s4.2-4.3, s17 F11 | The text matches R-98 (no ids; link after created-or-equal). The link is unauthenticated and "newest link" is by a self-declared stamp. A stale or planted link can print "reconciled". The T-E5 fallback text for option (a) must go (R-98 forbids an option-(a) branch). | minor | R-98 conditions; design s4.3 | The link carries the record's sha256; reconciliation checks the run's `plan.kind == discrimination`, the task version, and the synthetic combos, and orders links by the file's ledger stamp. Reconciliation only prints a note and never counts as a pass. Red test beside T-E6: no link after HB-RDY-010. | Inferred |
| F7 | s8.2 | Readiness picks the record by file name. It does not say the body's `task`, `platform`, `task_version[:16]` and `identity_hash[:16]` must equal the name. | minor | design s8.2 row 1 | Add the equality; T-E7 case: a win32 body renamed for another platform. | Verified (gap) |
| F8 | s5.1, s17.2 E2 | Even the s17.2 form is a denylist. `DROP_EXACT` lacks Google/Gemini/xAI/AWS/HF/NPM names (`config.HARNESSES` lists grok and agy). The agent needs almost nothing. | major | `profiles.py:38-41` | `SyntheticLauncher.argv_env` builds from the grader's allowlist (`grade/_env.py`, one definition) plus `HB_SYNTH_OVERLAY` and `TRACEPARENT`. T-E36 also sets an unlisted canary name and extends T-E34's scan to the credential canaries. | Verified |
| F9 | s9 | Says X-C's `verify` sweeps under an age gate. W0 rev 4 says verify is lock-free and sweeps nothing, and X-C never deletes in `bench/discrimination`. Text is stale, not a hole. | minor | W0 s4, s6 | Delete the sentence in rev 2. | Verified |
| F10 | s17 I2, s5.2 | Cites an "HB-PLN-002-style" refusal; W0 rev 5 says HB-PLN-004. `bench discriminate <task>` and the task id in `runs/.discriminate-<task>.lock`, `bench/discrimination/<task>/` and the run id are used as path parts without being matched to an existing `tasks/` entry. The `combo` to overlay mapping must be a table built from validated names. | minor | design s5.2, s9 | Match the id against the `tasks/` listing first; use HB-PLN-004; map combos from a table. | Inferred |

Held: no `engine.py` edit; the overlay is applied inside the cell by the agent; the record is written after the grading job closes; incomplete trials write no record; `parallelism: 1`; NA rows fail closed as HB-RDY-011; solutions are read only by discrimination runs; the record and link carry no path or user name.

Seam disagreements: (1) design s4.2-4.3 versus W0 rev 5 s6: superseded by R-98, W0 rev 6 owed, no code conflict left. (2) design s5.1 versus s17.2: internal (F2). (3) design s9 versus W0 rev 4 s4: stale (F9). (4) W0 s6 attach versus design s5.4: neither refuses a discrimination run (F1), a gap for X-C. (5) design s6 rule 4 and W0 s2 overlay: same list, same gaps (F3, F4).

GATE w1-e-discriminate · Security & Identity · PASS WITH CONDITIONS · 10 findings (rv-sec-w1e-e1e4, 2026-10-03)
