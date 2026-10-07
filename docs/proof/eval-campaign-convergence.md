---
id: "proof-eval-campaign-convergence"
title: "Proof: eval campaign convergence (X-CV)"
type: proof-pack
status: draft
owner: "@timianmalloo"
phase: "Eval wave 2 · convergence"
tags: [proof, convergence, resume, tlc, discrimination]
links:
  - { to: design-eval-resume, rel: relates-to }
  - { to: brief-eval-x-cv, rel: relates-to }
  - { to: rulings-register, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  What X-CV proved before the ten final discrimination records: the ADR-0021 section 4 table is covered node by node,
  TLC --quick passes with every ADR-0015 section 7 invariant and NoLaunchAfterStop, the SM1 record mismatch has a
  measured cause, and the records table is waiting for the Leader.
---

# Proof: eval campaign convergence (X-CV)

Session `x-cv-e1e4`, branch `build/eval-x-cv`, base `be134319`. No `src/` change in this turn. Item 3 (the ten records) is the Leader's, after the join.

## 1. ADR-0021 section 4 table (W2)

`tests/test_resume_table.py` parses the window table in `docs/design/eval-resume.md` section 4. It asserts that every row names a node id, that pytest collects each node, and that none carries a skip or xfail marker. The kill-then-resume tests are X-K1's and X-K2b's, unchanged: no row lacked a node, so there is no second implementation.

- Red first: with the W2 node id changed to a node that does not exist (a copy of the doc, `HB_RESUME_TABLE_DOC`), the check failed on `W2: tests/test_resume.py::test_window[W2_does_not_exist] is not collected`. Commit `30ee6cbf` carries the line. Observed.
- Green: `tests/test_resume_table.py` 2 passed. Observed.
- Parsed: 19 window rows, 23 node ids (W5 names three, W12 names three; W10 names `[W10a_rows_none]` and "etc.", so only W10a is checked by name).
- Node run, once, every named node: 23 passed in 8.74 s (output `C:\t\cv\nodes-run.txt`, not committed). Observed.

## 2. TLC (W3)

`uv run python tools/check_models.py --quick`: exit 0, last line `all model checks passed`. Observed.

| check | result |
| --- | --- |
| liveness | ok, 170,552 states, 18 s |
| grading | ok, 39,191,368 states, 156 s |
| safety-small | ok, 13,362,512 states, 59 s |
| safety-turns | ok, 17,751,072 states, 85 s |
| seeded variants | 34/34 rejected by own target (including `stop_resume_launches` by NoLaunchAfterStop) |
| reachability witnesses | 4/4 violated |

`models/run_lifecycle.safety.cfg` lists, under INVARIANTS, all five ADR-0015 section 7 invariants (PromptOncePerTurn, SnapshotBeforeNextTurn, NoSnapshotInFlight, CrashedTurnPredicate, ArchiveExistsMeansComplete) and NoLaunchAfterStop. Observed.

Full bounds are cited, not re-run: `docs/design/eval-resume.md` section 5.4 (the quick run, 8 min 56 s, at `315cf1d4`) and W1-J's one-time 42-minute US-44 run. After section 5.4's run, the only change under `models/` is `12ed04d1`, which touches `models/README.md` only (docs, no model or cfg). Observed with `git log -- models/`.

## 3. Planned against actual per track (GO19)

Actual is each worker closing entry's `duration_seconds` in the audit log, one value per part. A planned figure appears only where the plan states one (Inferred in the plan); otherwise "not recorded". The joins' committer times were not read in this turn: "not recorded".

| track | planned | actual per part (s) |
| --- | --- | --- |
| X-LB1 | not recorded | 1816, 3846 (a third entry, 1625, closed conditions) |
| X-FIXE | not recorded | 1112, 2339 |
| X-K1d | about 65 min per external turn (plan line 216, Inferred) | 1335, 10031, 1323 |
| X-RS | not recorded | 221, 159, 900, 1387, 1324, 1661, 2659 |
| X-FLAKE | not recorded | 856 |
| X-CRLF | not recorded | 2138 |
| X-START | withdrawn (Ruling 113) | 416 |
| X-K2b | 1.1 h (plan line 263, Inferred) | 635, 242, 1304 (the Leader's entry for part 1: 974) |
| X-CV | 2 h (plan line 263, Inferred) | recorded in this session's closing entry |

## 4. SM1 record mismatch (W4)

Claim: SM1's record is named for task version `db5fedd40cb534bb`; its folder hashes to `50596a4576f52e23`.

- Observed: of the ten tasks, only S2 (expected: W1 edit) and SM1 differ from their record. `plan.task_version_hash` over `tasks/SM1` in every commit that touched it gives 50596a45 (`666ded0c`), 8111def3 (`6bb64508`), d7ab10e5 (`8d9b3bf0`), 533c68b1 (`1700ca0f`). None gives db5fedd4. So the record was taken on bytes that no commit holds.
- Observed: `tree_hash` normalises CRLF and `plan.py` has not changed since `ea0bb7a2`, which predates the record, so neither line endings nor the hash function explain it. The ready flip in `666ded0c` is ruled out.
- Observed: X-RDY follow-on K1's entry (`al-01M48NSHB05XMZG6VYBG20J30S`) records the trial at 13:04Z to 13:18Z, and `666ded0c` is committed at 13:15Z. The record was taken in the working tree before the commit.
- Observed: `task_version_hash` skips only `__pycache__`, and `.gitignore` ignores `.pytest_cache/` and `.ruff_cache/` (`git check-ignore`), so a cache folder inside `tasks/SM1` is invisible to git status and is hashed.
- Inferred (medium): the working tree held an ignored cache folder or file inside `tasks/SM1` when the record was taken. This is the same class that X-FIXV fixed for the vendoring check (`eee7ea67`). Not confirmed: that tree is gone. The Leader's re-record from a clean tree settles it; a fresh SM1 record that is HB-RDY-001 at once is a stop (assumption 2 of the brief). Class to consider: a task-folder hash that includes git-ignored files.

## 5. X-START's outcome

X-START (closing entry `al-01M49WN1ZMTX2XXXT2WXNTMPGG`, 416 s) measured no start-bound miss at `-n 4` and no discriminating load signal. Ruling 113 withdrew it as a build turn and keeps Ruling 112's design dormant. It re-opens on a measured reference start-bound miss (a `hosts.jsonl` line with `end: "start bound"`). Condition 6: X-CV proceeds at the current engine identity with no re-record from the ruling.

## 6. Final records

The Leader's command list is in `docs/coordination/coordinator-log/c50.md`.

| task | record file | identity_hash | bench validate line | start-bound ends (count) | maximum reference start_ms |
| --- | --- | --- | --- | --- | --- |
| S1 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |
| S2 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |
| RS1 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |
| RS2 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |
| RW1 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |
| RW2 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |
| NG1 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |
| NG2 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |
| SM1 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |
| SM2 | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records | pending: the Leader's records |

Ruling 113 condition 3, operative sentences: "At X-CV's join and at every later join that accepts a property record as final, the compiling Coordinator reads the ten records' `hosts.jsonl` (or the record evidence that points to it, `property.py:529`) for `end: "start bound"` and writes the count and the maximum reference `start_ms` in the join log. Zero hits: the records are accepted and the margin is recorded as a number. Any reference hit: that record is **not** accepted as final".

The Leader and the compiling Coordinator fill the cells at the records commit and the join.
