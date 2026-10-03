---
id: brief-eval-x-rw
title: "Brief X-RW: rework tasks RW1 (E2) and RW2 (E4) - authoring now, ready after X-J1 and X-J2b"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-property-tasks, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-RW authors tasks/RW1 and tasks/RW2 to W1-L sections 6.2-6.3 with Erratum 1 and W0 rev 6.6, on Claude Sonnet. Authoring stops at draft; the ready flip is a follow-on after X-J1 and X-J2b join."
---

# X-RW: rework tasks RW1, RW2

**Harness** Claude Code sub-agent · `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **session** `x-rw-e1e4` · **branch** `build/eval-x-rw` · **budget** 200 calls · 200k · 3 h per task (RW1 first, RW2 second) · **skill** `/new-bench-task` for each folder (the task contract in `tasks/README.md`).

**Design:** W1-L `docs/design/eval-property-tasks.md` §2, §3, §5, §6.1-6.3, §14, §15, **Erratum 1** (before §17); W0 rev 6.6 §1, §2 (task fields, variant carrier with (f) and (g), the overlay rule, the `ready` order), §7.

## Owned paths
`tasks/RW1/**`, `tasks/RW2/**`, and the RW1 and RW2 entries of `bench/bom.yaml` only.

## Scope of this session: `draft`, not `ready`
Author each folder fully (`task.yaml`, `prompt.md`, `turns/2.md`, `tests/turn1/`, `tests/turn2/`, `oracle/solutions/{reference,naive,alt}/turn-{1,2}/`, `oracle/variants.py`, `oracle/wrong_apps.py`, `oracle/evidence.md`, `NOTICE.md`, licence copy), with `status: draft`. Hidden tests run on the base (observed to fail) and on the reference turn trees (observed to pass) with the real `correctness.grade`, and both runs go in `oracle/evidence.md`. **Do not flip to `ready`**: RW `ready` needs X-J1 and X-J2b (W0 rev 6.6 R6.6c). The Leader dispatches the `ready` follow-on in this tree after both join.

## Acceptance items (RV-TA W1-L rev 2; W1-L Erratum 1)
1. **R2-1:** variant names match `^[a-z0-9]{1,16}$` (`ratiohigh`, `t1regress`, `t2short`, `duplicate`, `deaddelegate`, `padturn1`, `nohookorder`, `ignorereturn`); `oracle/variants.py` is W0's one `VARIANTS` literal; for these check-less tasks `flips` lists metric ids; every `edits[].file` starts with `turn-<n>/`; a whole-file or new-file edit uses `old: ""`. A test loads each `variants.py` through W1-E's reader and fails on a bad name (in this session if X-E has joined, else in the `ready` follow-on).
2. **R2-2:** a fixture asserts that `humanfriendly/tests.py` is a test path under `_changes.is_test_path(path, base_paths)` (W0 rev 6.6 §13), and the same over RW2's base test layout (`test_schedule.py`). Write the expected classification now as data (test paths and product paths of each base, in `oracle/evidence.md`); the `ready` follow-on asserts it through `is_test_path` once X-J2a has joined (no `xfail`, no import of a missing function).
3. **R2-7:** one stub per task that returns a unique sentinel, and `test_<id>_stub_fails_every_hidden_test`.
4. **R2-4:** the seeded-disagreement readiness fixture for RW1 is written now; it runs in the follow-on (X-J2b's multi-turn path). Cite W1-E T-E11/T-E12, never `test_readiness_names_metric_expected_observed`.
5. `expected` values stay `Inferred` with the design targets until the follow-on's discrimination record measures them (FIXT-A; W1-L §5.3: no `<...>` placeholder at `ready`). Blocking items B-RW1, B-RW2 are closed only by measured counts.
6. EV-1 (valid task), EV-4 (the ceiling separates reference and naive) shown through the engine in the follow-on.

## Exit
E1 README §3 join gate (the full suite stays green; the task folders add tests). Report per E1 README §4, plus the per-task state (`draft`, what the follow-on needs).
