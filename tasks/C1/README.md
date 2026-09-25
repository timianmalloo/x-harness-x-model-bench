# C1 — Concept-oriented requirements to architecture

**Status: ready.** `prompt.md`, a pinned source, `workspace/`, hidden unittest tests, and an oracle that fails on the base tree and passes on `oracle/reference/` are all present. `uv run bench validate` accepts the folder. The wave-3 judge does not run in this slice; `oracle/rubric.md` holds the rubric text it will use.

## Problem

ProjDevBench problem **011, STLite Priority Queue** (ACMOJ id 2623), category Data Structure, difficulty Easy, at commit `9af6f408e45047947d2a6d1d27b64828c3eb913d`.

The paper groups its 20 problems as concept-oriented tasks and real-world application scenarios. Problem 011 is one concept: a `priority_queue` whose `merge` must be O(log n), which forces a mergeable heap and an exception-rollback rule. That is an architecture decision, and the spec is small enough for a local oracle. Management and storage problems (003, 004, 015, 016, 017) are the application scenarios, so they were not used. A+B (001) is a concept problem too, and it does not force a structure choice.

Requirements in `prompt.md` are that problem's behavioural requirements, restated as a Python module because the phase-1 correctness runner is unittest (R-7 condition 3: local tests, ACMOJ is not used). The same prompt is what every harness receives.

## Source pin

`git ls-remote https://github.com/zsworld6/projdevbench.git refs/heads/main` on 2026-09-25 returned `9af6f408e45047947d2a6d1d27b64828c3eb913d`. A blobless clone of that commit matches. `source.repo` and `source.commit` in `task.yaml` record it.

## Licence

R-7 records the repository as MIT. At this commit, `README.md` and `README_zh.md` each contain a "License" section whose body is the words `MIT License`. `git ls-tree -r` of the commit lists no `LICENSE`, `LICENSE.md`, or `COPYING`. Neither README contains a copyright line or the MIT permission text. `source.license` is `MIT`. `source.copyright` is null because there is no copyright line to read. No `LICENSE` file was copied into this folder; inventing one would state a copyright holder the upstream tree does not.

## Oracle

Hidden tests live in `tests/test_c1_hidden.py` and are not in `workspace/`. The reference solution lives in `oracle/reference/` only. Runs, commands, exit codes, and failing names are in `oracle/evidence.md`.
