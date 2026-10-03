---
id: review-eval-ds-w1c
title: "W1-C campaign record and bench campaign: Distributed Systems lens review"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Adversary-mode review of docs/design/eval-campaign-record.md (design/eval-campaign-record, ae21488b, 61338062) by
  the Distributed Systems lens. DS-1, F2 and F8 hold. Two majors: the torn-tail repair breaks the ledger-prefix rule
  after a commit, and the run side of conclude has no lock-then-probe partner. PASS WITH CONDITIONS.
---

# W1-C campaign record: Distributed Systems review (rv-ds-w1c-e1e4, 2026-10-03)

Read: sections 0, 2-7, 11, 13 (L, I, V rows), 14, 15 at 61338062. Code opened: `src/harness_bench/oslock.py` (whole), `ledger.py` `SegmentWriter.reopen`. Not repeated: RV-TA 1-9 and RV-PAT 1-8 (PAT 1 blocks on the state table; PAT 3 is the `others` set; TA 4 and 5 are the barrier assertion and the positive control).

## My W0 findings, checked here

| item | result |
| --- | --- |
| DS-1 freeze order | **Holds.** `attach` appends under `campaign.lock` only if `check_plan` holds; `register` is legal only in `piloted` or `registered`, so it is refused once `grid.attached` exists; `bench run` re-reads under the lock. Both interleavings end with the registered hash equal to every attached plan's hash. A plan built against a stale hash is refused at attach (the `plan --campaign` read is advisory). |
| F2 discrimination idempotency (X-E) | **Holds for W1-C.** W1-C has no path that rewrites a discrimination record. `verify` flags a modified or deleted tracked record and allows `??`. A re-run at an existing key is `create_once` returning false, then X-E's HB-RDY-010. |
| F8 own lock, then probe | **Holds in reasoning** (Dekker shape; `is_held` and `acquire` use the same byte-0 lock; `_try_lock` errors fall on the held side; a missing file is free and `acquire` creates it, so the race is closed). Needs the set form (PAT 3) and findings 3, 4 and 7. |

## Claims asked about

| claim | verdict |
| --- | --- |
| "At most one proceeds" | The proof is sound. The 90-race count is not evidence (TA 5) and the summary must not cite it as such. Rests on the proof plus a barrier test that can kill the mutant (finding 3). Windows only; POSIX is inferred (finding 7). |
| I-1/I-2 | Correct ordering claims. The register half needs M-I2 (TA 3). Both are in-process threads over `wait_s`, so they can fail on timing (finding 5). |
| Ledger-prefix rule | Right pattern. Two gaps: staged states (PAT 2) and the torn-tail repair (finding 1). |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 7 step 5 vs step 1 and FM-5 | **The crash repair breaks the witness rule.** After a crash the ledger ends in a torn line. If the operator commits before the next command, HEAD's blob holds the torn bytes. `verify` passes (working equals HEAD), the command runs, and `reopen` cuts the file back (`f.truncate(good)`) then appends. The working file is no longer a byte prefix of HEAD, so every later command is refused HB-CMP-003. The only exit is a hand edit of the ledger, which is what the rule exists to detect. | major | `ledger.py` `reopen` truncates to `good`; section 7 step 5 "byte prefix of the working file" | Compare the working file with HEAD's blob cut at its last newline (complete lines only). Add a test: torn tail, `git commit`, a command, `verify` is clean. Mutant: compare the whole blob. | Inferred (code read, not run) |
| 2 | 5 `conclude`, `abandon`; 5 `bench run`; 6 | **One-sided exclusion on the run side.** `conclude` probes the run's `.lock`; `bench run` takes `require_attached` under `campaign.lock`, releases it, then starts. A run can pass its check, then `conclude` probes a free `.lock` and appends, then the run takes its lock and writes cells into a concluded (or abandoned) campaign. Eligibility has no "recorded after conclusion" rule. This is the check-then-act shape the design bans (W-2) in the one pair it did not cover. | major | section 5 `bench run`: "(no probe: it writes nothing)"; `conclude`: "Refuses while any ... engine lock is held" | The run side takes its own lock, then probes `campaign.lock` through the same helper, then re-reads the state. Add the pair to L-7 and a mutant that drops the run-side probe. Or state that a late cell is ineligible by an added eligibility rule. | Verified (text); Inferred (interleaving) |
| 3 | 13 L-1, M-L1; 6 `between` | **The barrier cannot kill M-L1 as specified.** `between` fires after the own lock. The mutant swaps the order, so the barrier no longer sits between the mutant's two operations, and both-proceed appears only by timing. Also no barrier timeout: if one process dies, the other waits forever and the ring hangs. | major | L-1 text; section 6 `between` definition | Define `between` as "after the first operation, before the second". The mutant keeps that call between its swapped operations, so both probes see free before either lock. `Barrier(2).wait(timeout=10)` and a test timeout. | Inferred |
| 4 | 6 after-grading hook (SR-C2) | **The hook degrades on HB-CMP-001 only.** `verify_for_plan` probes every attached run. A sibling attached run graded in parallel raises HB-CMP-004. Unhandled, the grader fails after its pass, or the ADR-0018 11(b) check is silently skipped. | major | section 6 last paragraph | Map HB-CMP-004 and HB-CMP-001 to `campaign verify: not run (<code>)`. `verify` writes nothing, so give the hook `probe=False`. Test X-INT-3 with two attached runs, one graded. | Verified (text) |
| 5 | 6 `wait_s`; 13 I-1, I-2 | **Thread tests race the wait.** The loser retries in 0.2 s steps for `wait_s` (default 0.0). Under CI load the loser can time out with HB-CMP-001 where the test expects HB-CMP-010 or HB-CMP-009. | minor | section 6 step 2; I-1/I-2 "threads with `session(wait_s)`" | State `wait_s` large (30) in both tests; the winner releases on an event the loser sets. | Inferred |
| 6 | 5 `register` | **Preview and confirm are two reads of the file.** `--confirm` re-reads `--prereg FILE`. An edit between them registers a hash the operator never saw. | minor | table row `register`: "Without `--confirm`: print the statement and hash" | `--confirm <hash12>`; refuse if the recomputed hash differs. | Verified (text) |
| 7 | 6 "Why safe"; 15 S-C4 | **The lock domain is unstated.** The proof needs both sides to lock the same OS object. A grader in WSL (`flock` over 9p) and a campaign command in Windows (`msvcrt`), or a synced or network folder, do not exclude each other. | minor | `oslock.py` `_try_lock` per platform; S-C4 ran on Windows only | Add an `assume:` line: both sides run in one OS lock domain on a local disk; Say so in the operator doc. | Inferred |

Residuals accepted: FM-15 (a wholly uncommitted history); the W-5 spurious refusal; a lost uncommitted `grid.attached` fails closed through eligibility rules 2 and 3.

GATE W1-C · Distributed Systems · PASS WITH CONDITIONS · 7 findings (rv-ds-w1c-e1e4, 2026-10-03)
