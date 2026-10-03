---
id: review-eval-sim-w1c
title: "Simplifier lens review of W1-C, campaign record and bench campaign"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Simplifier, soft veto) findings on docs/design/eval-campaign-record.md (design/eval-campaign-record,
  ae21488b, 61338062) against W0 rev 3 and R-87..R-96. OI-4 answered: ring_run.attached.tag is constant and can go in
  the SR-C2 request. status and verify are specified both as read-only and as full lock-probe-sweep sessions.
---

# Simplifier review: W1-C campaign record and `bench campaign` (rv-sim-hc-e1e4)

Target: `docs/design/eval-campaign-record.md` on `design/eval-campaign-record` (`ae21488b`, `61338062`), against W0 rev 3 sections 4, 6, 13 and R-87..R-96 on `main`. RV-TA's findings (`eval-review-ta-w1c.md`) are not repeated. Verified = read in the documents or the tree; Inferred = reasoned.

## OI-4: is `ring_run.attached.tag` a constant in E1?

**Yes, and it is a constant in every epoch, not only E1.** Evidence in the design itself: `ring_run.attached` is written only by `pilot attach` (section 5); `pilot attach` refuses any ring that is not a pilot (C-21); a `pack-regression` run "belongs to no campaign" (section 3 row 5; spec UF-E2, EV-20); a `comparison` run enters through `grid.attached`, a different kind. So the field has one possible value, and `verify` would need one more row-shape rule (`tag == "pilot"`) to stop a hand-edited row from storing another. The field is derivable from the kind. **Recommendation: drop it.** W0 section 6 allows narrowing ("may merge kinds by narrowing"). Section 14 already carries SR-C2 for four W0 text fixes; this is a fifth item at no extra cost. The row becomes `{ring_hash, run_id}`. C-21 keeps its meaning (it reads the plan's `ring.tag`, not the row), and M-C21 stays.

Linked point: `ring_hash` has no compute reader. The section 2 reader table names `pilot pass`, the lock probe set and `eligibility`, and all three read `run_id` only; OI-1 shows the one rule that would use a ring hash cannot be decided from the ledger. Either name its reader (X-H2 header, EV-20) or drop it with `tag`. See finding 1.

## W1-C findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | section 3 row 5, `FIELDS["ring_run.attached"]`, section 2 reader table | `tag` is a constant (above). `ring_hash` is a stored field with no named compute reader (DM15 requires one). | minor | C-21 "tag `comparison`" refusal; section 2 table row `ring_run.attached.{tag, ring_hash, run_id}`; OI-1 | Drop `tag` via SR-C2. Keep `ring_hash` only with a named reader (it is the durable witness on a fresh clone, because `runs/` is gitignored), else drop it too. | Verified |
| 2 | section 5 intro, section 6 steps 1 to 7, section 9, section 5 `verify` and `status` rows, section 6 "What the lock does not cover" | **Contradiction that adds work.** Section 5 says every `bench campaign` subcommand follows the session protocol and section 6 says "every `bench campaign` subcommand uses it with no exception". The same section 5 rows say `verify` and `status` are "read-only", and section 6 says reads are lock-free. As written, `bench campaign status` takes the write lock, probes `grade.lock` of every attached run, and sweeps temps. So `status` is refused with HB-CMP-004 while a campaign run is being graded, which is the moment an operator most wants it, and a "read-only" command deletes files. No test (L-2 uses a write command) covers `status` or `verify` during grading. | major | section 5 intro, section 6 "session protocol" and "What the lock does not cover", section 5 table rows `verify`, `status` | `status` and `verify` call `campaign.read` plus `verify()` lock-free: no own lock, no probe, no sweep (the sweep stays in write commands). One sentence changes, `session` gets no new parameter, and L-2 gains one row (`status` during grading succeeds, folder bytes unchanged). `verify` reading a ledger mid-append is safe: a torn tail is ignored (ADR-0006). | Verified |
| 3 | section 13 F-5, F-10, F-11 | F-5 (latest wins) is asserted again by C-27 and C-31, whose rows already say "latest wins". F-10 (reader ignores a torn tail) tests `ledger` behaviour that ADR-0006's ledger tests own; F-9 keeps the campaign-specific part (`ledger.tail_repaired` is housekeeping, not a transition). F-11 (every kind has a writer and a reader) guards a closed enum that W0 forbids growing, and `verify` already rejects unknown kinds (F-6). | minor | section 13 F table; W0 section 6 "may not add one" | Delete F-5, F-10, F-11. | Verified |
| 4 | section 13 C-16, C-22, C-39 (and the idempotency halves of C-1, C-9, C-27, C-31, C-43, C-44) | Ten commands share one rule ("same content again = no-op"), each tested separately; C-16, C-22 and C-39 have no mutant of their own (M-C22 and M-C39 are blank). | minor | section 5 table "idempotency" column; section 13 rows C-16, C-22, C-39 | One parametrized `test_rerun_is_a_noop` over (state fixture, argv) with one mutant per row (the "no-op branch removed" mutants already exist). Folds 3 nodes and 6 half-assertions into one node. | Verified |
| 5 | C-32 second half, C-40, F-4 | C-32 asserts "a manifest and prereg contain no `os.environ` value and no absolute path"; the manifest half is W1-D's leak test (section 11 says so) and the prereg half is C-30's local-path row. C-40 (`attach` moves `registered` to `measuring`) is F-1's walk through the real CLI. F-4 (fix in `registered` keeps `registered`, stales the pilot) is the precondition of C-33. | minor | section 11 STRIDE row "I"; C-30 row "local-path source"; F-1, C-33 | Keep C-32's refusal and delete its leak assertion; delete C-40; merge F-4 into C-33. | Verified |
| 6 | V-7, V-9, S-3, G-2 | V-7 (temp folder) is V-6 with a directory fixture; V-9 (deleted or renamed discrimination record) takes the same `any other status` branch as V-3 on another path. S-3 (junction inside a temp is not followed) tests `atomic.sweep_temps`, which W1-B owns and tests; this module "never calls `rmtree`", which S-1 plus a grep for `rmtree` in `campaign.py` covers. G-2 (fresh clone with autocrlf) is a one-time proof of `.gitattributes` (`* text=auto eol=lf`), a git clone per run. | minor | section 7 verify steps 5 and 6, "sweep"; section 13 rows | Parametrize V-6/V-7 and V-3/V-9. Delete S-3. Move G-2 to the slow ring or run it once. | Verified |
| 7 | L-1 | "Over 40 natural races and 20 barrier races": the natural half is probabilistic. The design's own spike measured 0 of 60 natural runs with both proceeding, so a correct implementation and the check-then-lock mutant (M-L1) look the same most of the time; 40 process-pair spawns on Windows buy time, not a failure. The barrier half is deterministic and is what kills M-L1. | minor | section 15 evidence row for S-C4 (natural 60 runs: 54 one proceeded, 4 both refused, 2 own-held); L-1 | Keep the barrier races (a handful is enough because the `between` hook forces the overlap) and delete the 40 natural races. The spike stays as one-time evidence. | Verified |
| 8 | section 5 `pilot pass` vs W1-H 3.2 `pilot` (seam) | **Seam disagreement, same as W1-H finding 10.** W1-C calls `gates.pilot(view, disagreements)` "with the third parameter W0 rev 3 gave it"; W1-H adds a fourth, `expected_na`, which W1-C never sources. W1-C OI-2 and OI-3 (prereg names no tasks; who computes saturation) are open, and W1-H's design does not answer them. Both docs cite W0 section 8, which has three parameters. | major | W0 section 8 `pilot`; W1-C section 5 `pilot pass`, section 14 OI-1..OI-3; W1-H 3.2, 5 | Coordinator rules the arity (default `expected_na` to `{}`) and assigns OI-2/OI-3 to W1-H in its follow-up. W1-C then adds one line to `pilot pass` or states it passes none. | Verified |
| 9 | section 5 `baseline` ("Spike E4 cited as passed") | `SPIKE_E4` is a constant path to one note in a general module, and the machine reads only `status: accepted`. The author flags it. It is one precondition for one campaign. | minor | section 5 baseline details | Keep as a `baseline_unmet` entry, marked `simplify:` with trigger "a second spike precondition"; no table, no config. | Inferred |

## What earns its place (kept deliberately)

- **Eleven kinds, none added, none merged.** Section 3 tests each against "derivable from the other rows?" and the answers hold (`defect_fix.scope` stays because `CLASSES` can change; `admission.decided` stays because `runs/` is gitignored).
- **`fold` over one transition table, shared by `verify`.** One definition; no stored `state`.
- **`session` as a Template Method and `acquire_then_probe` as one function** used by both lock owners (DM7). The `between` hook is test-only and costs one parameter.
- **`check_plan` shared by `attach` and `bench run`,** and the git-prefix rule in `verify` (a prefix for an append-only file, equality for immutable files; the alternative "any change refuses" was shown wrong by W-6).
- **No `ledger.py` change, no `status.py` change, no cache of the fold, no `--campaign` alias.** The Simplifier pass in section 10 is genuine.
- **C-45 (state guard matrix) and C-46 (refusal shape over all cases):** two meta-tests that replace per-command copies.

Blocking: none. Soft veto not exercised. Finding 2 is a specification contradiction the author can fix by deleting two sentences' worth of scope; finding 8 needs a Coordinator ruling. After findings 3 to 7 the command tests number about 38 and the node count falls by about 10 without losing a mutant.

GATE W1-C · Simplifier · PASS WITH CONDITIONS · 9 findings (rv-sim-hc-e1e4, 2026-10-03)
