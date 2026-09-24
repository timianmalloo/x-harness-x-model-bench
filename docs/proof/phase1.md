---
id: "proof-phase1"
title: "Proof Pack: phase 1 walking skeleton"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, phase1, e2e, mutation, red-first]
links:
  - { to: design-phase1-walking-skeleton, rel: implements }
  - { to: coordination-phase1-finish, rel: relates-to }
  - { to: mutation-record-phase1, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  Phase 1 is usable. The real 4-cell E2E (Claude Code and Codex, pack on and off) passes on the integrated branch with
  real model calls: all cells valid, the ledger verifies, re-grading is byte-identical, and the report renders offline.
  Every pre-merge finding was closed red-first across tracks T1–T9, and every mutation file is killed. N5 (user skill
  roots reaching Codex cells) is disclosed and flagged, not fixed.
---

# Proof Pack: phase 1 walking skeleton

- **Change:** `impl/phase1`, from `e5ee302` (main before the finish plan) to the close commit. Joins: T5 `f47c5c9`, T3 `eb3ac27`, T4 `861ac76`, T2 `e69dc38`, T1 `9c32b00`, T6 `51a39e1`, T8 `0e24cb9`, T9 `81c5b10`, T11 `e37d223`, T10 `db2cca4`, T12 `f28b272`.
- **Spec / design:** `docs/specs/harness-bench.md` · `docs/design/phase1-walking-skeleton.md` (v4, native cells) · `docs/design/run-lifecycle-model.md`.
- **Tier:** T2.
- **Author / date:** the Coordinator seat (Claude Code, Opus 5.5), 2026-09-24. Plan: `docs/coordination/coordination-phase1-finish.md`. Run record: `docs/coordination/coordination-phase1-finish-run.md`.

## Claims & evidence

### Claim 1: the walking skeleton runs end to end with real harnesses and real models (M1, "usable")

**Evidence:** `tests/e2e/test_walking_skeleton.py` passed on the final integrated branch (`b641814`, after every join through T12) in run `e2e-1790255669`, 2026-09-24:
- `2 passed, 1 xfailed in 188.72s` (the xfail is Claim 5). An earlier run, `e2e-1790239442`, also passed, at `d13b222`;
- the real `bench` CLI, the pinned builds (Claude Code 2.1.274, Codex 0.156.0) and the operator's subscription logins;
- the matrix `bench/matrix.phase1.yaml`: X1 × {cc-sonnet, codex-sol} × pack {on, off} × 1 repetition.

**What the test asserts** (each assertion is on the rendered state, not an exit code alone):

| assertion | spec | observed |
| --- | --- | --- |
| 4 cells terminal, each with an outcome | design E2E exit list | `Outcomes: completed 4.` |
| the prompt each agent received is the plan's, byte for byte (hash from the harness's own session record) | US-10 | equal for all 4 cells (it failed for Codex pack-on in run 2; fixed by T8) |
| every cell valid: a served model, at least one call, no model mismatch | US-11 | `Validity: valid 4.` |
| the executed build is the planned build (sha256) | US-12 | equal for all process starts |
| zero permission requests | US-14 | `[0, 0, 0, 0]` |
| `bench verify` exits 0: ledger chains, seals, heads, archive hashes and bytes, both before and after the re-grade | US-19, R-2 | `verify: ok` twice (the second run was added for N6) |
| a re-grade gives a byte-identical canonical export | US-26 | equal |
| `report.html` renders with no network reference | US-40 | no `http(s)://`, `<script`, `@import`, `url(`, `<link` |
| no process remains in any cell job | ADR-0013 | all dead |
| teardown removes the run's working copies, after they are archived | US-19, design E2E exit list | `cells/<run>` gone |
| the run's folder is removable afterwards (nothing left open or read-only) | CLN-A | removed (it failed before T9) |

**Measured cost of the run** (`docs/proof/phase1-e2e-last.json`, parallelism 2):

| cell | outcome | wall | tokens (all models) | pass@1 |
| --- | --- | --- | --- | --- |
| X1.cc-sonnet.pack-on.r1 | completed | 18.1 s | 321,317 | 1 |
| X1.cc-sonnet.pack-off.r1 | completed | 12.6 s | 218,955 | 1 |
| X1.codex-sol.pack-on.r1 | completed | 142.2 s | 565,803 | 1 |
| X1.codex-sol.pack-off.r1 | completed | 29.5 s | 79,015 | 1 |

`plan` took 0.4 s and `run` (all cells, then grading) took 147.7 s.

In the earlier run (`e2e-1790239442`), the Codex pack-on cell took 53.5 s and 190,824 tokens. That is one sample each, and model behaviour varies between runs (residual 3). Cost per cell is `NA`: the price list has no entry for `claude-haiku-4-5-20251001` (Claude Code's helper calls) or `gpt-6-sol`. The report says so for each cell, as US-23 requires: a sourced basis, or NA (see Residual risk 1).

**Oracle:** the E2E runs the real composition root (`cli.main`) and asserts on ledger rows, native session records and the rendered report. It fails when:
- any cell ends invalid;
- a prompt differs by one byte;
- a build hash differs;
- a verify check fails;
- any artifact of the run is left behind.

Its history shows it can fail. Run 1 failed on HB-CELL-113 (the race, T6). Run 2 failed on US-10 (the Codex reader, T8). Run 3 passed but left a folder, which led to T9 and the removal assertion.

**Red observed before green:** yes, as runs 1 and 2 above.

**Confidence:** Verified for this matrix, on this host, on 2026-09-24.

**Residual risk:** one repetition per combo, so no interval (`n < 2`). One task (X1). Model behaviour is not deterministic. A future run can fail on the model's side while the engine stays correct.

### Claim 2: every pre-merge review finding was closed red-first

**Evidence:** one findings file per track. Each has, per finding, the test node, the test-only red commit, the failing line at red and the fix commit. The Coordinator re-ran red commits from every track in throwaway worktrees and saw them fail. It also checked that every cited SHA exists in history; one apparent miss, `5f1c0de`, is a fake credential suffix, not a SHA.

| track | findings | file | Coordinator verification |
| --- | --- | --- | --- |
| T1 engine hardening | the 17-item checklist plus 8b (budget kill after turn end, cleanup after seed/spawn failure, archive failure recorded, broken-ledger futures, worker-side validation, `turn_usage` per model, one stop path, HB-RUN-002 once, `engine.log` extras, grading heartbeat, `updates`/`last_update_ms`, ENOSPC → disk, HB-RUN-005, T-LOG-nosecret, T-ENG-suspend / T-JOB-daemon / T-ARC-full, one transition table, Simplifier minors) | `findings-T1.md` | two reds re-run; `engine.json` 44/44 |
| T2 ledger and verify | T2-1..T2-12 (tamper probes exit 5, `grading.completed.heads` per R-2, D2 hypothesis properties, D6 golden ledgers, poison writer, the T3 seam) | `findings-T2.md` | two reds re-run |
| T3 process edges | T3-1..T3-10 (driver, procs, telemetry; D5/D7 replay) | `findings-T3.md` | two reds re-run; `t3.json` 15/15 |
| T4 surfaces | T4-1..T4-9 (exact-value credential scan, one cell-id definition, budgets from `prompt_sent`, R-3 status fields, id validation, UI states, one stop rule, N5 flag) | `findings-T4.md` | status 12/12, report 21/21, cli 11/11 |
| T5 N5 spike | a negative result (Claim 5) | `findings-T5.md` | the canary run observed |
| T6 workspace race | HB-CELL-113 (E2E run 1) | `findings-T6.md` | red `0082875` re-run |
| T8 reader and paths | US-10 Codex reader; relative `--tools-dir` (E2E run 2) | `findings-T8.md` | both reds re-run; fixture scanned |
| T9 cleanup and log | a lost build's temp folder; engine log handlers (E2E run 3) | `findings-T9.md` | red `e225ff5` re-run, 4 of 4 failed as stated |
| T11 verify later pass | Test Architect N1: a re-sealed later pass with no `grading.completed` | `findings-T11.md` | red `8edd94f` re-run (`0 == 5`); `views.json` 34/34 |
| T10 engine mutation | the 466 engine mutants never run; the kill-retry cap drift (60 s against the design's 30 s) | `findings-T10.md` | cap red `70531dc` re-run (`32.0 != 30`); two kills and one equivalent spot-checked |
| T12 mutation re-run | 29 overstated kills; one false equivalence | `findings-T12.md` | three overstated kills re-run before and after `a0c4f52` |
| T7 (Coordinator) | E2E-E piped gate; TOOL-A stale bytecode in `mutate_check` | this pack, `defect-classes.md` | reds `291468b`, `3ecd1eb` |

**Oracle:** a test that failed on the commit before its fix, for the stated reason, backed by a named mutant killed by that test.

**Red observed before green:** yes, for every defect, with these exceptions:
- T1 items 14 and 15 were missing controls rather than defects. Their red is shown under a named mutant.
- **T4-1's red commit `3c6db13` is not test-only.** It adds `src/harness_bench/report/credentials.py` (99 lines), and its red is a signature `TypeError`, not the behaviour under test (found by the Test Architect's re-review, N3). The helpers are backed by `report.json` mutants. The behaviour tests (`test_a_rotated_token_found_only_in_an_archived_home_is_refused` and the base64/URL-encoded variant) use a token that matches none of the shape regexes, so only the exact-value path can catch it.
- The Test Architect checked 18 other sampled reds (`git show --stat`), and none touches `src/`.

**Confidence:** Verified for the sampled reds and all mutation files. For reds the Coordinator did not re-run, it is as reported by the track (Inferred).

**Residual risk:** see the list below.

### Claim 3: the mutation bar is met

**Evidence:** `docs/notes/mutation-record-phase1.md`.
- **cosmic-ray, every mutant:** 2699 across lifecycle, errors, engine (all 767), ledger, views and grade. Each was run, then re-run with bytecode off (T12, `src` at `ceed6c1`): 2267 killed, 432 argued equivalent, **0 open**.
- **The re-run corrected the per-track records.** 29 mutants recorded killed were not (now killed by test-only `a0c4f52`), and one engine equivalence argument was wrong (L394, killed).
- **Hand-written mutations:** all 13 `tests/mutations/*.json` files, 198 entries, were re-run with the fixed checker at `ceed6c1`. All 198 were killed, and `src` was clean afterwards. This supersedes the earlier 188/188 at `d13b222`, which ran on the pre-TOOL-A checker.
- **Design drift found by the engine run:** the kill-retry cap was 60 s against the design's 30 s. It is fixed red-first (T10: `70531dc` → `e10b1e9`).

**Oracle:**
- The hardened `tools/mutate_check.py` counts a kill only when pytest exits 1 with a named test failing (`ae6e8f0`). Since `6d26c76`, it writes no bytecode from a mutant (TOOL-A: red `3ecd1eb`).
- For cosmic-ray, the Coordinator re-verified sampled dispositions with that checker:
  - T10's two kills and one equivalent;
  - T12's three overstated kills: survived at `ceed6c1`, killed at `a0c4f52`.

**Red observed before green:** n/a. A mutant is a seeded red.

**Confidence:** Verified for 0 open mutants, and for every disagreement T12 dispositioned one at a time.

**Residual risk:** cosmic-ray counts any non-zero exit or timeout as KILLED (TOOL-B), so its 2267 kills are an upper bound. They were not each re-checked for a named test failing. A named-test re-derivation from `cosmic-ray dump` is the unbuilt control.

### Claim 4: the start-benchmark skill edit is better than the old skill (A6)

**Evidence:** `docs/notes/a6-start-benchmark-golden-cases.md`. Five golden cases, same model (sonnet): the new skill passes 5 of 5; the old skill passes 1. The replies are committed in `docs/proof/a6-replies/`. Scoring the compiled-matrix replies again at the close with `tools/a6_check_matrix.py` gave exit 1 for both old replies and exit 0 for both new ones.

**Confidence:** Verified for these cases. One sample per case, so non-determinism is not measured. The new skill's C2–C4 replies were not saved; the note's table is their only record.

### Claim 5: N5 is disclosed, flagged and guarded, not fixed (Ruling R-5)

**Evidence:**
- Inside a cell, Codex 0.156 reads `~/.agents/skills` from the operator's profile. Neither a per-cell `HOME`/`USERPROFILE` nor `features.skip_host_skill_discovery` removes it (`docs/notes/spike-n5-codex-skill-roots.md`).
- The US-13 canary in the final E2E printed `US-13 codex: ... leaked into the probe ['skill (~/.agents/skills, via USERPROFILE)']`, and the test stays `xfail(strict=True)`. If Codex stops leaking, the strict xfail fails and forces this record to be revisited.
- Claude Code showed no leak.
- The report flags it for the run: `user-config exposed (N5): see docs/notes/spike-n5-codex-skill-roots.md, the US-13 canary`. That line appeared in the final E2E's CLI output, so the flag is proven through the full ledger-to-report path. That closes T4's residual "no CLI-level test of the N5 flag".

**Exposed cells:** every Codex cell, pack on or off. The operator's user-level skills (the skill observed in this run was `microsoft-foundry`) can shape a Codex agent's behaviour. Compare Codex results with that in mind.

**Also seen:** a `<recommended_plugins>` block in the Codex pack-on context. Its source is not verified; it may be the operator's plugin marketplace configuration. It is flagged, not investigated.

**Confidence (split per ruling R-6):**
- **Verified:** the leak exists, and the report flags it. Both were observed in the canary and in the report.
- **Inferred:** the leak is the same with the pack on and off. The model: the leak path, `~/.agents/skills`, is resolved from the operator's profile, and the pack does not touch it. **Not measured**, because the canary's probe is always a bare cell. The probe that would decide it: run the US-13 canary with the pack seeded into the probe cell, pack on and pack off, and compare the leaked sets. Until then, pack-on against pack-off comparisons for Codex rest on that model.
- **Flagged:** the `<recommended_plugins>` block. Its source is unverified, and it was seen only with the pack on.

**The skill name is now measurement-emitted (R-6 condition 3).** The canary in the final E2E printed `US-13 codex: ... leaked items ['microsoft-foundry']`. Its positive control showed the canary for both harnesses (N2), and Claude Code's leaked items were `[]`.

## Failure modes found by the real E2E (none were visible in unit tests)

| run | failure | class | fixed by | proven by |
| --- | --- | --- | --- | --- |
| 1 | two workers built one task source / pack checkout at once; `os.replace` failed (HB-CELL-113) | CONC-A | T6 `_land` | concurrency tests, red `0082875` |
| 2 | the Codex reader took the injected `# AGENTS.md instructions` block as the prompt (US-10) | RIG-D | T8 `_is_injected_context` | real scrubbed pack-on record, red `05f52fa` |
| 2 | a relative `--tools-dir` resolved under the cell's working copy (HB-CELL-113) | PATH-A | T8 `_resolve_paths` | red `62c38ba` |
| 3 | the race loser's temp folder stayed (read-only git objects) | CLN-A | T9 `_discard` | red `e225ff5` |
| 3 | log handlers accumulated; a run's `engine.log` stayed open | CLN-A | T9 `configure_logging` / `cmd_run` | red `e225ff5` |

Each class is in `docs/lessons/defect-classes.md` with its sweep and control.

## Verification commands

```
uv run pytest -q -p no:cacheprovider -m "not credentials"   # 592 passed, 5 deselected at the T12 join (recount)
uv run ruff check src tests tools                            # clean
uv run pytest -q -p no:cacheprovider -m "" tests/e2e -s -rf  # real models: 2 passed, 1 xfailed
uv run python tools/mutate_check.py tests/mutations/<file>.json   # per file: "every mutation killed"
```

A gate's exit status is read on its own line (CT27). `tools/heredoc_guard.py` now blocks a piped gate (E2E-E).

## Flagged risks / residual unknowns

1. **Cost is `NA` for every cell.** The price list lacks `claude-haiku-4-5-20251001` and `gpt-6-sol`. To compare cost, add sourced prices for both. Guessed prices are not acceptable.
2. **N5** (Claim 5). Codex results carry the operator's user-level skills. **Next step for the human (R-6):** run the pack-seeded canary probe. R-5 reopens if the pack-on leaked set differs from pack-off, or if `<recommended_plugins>` turns out to have a pack-dependent source.
3. **One repetition, one task.** No confidence interval until `repetitions ≥ 2`.
4. `last_update_ms` records null. Seam `req-01M38KX8503601BEP857749VVF` (T1 → T3: `TurnResult.last_update_seconds`) is still open, because T3 had closed. It is a phase-2 follow-up.
5. `cli_table.render` prints cell labels to stdout before `report.html`'s credential scan runs (T4). A credential that leaked into a label would reach the terminal. Labels are built from plan ids, which are validated against a regex (T4-5), so this needs a plan-id path to carry a secret. It is flagged for the Security lens.
6. `procs.spawn()` can raise `TimeoutExpired` before `job.close()` after a failed assignment. `host.py` does not check the results of `GlobalMemoryStatusEx` and `QueryUnbiasedInterruptTime` (T3).
7. A grading pass without `heads` (a ledger from before R-2) gets only a warning on a cut or a deleted segment. Truncating past `run.completed` shows as incomplete, not as an integrity error (T2, per R-2).
7a. **A later grading pass can be deleted whole without detection** (Test Architect N1, shape A; `findings-T11.md`).
    - `run.completed` names only the in-run pass, and no later pass records the heads of an earlier one. So deleting all four segments of a later `bench grade` pass leaves an internally consistent ledger, and views fall back silently to the previous pass.
    - Cutting a later pass's events segment without re-sealing it looks like an honest crash, which is a warning.
    - T11 closed only the re-sealed form (B), which is now HB-LED-002 and exit 5.
    - Detecting (A) needs an anchor outside the run's own segments. That is a design decision for ADR-0006, not a `verify` change.
    - Until then, the scores of a run graded more than once are only as trustworthy as the filesystem that holds them.
8. `peak_memory` and `cpu_ms` are null when a job query fails (T1).
9. The D5 replay transcripts are partly schema shapes, not recordings (T3).
10. cosmic-ray kill counts are non-zero-exit verdicts, not named-test failures (TOOL-B, Claim 3). The engine's partial scope is closed (T10, T12).
11. Test-fixture teardowns still use `rmtree(ignore_errors=True)`. About 170 folders from earlier test runs remain under `C:/Projects/bench-test` (CLN-A, partially controlled). Deleting them was refused by this session's permission check, so the human deletes them.
12. `verify-ruling-citations.py` checks nothing here (GATE-A): it reads only `### Ruling NN` headings, and the rulings use `## R-n`. The rulings R-1..R-5 are cited by hand in this pack and the design; no gate checks those citations.

## Status & next action

| | |
| --- | --- |
| **Completed** | Phase 1 walking skeleton, usable: the real E2E passes; every findings file is red-first; all mutation files are killed; A6 committed; deviations and the defect register updated. |
| **Remaining** | The Test Architect's re-review (M2), then fast-forward `main` and push. The human's list: prices (1), N5 review (2), grok ≥ 1.0.34 or agy's mode, then re-qualify (R-4), the leftover folders (11), the ruling heading format (12). |
| **Best next action** | Run `bench plan --matrix <yours> --confirm`, then `bench run <id>`, then `bench report <id>` (the `start-benchmark` skill walks through it). |

## Gate record

### Round 1: Test Architect, Adversary Mode, at `2da830a` (2026-09-24): **BLOCK**

The reviewer re-ran the suite (516 passed), `ledger.json` (20/20) and `engine.json` (44/44). It read the sampled reds and the cited tests, and probed the golden ledger.

| original item | verdict |
| --- | --- |
| verify misses a cut or deleted segment | CLOSED for the R-2 scope |
| mutation bar | CLOSED for ledger, errors, views and grade. **OPEN for `engine.py`:** 466 of 765 mutants were not run. The partial-scope deviation was written by the author, so it cannot clear the author's veto |
| E2E, canary and Proof Pack | CLOSED |
| exact-value secret scan, T-LOG-nosecret, T-FI-unkillable, fault tests, D6 golden ledgers | CLOSED |
| D5/D7 transcript replay | ACCEPTED-AS-DISCLOSED, on condition that a full ACP transcript is captured at the next E2E |
| cosmic-ray instead of mutmut | ACCEPTED-AS-DISCLOSED |
| N5 strict xfail | ACCEPTED-AS-DISCLOSED, with N2 below |

**New findings, and how each is handled:**
- **N1 [Major]:** `verify` exits 0 when a later grading pass is deleted, or cut and re-sealed. **Track T11 (joined `e37d223`)** makes the re-sealed form HB-LED-002, exit 5 (red `8edd94f`, fix `bdcd2ef`). Whole deletion is disclosed as residual 7a.
- **N2 [Major]:** the canary had no positive control, and its xfail had no `raises=`. Fixed in `6362c6e`.
- **N3 [Minor]:** Claim 2 overstated test-only reds (T4-1). Corrected above.
- **N4 [Minor]:** R-5's claim that the leak is the same with the pack on and off is unmeasured. Routed to the Owner.
- **N5 [Nit]:** the report points to the evidence instead of naming the skill. Routed to the Owner.
- **N6 [Nit]:** the E2E did not run verify after the re-grade. Fixed in `6362c6e`.
- **Required item 1: done, no waiver.**
  - **T10 (joined `db2cca4`)** ran the 466 remaining `engine.py` mutants: 0 open. It found and fixed the kill-retry cap drift, and found TOOL-A in `mutate_check`, which is fixed.
  - **T12 (joined `f28b272`)** re-ran all 2699 cosmic-ray mutants with bytecode off: 0 open. It closed 29 overstated kills with tests.
