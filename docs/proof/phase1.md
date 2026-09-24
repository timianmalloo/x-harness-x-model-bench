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

- **Change:** `impl/phase1`, from `e5ee302` (main before the finish plan) to the close commit. Joins: T5 `f47c5c9`, T3 `eb3ac27`, T4 `861ac76`, T2 `e69dc38`, T1 `9c32b00`, T6 `51a39e1`, T8 `0e24cb9`, T9 `81c5b10`.
- **Spec / design:** `docs/specs/harness-bench.md` · `docs/design/phase1-walking-skeleton.md` (v4, native cells) · `docs/design/run-lifecycle-model.md`.
- **Tier:** T2.
- **Author / date:** the Coordinator seat (Claude Code, Opus 5.5), 2026-09-24. Plan: `docs/coordination/coordination-phase1-finish.md`. Run record: `docs/coordination/coordination-phase1-finish-run.md`.

## Claims & evidence

### Claim 1: the walking skeleton runs end to end with real harnesses and real models (M1, "usable")

**Evidence:** `tests/e2e/test_walking_skeleton.py` passed on the integrated branch (`d13b222` plus the E2E's own cleanup change) in run `e2e-1790239442`, 2026-09-24:
- `2 passed, 1 xfailed in 111.19s` (the xfail is Claim 5);
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
| `bench verify` exits 0: ledger chains, seals, heads, archive hashes and bytes | US-19, R-2 | `verify: ok` |
| a re-grade gives a byte-identical canonical export | US-26 | equal |
| `report.html` renders with no network reference | US-40 | no `http(s)://`, `<script`, `@import`, `url(`, `<link` |
| no process remains in any cell job | ADR-0013 | all dead |
| teardown removes the run's working copies, after they are archived | US-19, design E2E exit list | `cells/<run>` gone |
| the run's folder is removable afterwards (nothing left open or read-only) | CLN-A | removed (it failed before T9) |

**Measured cost of the run** (`docs/proof/phase1-e2e-last.json`, parallelism 2):

| cell | outcome | wall | tokens (all models) | pass@1 |
| --- | --- | --- | --- | --- |
| X1.cc-sonnet.pack-on.r1 | completed | 23.4 s | 324,698 | 1 |
| X1.cc-sonnet.pack-off.r1 | completed | 12.5 s | 219,084 | 1 |
| X1.codex-sol.pack-on.r1 | completed | 53.5 s | 190,824 | 1 |
| X1.codex-sol.pack-off.r1 | completed | 25.8 s | 63,399 | 1 |

`plan` took 0.4 s and `run` (all cells, then grading) took 69.5 s. Cost per cell is `NA`: the price list has no entry for `claude-haiku-4-5-20251001` (Claude Code's helper calls) or `gpt-6-sol`. The report says so for each cell, as US-23 requires: a sourced basis, or NA (see Residual risk 1).

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

**Oracle:** a test that failed on the commit before its fix, for the stated reason, backed by a named mutant killed by that test.

**Red observed before green:** yes, for every defect. T1 items 14 and 15 were missing controls rather than defects. Their red is shown under a named mutant.

**Confidence:** Verified for the sampled reds and all mutation files. For reds the Coordinator did not re-run, it is as reported by the track (Inferred).

**Residual risk:** see the list below.

### Claim 3: the mutation bar is met, with one disclosed gap

**Evidence:** `docs/notes/mutation-record-phase1.md`.
- cosmic-ray 8.7.0 has no open mutant over lifecycle, errors, 299 of engine's 765 mutants, ledger, views and grade.
- All 13 `tests/mutations/*.json` files, 188 entries, were re-run under the hardened checker on the integrated code (`d13b222`, after the last join). All 188 were killed, and `src` was clean afterwards.

**Oracle:** the hardened `tools/mutate_check.py` (`ae6e8f0`, `9dcbc90`) counts a kill only when pytest exits 1 with a named test failing. A timeout or an error is not a kill. The first sweep under this rule exposed one false kill, `engine.json`'s "budget never enforced", which was killed only by a timeout; T1 fixed it.

**Red observed before green:** n/a. A mutant is a seeded red.

**Confidence:** Verified.

**Residual risk:** `engine.py`'s 466 out-of-scope cosmic-ray mutants (`run`, `_launch`, `_run_cell`, `_archive`, `_classify`, `configure_logging`, `_job_query`, `_confirm`). They are covered only by hand-written entries and by the unit, conformance and E2E tests.

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

**Confidence:** Verified (observed in the canary and the report).

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
uv run pytest -q -p no:cacheprovider -m "not credentials"   # 516 passed, 5 deselected at the T9 join (recount)
uv run ruff check src tests tools                            # clean
uv run pytest -q -p no:cacheprovider -m "" tests/e2e -s -rf  # real models: 2 passed, 1 xfailed
uv run python tools/mutate_check.py tests/mutations/<file>.json   # per file: "every mutation killed"
```

A gate's exit status is read on its own line (CT27). `tools/heredoc_guard.py` now blocks a piped gate (E2E-E).

## Flagged risks / residual unknowns

1. **Cost is `NA` for every cell.** The price list lacks `claude-haiku-4-5-20251001` and `gpt-6-sol`. To compare cost, add sourced prices for both. Guessed prices are not acceptable.
2. **N5** (Claim 5). Codex results carry the operator's user-level skills.
3. **One repetition, one task.** No confidence interval until `repetitions ≥ 2`.
4. `last_update_ms` records null. Seam `req-01M38KX8503601BEP857749VVF` (T1 → T3: `TurnResult.last_update_seconds`) is still open, because T3 had closed. It is a phase-2 follow-up.
5. `cli_table.render` prints cell labels to stdout before `report.html`'s credential scan runs (T4). A credential that leaked into a label would reach the terminal. Labels are built from plan ids, which are validated against a regex (T4-5), so this needs a plan-id path to carry a secret. It is flagged for the Security lens.
6. `procs.spawn()` can raise `TimeoutExpired` before `job.close()` after a failed assignment. `host.py` does not check the results of `GlobalMemoryStatusEx` and `QueryUnbiasedInterruptTime` (T3).
7. A grading pass without `heads` (a ledger from before R-2) gets only a warning on a cut or a deleted segment. Truncating past `run.completed` shows as incomplete, not as an integrity error (T2, per R-2).
8. `peak_memory` and `cpu_ms` are null when a job query fails (T1).
9. The D5 replay transcripts are partly schema shapes, not recordings (T3).
10. `engine.py` has partial cosmic-ray scope (Claim 3).
11. Test-fixture teardowns still use `rmtree(ignore_errors=True)`. About 170 folders from earlier test runs remain under `C:/Projects/bench-test` (CLN-A, partially controlled). Deleting them was refused by this session's permission check, so the human deletes them.
12. `verify-ruling-citations.py` checks nothing here (GATE-A): it reads only `### Ruling NN` headings, and the rulings use `## R-n`. The rulings R-1..R-5 are cited by hand in this pack and the design; no gate checks those citations.

## Status & next action

| | |
| --- | --- |
| **Completed** | Phase 1 walking skeleton, usable: the real E2E passes; every findings file is red-first; all mutation files are killed; A6 committed; deviations and the defect register updated. |
| **Remaining** | The Test Architect's re-review (M2), then fast-forward `main` and push. The human's list: prices (1), N5 review (2), grok ≥ 1.0.34 or agy's mode, then re-qualify (R-4), the leftover folders (11), the ruling heading format (12). |
| **Best next action** | Run `bench plan --matrix <yours> --confirm`, then `bench run <id>`, then `bench report <id>` (the `start-benchmark` skill walks through it). |

## Gate record

The Test Architect re-review for M2 is recorded below when it returns.
