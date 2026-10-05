---
id: brief-eval-x-i5
title: "Brief X-I5: S1 fix - the F4 payload drop and the two NA declarations (E1 follow-on, Sonnet)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: coordination-e2e4, rel: implements }
  - { to: brief-eval-x-i, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-19"
summary: "X-I5 applies the operator's decision (2) of 2026-10-05 to S1: the check keeps payloads A0, B2, B3 and C0 and drops the other nine, expected.reference declares NA for behavioural_equivalence and regression_count, and S1 gets a new task version; the strict-xfail marker at tests/test_e1_e2e.py:327 is removed when its leg passes. Sonnet, from the integration head; the Leader then runs bench discriminate S1 and commits S1 ready with its record (Coordinator #30)."
---

# X-I5: the S1 fix (F4 drop and NA declarations)

Written by Coordinator #30 on `coord/eval-c30-t0` at `37ec0585` (`integrate/e2e4-18`), from `x-i.md` (the X-I4 section) and the operator's decision (2) of 2026-10-05 (`docs/coordination/eval-wave2-e1/overnight-2026-10-05.md` section 7). Plan row: `docs/coordination/coordination-e2e4.md`, track X-I5. Where this brief differs from `docs/coordination/eval-wave2-e1/README.md` sections 1-4, this brief wins.

## Seat and tree
- **Seat:** Claude Code Agent tool, `model: sonnet`, served `claude-sonnet-5-5` expected (R-91). The served id is the first line of your report.
- **Session** `x-i5-e1e4` · **branch** `build/eval-x-i5` · no contract file.
- **Base:** the integration head at dispatch (`integrate/e2e4-18` or its successor), never `main`. From the primary: `python docs/ai-forward-pack/scripts/coord-core.py worktree new --branch build/eval-x-i5 --session x-i5-e1e4 --base <integration head>`. Record the base SHA. Work only in the printed tree by absolute path. Never `EnterWorktree`; never checkout or switch in the primary. `AGENT_SESSION=x-i5-e1e4` inline on every commit and coord call.
- **Leader** `leader-e1e4`, epoch 18. **Owner** `owner-fable`. If the epoch changes, stop at your next commit and report.

## Depends on (check each on your base with `git merge-base --is-ancestor <sha> HEAD`; stop and report the one that is missing)
- X-I4's merge `36caa053` (payload ids as the `inj` clauses; `clauses.json`; task version `cafd0092`).
- X-INT's merge `13db8d6f` (`tests/test_e1_e2e.py` and its `:327` leg).

## The decision you apply
The operator's decision (2), 2026-10-05: "S1: keep A0, B2, B3 and C0, and drop the other nine." Its basis is the J2 record on `leader/s1-discrimination` at `5f54cf0b` (not merged): only A0, B2, B3 and C0 exploit any variant; A1, A2, A3, B0, B1, B4, C1, C2 and C3 exploit nothing. You apply the decision; you do not re-decide it.

## State on the base (Coordinator #30 opened each at `37ec0585`)
- `tasks/S1/oracle/check/check.py:27-29`: `INJ_A` has four payloads (A0..A3), `INJ_B` five (B0..B4), `INJ_3` four (C0..C3). `payload_ids(prefix, hits)` (`:33`) builds each id from the tuple's prefix and the payload's **index**. `inj_1` (`:91-102`) and `inj_3` (`:105-108`) try every payload.
- `tasks/S1/oracle/variants.py` declares the measured clauses: m1 `inj-1: A0,B2,B3`, m12 `B2,B3`, m13 `B2`, m8 `inj-3: C0`.
- `tasks/S1/task.yaml:37-44`: `expected.reference` holds `property_check_pass` and `exploit_probes_blocked` only. The NA form is `{ na: "<reason>" }` (precedent `tasks/NG1/task.yaml:39`); `readiness.expected_na` (`src/harness_bench/readiness.py:94`) reads the reference role only.
- `tests/test_e1_e2e.py:327`: `test_s1_as_committed_passes_the_real_pilot_gate` is a strict xfail ("S1 declares no NA for behavioural_equivalence and regression_count in expected.reference, so the real pilot gate refuses it (HB-CMP-008)").
- `tests/test_e1_e2e.py:248-256`: the walk's `declare_na` inserts the same two NA lines into a temp copy of S1 (`behavioural_equivalence: {na: "not a D-task"}`, `regression_count: {na: "task has no public tests"}`).
- `tasks/S1/oracle/evidence.md`: the sections "Leave-one-out table" (`:111`) and "F4 carrier (X-I4)" (`:152`).

## Owned paths
`tasks/S1/**`, `tests/test_security_tasks.py`, and in `tests/test_e1_e2e.py` only the `:327` strict-xfail marker (pre-granted by the plan). Not yours: every `src/` file, every other test file, `tests/mutations/*`, `bench/discrimination/**`. A line in another owner's file is a seam request: `python docs/ai-forward-pack/scripts/coord-core.py request add --to coord-opus-e1e4 --deadline default --fallback "<what you build meanwhile>" "<ask>"`. Build the fallback in its own commit that names the request id, and finish green (README section 2).

## Acceptance items
- **I5-1. The payload set.** `INJ_A`, `INJ_B` and `INJ_3` keep exactly A0, B2, B3 and C0 and drop the other nine. **A kept payload keeps its id:** m1 still measures `A0,B2,B3`, m12 `B2,B3`, m13 `B2`, m8 `C0`. Today's index-derived ids would rename B2 and B3 to B0 and B1 after a drop, so the id must travel with its payload, with one definition of the id in `check.py` (never a second table). Each variant's clause is re-measured through the real host, never copied (FIXT-A).
- **I5-2. Outcomes unchanged.** The reference still blocks 8 of 8 probes and the naive 3 of 8; the `expected` values and their provenance comments are unchanged except for I5-3's two new lines. Every variant flips exactly its own probes (`test_s1_each_defect_variant_flips_exactly_its_probes`).
- **I5-3. The NA declarations.** `expected.reference` declares `behavioural_equivalence` and `regression_count` as `{ na: "<reason>" }`. Each reason states why S1's cells never record that metric, read from the grader that would produce it (open it; never guessed). The walk's two texts are a reference, not evidence.
- **I5-4. A new task version.** `plan.task_version_hash(tasks/S1)` moves with the edit; there is no version field to bump. Add a section "F4 drop and NA (X-I5)" to `evidence.md`: the change, the operator decision it applies, the measured clause per variant, the old (`cafd0092`) and new task version hashes, the base and commit. Update the "Leave-one-out table" for the nine dropped payloads.
- **I5-5. The `:327` leg.** With the NA lines committed, `test_s1_as_committed_passes_the_real_pilot_gate` passes; remove its strict-xfail marker in the commit that makes it pass (a marker that turns XPASS fails the run). *assume:* the walk's `declare_na` still runs green once S1 already declares both lines. **Confirm:** the walk tests in `tests/test_e1_e2e.py` pass on your green commit. **If false:** `declare_na` is X-INT's code, not yours: raise a seam request to `coord-opus-e1e4` with the fallback "skip the insert when the committed `task.yaml` already declares both metrics", built in its own commit.
- **I5-6. `bench validate`.** `uv run bench validate` reports no EV-1 problem for S1.
- **I5-7. No flip, no record.** `status` stays `draft`. Do not run `bench discriminate S1` for a record and commit nothing under `bench/discrimination/**`: the Leader runs `uv run bench discriminate S1` (credentials removed) after your join and commits S1 `ready` with its record in one commit (serial spine 6).

## Red first (README section 2)
Commit a skeleton first: final test names, each red by a deliberately wrong expected value. Run the guard list on it. Then the red tests, each failing **on an assertion** (never `ImportError`, `KeyError` or `FileNotFoundError`; RED-C): a test that the check's payload ids are exactly `A0, B2, B3, C0`, and the NA declarations read through `readiness.expected_na`. A test that already passes on the base is recorded "green on arrival", never faked red. Then the green commit. For each red commit report the SHA, the node and the failing assertion line.

## Gate (R-104: own files and own mutations only; each command on its own line, exit status read, never behind a pipe)
1. `uv run pytest -q tests/test_architecture.py tests/test_identity.py tests/test_atomic_sites.py tests/test_arms_guard.py tests/test_discriminate.py tests/test_mutate_check.py tests/test_skills_in_sync.py tests/test_timing_hygiene.py` (the guard list, on the skeleton commit and on the final commit)
2. `uv run pytest -q tests/test_security_tasks.py tests/test_readiness.py tests/test_e1_e2e.py`
3. `uv run ruff check src tests tools`
4. `uv run bench validate`
5. `python docs/ai-forward-pack/scripts/docs-graph.py validate`

- **Own mutations:** no `tests/mutations/*.json` names `tasks/S1`, so run two hand mutants once each and report them; do not commit them. (m-a) Restore one dropped payload: the I5-1 id-set test fails. (m-b) Delete one NA line: the `:327` leg fails. After each, `git diff --exit-code tasks/S1` prints nothing. Never `mutate_check --touched`.
- `tasks/` is outside the ruff gate; do not lint or reformat task files (a reformat moves the task version for no reason).
- A skip because the upstream base cannot be reached is reported as not run, never as a pass. No campaign ledger (`bench/campaigns/**`) on your branch. The whole suite is the Leader's.

## Not in scope
- Re-deciding keep or drop; dropping or keeping any payload beyond the decision.
- Flipping S1 to `ready`, running the record, or committing a discrimination record.
- Any `src/` edit, any other test file's lines beyond the `:327` marker, `tests/mutations/*`.
- Merging or pushing. Killing any process by name or pattern (only PIDs you started).

## Budget
60 calls · 150k context · 1 session · 1 h (plan, Inferred). At 85 %: commit, stop, report what remains. Fallback: a fresh Sonnet session from this brief.

## Report (README section 4, at most 12 lines)
Served model id first · base SHA and branch tip · per red commit: SHA, node, failing assertion · each gate command's exit status · the measured clause per variant · the old and new task version hashes · the two NA reasons with the source each was read from · hand-mutant results · seam requests raised · every `assume:` and whether it held · budget used.
