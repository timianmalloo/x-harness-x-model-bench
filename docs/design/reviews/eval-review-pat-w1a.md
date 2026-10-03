---
id: review-eval-pat-w1a
title: "Patterns Expert review of W1-A, arms v2 (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1, w1-a]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of design/eval-arms (ab13f0eb) against W0 rev 2 and R-87..R-93. The hash-keyed blocked order with a
  bounded redraw and the AST form of G1 survive; the dropped top-level pack makes four readers degrade silently
  (one of them not covered by SP-A3), G1's token set is narrower than its claim, and the drop is in no seam request.
---

# RV-PAT review: W1-A `docs/design/eval-arms.md` against W0 rev 2

Read in full on `design/eval-arms` (ab13f0eb); W0 from `main`. Code opened on `main`: `board.py:755-757`, `report/html.py:265-266,288`, `report/summaries.py:175-178`, `report/pack_improvement.py:742-748`, `cli.py:145-148`, `views.py:525`.

**Patterns that fit.** Anti-corruption layer over a versioned document (`cell_arm` / `arm_pack` / `plan_comparisons`), Adapter for the in-memory `/1` upcast, Frozen label for the `pack` ingredient key, Fail fast for HB-PLN-004, Template with late binding for role arms. The order is a randomized complete block design with restricted randomisation: sorted SHA-256 keys instead of a PRNG is the right call (stable across Python versions; no `stats.py` import into a run-class module). The bounded redraw is rejection sampling with the accepted seed recorded; with a measured 25 % first-draw failure at the pilot shape, a bare refusal would be the worse idiom. A counterbalanced block (alternate arm order by block index) would need no redraw, but EV-17 asks for a seeded permutation and the 5 % assertion, so the Simplifier's alternative does not displace this one. Mutual check with RV-SIM: the pattern survives. The AST form of G1 is the repo's own idiom (`tests/test_architecture.py`) and is better than W0's regex (SP-A5 shows the regex hits a comment).

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 history table (top-level `pack` dropped), 3.8, SP-A3, SR-3 | **Dropping the top-level `pack` turns four legacy readers into silent degraders, and SP-A3 covers only some.** SP-A3 ran `board.build`, `assemble` and `render` on a view, so "no exception" holds. But `pack_improvement.py:747` reads raw plan cells (`isinstance(c.get("pack"), str)`): a `/2` cell has `arm`, so `planned` is silently empty. `board.py:755-757` reads `(plan).get("pack", {}).get("revision")`, so `same_pack_revision` is `None` for two `/2` plans and ADR-0014's "hard precondition" is skipped, not failed. `summaries.py:177` writes `pack_revision: None` into the ranking manifest. `html.py:265,266,288` print "not recorded" for a run that has a pack. SR-3 names the header text and `no_pairs`, not these three. | major | `pack_improvement.py:742-748`; `board.py:755-757`; `summaries.py:175-178`; design 3.8 SP-A3, 5.1 | Add the three sites to SR-3's list with a fixed phase. For E1, make `board.compare` and the ranking manifest refuse a `/2` plan (loud) until E3 migrates them, or read `arm_pack` for the one pack-bearing arm. Add a test that runs each of the four readers on a `/2` plan with a pack-bearing arm and requires a true statement or a named refusal, red against today's code. | Verified (code); Inferred (that E1 runs reach `board.compare` and the manifest) |
| 2 | 3.8 G1 token set | **The AST scan is narrower than "no reader reads `pack` directly".** It matches three forms. It misses `.pop("pack")`, `"pack" in cell`, `getattr(x, "pack")`, `operator.itemgetter("pack")`, `for k in ("pack", ...)` and a `pack=` keyword. Second, the allowlist exempts a file wholesale: `html.py` has 36 hits and `board.py` 19 (SP-A5), so a new direct read in an allowlisted file is invisible, and the E3 narrowing has no burn-down measure. | major | design 3.8 table and SP-A5 counts | Flag every string `Constant == "pack"` outside docstrings, every `Attribute` named `pack`, and every `keyword(arg="pack")`. Pin the per-file hit counts from SP-A5 in `PACK_READERS_ALLOWED` (a ratchet): a count may fall, never rise; X-A3 lowers them to zero. Fixture per added form. | Verified (token list, counts); Inferred (which forms occur in future code) |
| 3 | 3.4 `draw_launch_order` | **Refusal text and cap are shaped by the 2-arm case.** The message says "needs at least 2 blocks", which is false for a 2-block, 4-arm plan that may need more draws than the cap. SP-A2 stops at 3 arms; arm count is uncapped (4.). `launch_seed` has a reader only in a test, and `draws` is in a log event, not the plan. | minor | design 3.4 table (max 40 draws at 2x3), 4 (no `MAX_ARMS`) | Report the shape and the draws made in the message, and drop the "at least 2 blocks" claim for A > 2. Add the 2x4 and 3x4 shapes to SP-A2's table in the test. The cap-exhaustion test already exists; give it a 3-arm case. | Verified (text); Inferred (4-arm pass rate) |
| 4 | 2 `CellView.pack`, event key, `Cell.id` | **Three names for one concept stay: `pack` (recipe key, `CellView`, report rows) and `arm` (cells, events).** The frozen recipe key is right; the `CellView.pack` misnomer is recorded as "E3 renames it". Nothing makes E3 do it. | minor | design 2 history table (AD-8); 5.1 | Give AD-8 a trigger that the allowlist ratchet (finding 2) enforces: the rename is done when the `pack` hit counts reach zero. | Verified (text) |
| 5 | AD-2, SR-1..SR-4 vs W0 s5 | **Seam: the dropped top-level `pack` is in no seam request.** W0 s5 says `bench-plan/2` is `/1` "with these changes" and lists no removal; W0's accessor text still names the top-level `pack` for legacy plans only, but the readers above read it directly. The drop appears only as AD-2 ("no decision needs the Owner") and in the ADR-0014 amendment text. SR-1 covers quoting, HB-PLN-004 and G1's tokens, not this. | major | `eval-seam-contracts.md` s5 field table and accessor line; design 12 | Add it to SR-1 so W0 rev 3 lists the removal beside `arms`, and so X-D, X-C and X-H2 read the same table. | Verified |
| 6 | 3.5 ready rule | **"Ready" may be two predicates.** HB-PLN-004 reads `task.yaml status`. W0 s3 has `bench validate` run X-E's `readiness.py`, which also checks `expected` and the discrimination record. If `status: ready` can be set without that check passing, `bench plan` accepts a task `bench validate` refuses. | minor | design 3.5; W0 s3 (readiness hook in `cmd_validate`) | State that `status: ready` is written only by the readiness path, or have `build_plan` call the same predicate. One test: a task with `status: ready` and a failing `expected` is refused by both. | Inferred (W1-E's write path not re-opened) |

**Seam disagreements (E2E-D).** Finding 5 (W1-A vs W0 s5). No new disagreement with W1-D: W1-A's `plan.py` imports neither `campaign` nor `identity`, and W1-D's run-side-only `plan.campaign.identity` change is already in the Coordinator's request `req-01M41DJDH521RE0M4QJJK1FRTD`, so it is not re-raised.

**Residual risk.** Finding 1 shows up in the E1 demo as a wrong or empty report line, not as an error.

GATE W1-A · Patterns Expert · PASS WITH CONDITIONS · 6 findings (rv-pat-ad-e1e4, 2026-10-03)

Conditions: findings 1, 2 and 5 before X-A1 starts; 3, 4 and 6 may be recorded. Advisory lens; RV-TA's hard gate stands independently.
