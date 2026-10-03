---
id: review-eval-pat-w1c
title: "Patterns Expert review of W1-C: campaign record and bench campaign (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of docs/design/eval-campaign-record.md (design/eval-campaign-record, ae21488b, 61338062) against W0
  rev 3 and R-87..R-96. One blocking finding: the state table leaves no legal way to re-pilot after a fix in the
  registered state. The acquire_then_probe protocol is sound but its signature fits one probe, not a set. Gate BLOCK.
---

# RV-PAT on W1-C (session `rv-pat-hc-e1e4`, 2026-10-03)

Read from `design/eval-campaign-record` at 61338062 (532 lines), W0 rev 3 s6, `oslock.py`, `rulings.md` R-96.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | s4 transition table; s5 `pilot attach`, `pilot pass`, `power`; F-4, C-33 | **State-guard dead end.** A fix in `registered` leaves the state `registered` and makes `pilot_current` false. `register` then "waits for a new pilot pass" (C-33: "then OK after `pilot pass`"). But `pilot.passed`, `ring_run.attached` and `power` are legal only in `baselined` and `piloted`. No command can produce the pass; the second half of C-33 cannot go green; the only exit is `abandon`. The same hole exists in `measuring`. | blocking | table rows at lines 159-160 (`ring_run.attached`, `pilot.passed`: `baselined`, `piloted`); F-4 line 363; C-33 line 408; s5 `register` refusal "no current pilot" line 184 | Decide and write one rule. Either a fix in `registered` demotes to `baselined` like a fix in `piloted` (and a fix in `measuring` is refused as a freeze), or `pilot attach`, `pilot pass` and `power` become legal in `registered` while no grid is attached. Add the cell to C-45 with its mutant. | Verified |
| 2 | s7 `verify` step 5, git witness | The porcelain rule allows `??` and ` M`/`M ` on the ledger only. A routine `git add` before the commit yields `A ` on a new content file and `AM`/`MM` on the ledger; all fall under "any other status: tampering". An operator who stages, then runs the next campaign command, is refused with HB-CMP-003. Spike S-C3 covered ` M`, `??`, ` D` and rename, not staged states. | major | s7 lines 238-240; s15 evidence row for S-C3 | Treat index/work-tree letters in `{A, M, ?}` on the ledger as prefix-checked against HEAD, and `A ` and `??` on content files as new. Add `A `, `MM`, `AM` rows to V-4 and V-5 on a real repo. | Verified (text); Inferred (porcelain letters, not run) |
| 3 | s6 `acquire_then_probe(own, own_code, other, other_code, between)`; L-6 | The signature takes one `other` lock. The campaign side must probe a set (every attached run's `grade.lock` plus the argument run). As written, X-C loops `is_held` itself or calls the helper once per run, which breaks the "one function, one definition" claim (DM7) that justified SR-C1. | major | s6 line 210 (a set) against line 215 (single `other`) | `others: Sequence[tuple[Path, str]]`; the helper probes all while holding the own lock and releases on the first held. L-7 then asserts both sides call it with their set. | Verified |
| 4 | s6 safety argument; `oslock.py` | The reasoning (own lock first, then non-blocking probe; at most one proceeds) is sound and the 90-run measure agrees. It is the symmetric try-lock handshake and is correctly one function. `is_held` and `acquire` use the same byte-0 lock (`_try_lock`), which the argument needs. `between=` is a test hook in a production signature: acceptable as the only seam for a deterministic barrier. | minor | `oslock.py` `_try_lock`, `is_held`; s6 line 217 | Make `between` keyword-only; name the pattern in the docstring. | Verified |
| 5 | s5 `pilot pass`, `register`, `power`; W1-H s3.2 | **Seam disagreement with W1-H.** (a) `gates.pilot` arity: 3 in W0 s8, 4 in W1-H. (b) W1-H F13 refuses a `None` reader list; W1-C has no handling for a reader that failed. (c) R-96 condition 1 needs the `level_rule` sentence in the `register` preview "before the hash is taken"; it is absent. (d) W1-H R-H1 asks `register` to warn when `min_pairs` is below the required n; it does not. Four items across two documents, owned by neither. | major | W1-C lines 184, 196; W1-H lines 106, 210, 416; R-96 cond. 1 | Coordinator rules the four together. W1-C adds the `level_rule` line to the preview, turns a failed reader into a pilot refusal, and adds the `min_pairs` warning. | Verified |
| 6 | s5 `register` check "final power inputs" | `register` reads the latest `role: final` row. A fix demotes to `baselined` and a new final needs a new pilot, but nothing forces the latest final row to be later than the latest demotion. A stale pre-fix final can satisfy "mde equals final". | major | s5 line 197; s3 kind 4 line 117 | Require the final row's `seq` to exceed the last baseline or fix row; add a mutant that drops the order check. | Inferred (from the text; no code yet) |
| 7 | s5 `HB-CMP-008` | One code carries two meanings: gate items failed (`pilot pass`) and register preconditions. The design justifies HB-CMP-010 as "one predicate, one code" and holds HB-CMP-008 to a looser rule. | minor | s5 lines 182, 184 | Split the code, or state the rule as "one code per command family". | Verified |
| 8 | s5 `baseline` idempotency; s10 | The no-op test compares the tree to the baseline hash. After a recorded fix the tree equals the effective identity, so a repeat `baseline` is refused with "only a recorded fix changes the engine" although one exists. Separately, `session` is Execute-Around (a context manager), not Template Method. | minor | s5 line 178; s10 line 293 | Compare with the effective identity; rename the pattern. | Verified |

**Ledger-prefix rule.** The pattern is right (a witness check: prefix for append-only, equality for immutable) and the failure it removes (W-6) is real. Finding 2 is the gap: it was spiked on unstaged states only. Residual FM-15 (a wholly uncommitted history) is honestly accepted.

**Command state-guard table.** Eleven of twelve commands are consistent between s4 and s5; the exception is finding 1. The matrix test C-45 is the right control and must carry the `registered` row for `pilot pass`.

GATE W1-C · Patterns Expert · BLOCK · 8 findings (rv-pat-hc-e1e4, 2026-10-03)
