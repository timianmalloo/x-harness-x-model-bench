---
id: coordination-eval-wave2-e1-overnight-2026-10-05
title: "Overnight run 2026-10-04/05: Leader leader-e1e4 epoch 17 (E1 build joins, E2 starts)"
type: doc
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: relates-to }
  - { to: coordination-eval-campaign, rel: implements }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-12"
summary: >-
  The overnight Leader run, epoch 17, 2026-10-04 16:56 to 2026-10-05 07:00 local. Phase 1 joined and pushed. Every E1 build
  track was built and joined, 18 tracks in 7 pushed batches (origin/main a6e37b76 -> `17e22e00` plus this report). X-INT, the E1 end-to-end
  turn, was built and joined, and its E1 E2E list is green (24 passed, 7 strict xfail). One operator action unblocks the external harnesses: the earlier session left an applied mutant in the
  primary's views.py, which froze main in the primary and the external runner, so the E1 critical path ran on Sonnet
  under R-105. Rulings R-104, R-105 and R-106. The gate ring was measured at 77 to 81 min. The operator queue below has a
  recommended default for each item.
---

# Overnight run 2026-10-04/05 (Leader `leader-e1e4`, epoch 17)

**Result.** `origin/main` moved from `a6e37b76` to ``17e22e00` plus this report`. Every move was a fast-forward. Each pushed head had a green all-rings run (R-104), a green touched-mutation run, a gate-stamp check or renewal, and lint, docs-graph and ruling-citation checks. The verify gates are no worse than before: 4 failed at the start and 2 fail now, both allowed exceptions. Every E1 build track has joined. X-INT's E1 E2E list is green on `451c5847` and joined in batch 7. Of E2-E4, X-J2a (Agy) ran before the block at 20:25. After it, no external turn was dispatched (R-105), and the Sonnet-only E2-E4 work ran instead: X-LB0 and the S1 work.

## 1. Operator steps (steps 1-3 done by the operator at 06:20; the Leader committed the ledgers)

1. **Restore the primary checkout** `C:\Projects\x-harness-x-model-bench`:
   - `uv run python tools/mutate_check.py --restore`. This restores `src/harness_bench/views.py`, which still carries the `busy_ms` mutant `if True:` from the earlier session's interrupted `mutate_check --touched c3b35df7`. The command is byte-exact and removes `.git/mutate-applied.json`.
   - `git checkout -- docs/coordination/eval-wave2-e1/README.md`. This removes a stray duplicate of Coordinator #25's §8 entry, which that seat wrote into the primary by absolute path. The committed copy is on `origin/main`.
   - `git merge --ff-only origin/main`.
   - Commit the coord ledgers the tools wrote into the primary: 4 modified files and about 20 new files under `.agents/log/`. `origin/main` does not touch those files, so they do not block the fast-forward.
   - My own restore was refused by the permission layer, so I left the primary untouched all night. Every gate ran in `C:\Projects\xh-gate`, detached and then on branch `integrate/e1e4-17`.
2. **Then ask for the wrapper change (BASE-A, R-105 c8).** `.tools/coord/runner-leader.sh` should take the invoking tree as an argument. The runner bases every external dispatch on the primary's HEAD (`coord-runner.py` `prepare`), so one dirty file in the primary stops all external work.
3. Decisions are in §7, each with a recommended default.

## 2. What landed (`origin/main` `a6e37b76` → ``17e22e00` plus this report`)

| batch | head pushed | contents | gate evidence |
| --- | --- | --- | --- |
| 1 (Phase 1) | `4891e4d4` | integration fix `fix/merge-integration`; `test_report_browser` expects `pack-improvement` (design §2); gate stamp renewed | touched mutations from `c3b35df7`: 893 killed, plus 2 documented (M27 not run, no symlink right; M14b POSIX-only); gate ring 4,595 s; non-gate rings 2957 passed |
| 2 | `19e7536d` | X-I2, X-A1b, X-LB0, X-J2a, X-H1a, X-B2, and an X-B2 fix | 813 killed + correctness.json 55/55 with dotnet; gate ring 4,694 s; one red bisected to X-B2 (a stale fault-injection point) and fixed; rings 3064 passed |
| 3 | `0f64e7af` | HYG-VERIFY, X-I3, X-E, X-H1b, X-H1c, plus their fixes | 745 killed, 5 survived and all killed by follow-on tests or rewrites; 2 ring defects fixed (a conftest import collision; a G1 literal); rings 3305 passed |
| 4 | `aab95436` | X-I4, X-C1, plus a fix | 487 killed, 1 stale find retargeted; rings 3433 passed |
| 5 | `9a407669` | X-C2a, X-H2, R-106, plus a fix | 662 + 1 retargeted; gate ring 4,839 s; rings 3586 passed |
| 6 | `073067bd` | X-C3a, Coordinators #25-#28 | 508 killed; rings 3646 passed |
| 7 | `17e22e00` | X-C3b, X-INT, the overnight ledgers (`13189f8c`) | 877 killed; gate ring 4,766 s, stamp `ba1bc639`; one ring red (C3b: skill drift and a timing-scan entry), fixed by `024b4cfd`; rings 3723 passed, 8 xfailed (X-INT's 7 recorded legs + 1 standing) |

The standing skips in every run were 11, later 13. Five are symlink tests (no symlink right), five are POSIX-only process groups, one needs the absent `C:/projects/terminal-bench-2`, and later two more were added: a by-design parameter case and a campaign-lock symlink. None names dotnet, a gate run or playwright, so R-104 c3 is met.

## 3. Tracks

Served model ids for Sonnet workers are self-reported from each session's environment. That is the R-91 Agent-tool readback. The external ids are read from native records.

| track | harness / served model | red → green (selected SHAs) | join | planned / actual |
| --- | --- | --- | --- | --- |
| X-A1b | Codex 0.160.0, `gpt-6.1-sol` ×5 (rollout) | `be077f19` → `40aa4e83` | batch 2 | 3,300 s / 2,669 s |
| X-H1a | Grok: try 1 served `grok-4.6-build` at first response and was killed (R-103); retry r2 served `grok-4.7-build` ×36 but was red-only at 2,400 s; green by Sonnet | `365b1e76`, `b0cad73b` → `260c3402` | batch 2 | 2,400 s / 2,400 s + 30 min |
| X-B2 | Agy 1.2.13, `gemini-3.8-flash-high` (cli.log); red-only at 3,300 s; green by Sonnet | `f79ec925`, `efafa448` → `cb7523eb`; fix `16c25689` | batch 2 | 3,300 s / 3,300 s + 18 min + fix |
| X-J2a | Agy, `gemini-3.8-flash-high` | `b39cecba` → `e750bfc9` | batch 2 | 3,300 s / 3,188 s |
| X-I2 | Sonnet `claude-sonnet-5-5` | `17541943` → `b9ff0162` | batch 2 | 2 h / 40 min |
| X-LB0 | Sonnet | `4d22202b` → `64c3ea6a` (+2 pairs) | batch 2 | 75 min / 15 min |
| HYG-VERIFY | Sonnet | gates' own output → 4 commits | batch 3 | 90 min / ~30 min |
| X-I3 | Sonnet (uncompiled follow-on of X-I's brief) | `043efb8b` → `6afdf6f7` | batch 3 | — / 6 min |
| X-E | Sonnet | `0b67eea8` → `e664b1af`…`3aab1c8a`; egress `075bce78` → `852fdf7c` | batch 3 | 3.5 h / 55 min + follow-ons |
| X-H1b | Sonnet (planned Grok, R-105) | `d667152b` → `3c08d18e`; survivors `73dbb31d` | batch 3 | 2 h / ~100 min |
| X-H1c | Sonnet (planned Grok, R-105) | `75bcbf8e` → `9efa9905`; G1 `1fb067a7` | batch 3 | 2 h / 12 min |
| X-I4 | Sonnet | `f174af55` → `c8218c16` | batch 4 | 100 calls / 30 calls |
| X-C1 | Sonnet (planned Agy, R-105) | `b4bfb5ab` → `6432d632`; find `510d793b` | batch 4 | 3 h / 52 min |
| X-C2a | Sonnet (planned Agy, R-105); stopped at its context ceiling | `ada9760c` → `7ac20c62`; find `32415306` | batch 5 | 2.5 h / 50 min |
| X-H2 | Sonnet (planned Agy, R-105) | `295dd3e4` → `76e841d2` | batch 5 | 2.5 h / 65 min |
| X-C3a | Sonnet (planned Agy, R-105) | `c7d84e9e` → `5281420a` | batch 6 | 2.5 h / 2 h 20 min (mostly lock wait) |
| X-C3b | Sonnet (planned Agy, R-105) | `262efa70` → `15c6bb74`, `089679d3` → `c57c6ac7` | batch 7 | 2.5 h / 79 min |
| X-INT | Sonnet | `8b1ceaae` skeleton, `1aed1e21` (synthetic red), `451c5847` green | batch 7 | 2 h / 55 min |
| X-I-S2 authoring | Sonnet | blocked: the clone of pinned bottle `cbd569c4` was refused ("Code from External"); no commits | — | — |
| J2 (S1 record) | Leader, `discriminate.run` | record `5f54cf0b` on `leader/s1-discrimination` (not merged) | — | — / 59 s |

**Reds re-run by the Leader** on at least one red SHA per track. Each failed on an assertion or "DID NOT RAISE". There were two exceptions: X-C3b's skeleton reds that failed by `KeyError`, recorded as RED-C, and HYG-VERIFY, whose red is each gate's own output.

## 4. Failures caught, and their classes

Each one was caught before a push.
- **X-B2 batch-ring red.** `test_engine` patched `archive.shutil.copyfile`, a call that X-B2's new path no longer makes. GUARD-A (2nd instance). Fixed by re-pointing the injection under a granted seam request.
- **Batch-3 survivors (5).** Four were missing tests in X-H1b's `verdicts.json`. One was an equivalent mutant in X-E's `discriminate.json`, which was rewritten. Both tracks had left their own mutation runs to the batch.
- **Batch-3 ring defects.** A bare `from conftest import` collided under `-n 4` (CONF-A candidate). `gates.py` had a bare `"off"` that broke the G1 literal ratchet (GUARD-A, 3rd instance).
- **Batch-7 ring red (X-C3b).** C3b edited the generated copies of `start-benchmark/SKILL.md` instead of the source plus `tools/sync-skills.py`, and `test_skills_in_sync` caught the drift. It also added a real-time dependence in `test_identity.py::launch_diff` that was not in `TIMING_ALLOWED`; that is a TIME-B instance, and the timing-hygiene scan caught it. Both were fixed by a C3b follow-on before the push. Neither guard file was in the worker's guard list (GUARD-A, 4th instance). Control: add `tests/test_skills_in_sync.py` and `tests/test_timing_hygiene.py` to the standard worker guard list.
- **Stale mutant finds after a shared-file edit (MUT-E).** There were 4 instances, in `cli.json` twice and in `egress`/`plan` (by C3b). `test_every_mutation_find_text_occurs_exactly_once` catches the shape only where it runs. It is now in every worker's guard list.
- **Leader errors (mine).** (1) I gave workers `mutate_check --touched main` instead of their own sets, which duplicated work and held SUITE-LOCK for 20-40 min each. Fixed forward. (2) I queued a mutation run in the gate tree behind a pending stamp renewal, which could have stamped a mutant. I stopped it by PID before it took the lock. Proposed control: `gate_stamp --renew` computes its digest under the suite lock. (3) A conflict-resolution edit failed while a parallel `git add` committed conflict markers on a staging branch. It was never merged or pushed. I rebuilt the stage with a marker scan before every add.
- **Seat errors.** Coordinator #15 said "nothing uses `_in_radius`" without a grep, and a fixture does use it, so the alias stays. Coordinator #6's brief claimed "c reads nothing from a or b" for X-H1c. That was false, and R-105 relied on it (DEP-A). Coordinator #25 wrote into the primary by absolute path (PRIM-A candidate).
- **Classes registered this run** (by the Coordinator, in `docs/lessons/defect-classes.md`): MARK-A, RUN-B, DEP-A, BASE-A, INT-A, TEST-C, TEST-D, TEST-E, GUARD-A (and its upgrade trigger fired), plus instances of MUT-A, MUT-E and EDIT-B. **Candidates still owed a register entry:** PRIM-A, CONF-A, RED-C, EOL-A, GUARD-B, MEAS-B, DESIGN-CITE-A, SEAM-TYPE, and the Leader's stamp-race and staged-markers controls.

## 5. Rulings this run

- **R-104** (DR-12): the per-join recount is the default ring. Every ring runs once per batch, with `HB_REQUIRE_DOTNET=1` and `-rs` read. A head without a green all-rings run is never pushed. *Bounded reading I applied:* the gate ring ran once per `grade/` batch, at the stamp renewal, and was not repeated in the same batch's all-rings run when the digest was unchanged. Each batch's non-gate rings then included `test_gate_stamp`.
- **R-105** (DR-13): while the primary is blocked, the E1 critical-path external turns run as Sonnet from the integration branch, and E2-E4 externals wait. Its X-H1c-on-Grok exception was void, because DEP-A made X-H1c wait for X-H1b.
- **R-106** (DR-14): `launch_check` takes its key set from the plan's stamp, and `check_plan` gets an HB-CMP-010 clause. A changed build still stops a launch through the per-cell build check. Landed in X-C3b, with the INT-A control as the cross-owner launch test.
- **Coordinators #14-#28** compiled every brief (CO-S0) and ruled 10 seam requests (X-A1b ×2, X-J2a, X-E ×2, X-H1b ×2, X-B2, X-C1, X-H2), all resolved with none open. One was denied: X-H1b's coverage marker, which became `slow`. Three decision requests went to the Owner (DR-12, DR-13, DR-14), and all three were ruled.

## 6. Worker cap and process counts (LOAD-A's owed measurement)

- **Measured:** up to 4 workers ran at once, plus up to 3 seat sessions (Owner and Coordinators) and the Leader's gate runs. The process count stayed between 281 and 393 (measured), against the stop line of 1,500. There were 0 AppModel-Runtime 208/212 events and 0 trips in 172 health checks, and no terminal deaths.
- **The cap never limited the run.** The DAG did: after 20:30 at most 2-3 tracks were dispatchable at once. So 5 and 6 were never exercised, and LOAD-A's 3-worker figure is neither confirmed nor refuted above 4 (Inferred).
- **The bottleneck was SUITE-LOCK plus the gate ring.** Each ring took 77-81 min, three times, and the non-gate rings took 11-14 min per batch.

## 7. Decisions for the operator (recommended default first)

**Taken at 06:30 by the operator:**
- (1) Grok: keep R-103's kill-and-retry.
- (2) S1: keep A0, B2, B3 and C0, and drop the other nine.
- (3) T-E9: stays held.
- (8) Catalog freeze: keep the plan's order (R-86, after X-G3), and demo E1 on test data.
- (4) Bottle clone: the operator adds the permission rule, then X-I-S2 is re-dispatched from `build/eval-x-i-s2c`.
- (5) and (6): delete the remote `build/eval-x-f`, remove the merged worktrees and stray branches, and remove `C:\Projects\mc.out`. The Leader runs these after the batch-7 push.
- The overnight run stops at batch 7. The operator also completed §1 steps 1-3 (`views.py` restored, the stray README discarded, fast-forward to `073067bd`). The Leader committed the ledgers (`13189f8c`) and they went out with batch 7.

The list below is the original queue with its defaults, kept for the record.

1. **Grok pin.** X-H1a's first try served `grok-4.6-build` at its first response, the third drift session in two days. *Default:* keep the R-103 kill-and-retry. Please check grok.com's routing for this subscription.
2. **S1's F4 payloads.** The J2 record (`5f54cf0b`, not merged) shows that only A0, B2, B3 and C0 exploit any variant. B3 never exploits alone. A1, A2, A3, B0, B1, B4, C1, C2 and C3 exploit nothing. *Default:* drop the nine, keep A0, B2 and C0, and decide B3 (keep it for coverage of the `b` branch). This needs a new task version and a new record. Then S1 can go `ready` in one commit with the record.
3. **T-E9: wiring `readiness.problems` into `bench validate`.** It would turn CI's `bench validate` red today, on 8 HB-RDY-005 items in the draft tasks NG1, NG2, RW1, RW2, SM1 and SM2. *Default:* keep it held until those tasks are flipped or exempted as draft.
4. **The bottle clone for X-I-S2.** *Default:* allow `git clone https://github.com/bottlepy/bottle` with checkout `cbd569c4…` for the worker, or place a clone at a path, then re-dispatch from `build/eval-x-i-s2c`.
5. **Remote branch `build/eval-x-f`.** Deleting it was refused ("Git Destructive"). *Default:* delete it (`git push origin --delete build/eval-x-f`); it is merged.
6. **Local cleanup.** About 35 merged worktrees and branches remain (`coord worktree cleanup` keeps trees whose seat sessions were never ended), plus `integrate/b3-stage`, a staging branch with conflict markers that was never merged, and `C:\Projects\mc.out`. *Default:* `coord worktree cleanup --remove` after ending the seat sessions, and delete `integrate/b3-stage`.
7. **Pack findings for ai-forward** (from HYG-VERIFY): the machine-paths gate has no file-level exemption for byte-exact captured records; its relative-glob false positive; its fix text says `python3`. *Default:* file them against the pack.
8. **Catalog 0.7 freeze timing (for the E1 demo on real data).** The plan freezes after X-G3 (E3, R-86). The E1 demo needs a non-`.dev` catalog for `campaign baseline`. *Default:* keep the plan's order and demo E1 on the E2E fixtures now. Bring the freeze forward only if you want a real-data E1 demo before E3. It would need an Owner ruling, because R-86 sets the order.
9. **The gate-ring cost** is 77-81 min per `grade/` batch. *Default:* ask the Coordinator for a CI-OPT note on splitting the gate ring by input (dotnet mutation versus the rest). Profile before choosing.

## 8. E1 demo readiness

- **Built and joined: yes.** Every E1 build track is on `origin/main`. X-INT's E1 E2E list is green on `451c5847`. Items 1, 3-9, 11 and 13 pass on real modules and the real CLI, with real grading. Item 14 had nothing left. The strict-xfail legs are written with their failing assertions, so each turns red when its cause is fixed. They are: item 2's and item 12's `bench validate` legs (T-E9 held), item 5's `campaign.run_side_check` on a plan without a campaign block, item 7's two-arm pack-effect text (X-A3's reader migration), and item 10's EV-18 cell id in the summary.
- **Demo on real data: not yet. Two preconditions are unmet.** X-INT measured both (SKL-A):
  1. **The catalog is `0.7.dev` and unfrozen.** `campaign baseline` is refused with HB-CMP-006, and `.dev` passes count as probes, so `pilot pass` and `report` see no current pass. The demo needs the 0.7 release and freeze. In the plan that is R-86's Leader step after X-G3 (E3). Bringing it forward is your call (§7).
  2. **S1 as committed fails the real pilot gate.** `expected.reference` lacks NA for `behavioural_equivalence` and `regression_count`, so the gate reports "metric-not-recorded". The fix is an X-I `task.yaml` edit or a gate narrowing. Either moves S1's task version, and then F4's record is redone with it.
- **The demo can run today on the E2E fixtures** (`tests/test_e1_e2e.py::…happy_path`: create → baseline → pilot → admit → power → register → run → report on real modules). It cannot yet run on the real catalog and S1.

## 9. Next three actions

1. **Operator, 5 minutes:** the §1 restore and fast-forward. This unblocks the external runner (BASE-A) for E2-E4, so X-J1, X-A3, X-K1, X-K2, X-LG and X-G3 can go to Codex, Agy and Grok again.
2. **Decide §7.2 (F4) and fix S1's NA declarations in one X-I turn.** Then run J2 again (I have it scripted) and commit S1 `ready` together with its record. That clears precondition 2.
3. **Dispatch E2 on its own harnesses:** X-J1a (Codex, compiled) and X-J2b (Agy; needs X-E, X-LB0 and X-J2a, all joined). Meanwhile the Coordinator lands what it owes: W0 rev 6.11 (R-106 c4), the register entries for the candidate classes in §4, and GUARD-A's upgrade (the guard-file list in the brief template).
