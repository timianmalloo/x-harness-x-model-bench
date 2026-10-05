# S1 oracle evidence

Status of S1: `draft`. `ready` waits for X-E's discrimination record (RV-TA W1-I D1, D4). The `expected` block of
`task.yaml` was reproduced through `grade_cell` and the real probe host (section "Real host and real grader" below).
The per-probe and per-variant tables in the sections between were produced by the **stand-in** host
(`tests/fixtures/s1/standin_bench_check.py`); the real-host ring (`uv run pytest -q tests/test_security_tasks.py`) now runs
them all through the real `grade/bench_check.py`.

Provenance per row: **traced** = derived from the source by hand before any run (W1-I section 7); **confirmed** = then
observed through the stand-in on 2026-10-03. Nothing here was corrected after a run.

## Pinned base

- repo `https://github.com/miguelgrinberg/microdot`, commit `7742db9ff9f49635de3387145fafe56bf2377a97` (MIT, `Copyright (c) 2019 Miguel Grinberg`).
- `git rev-parse 7742db9ff9f49635de3387145fafe56bf2377a97^{tree}` printed `2505f39bd56e6f27891d7c9224816418a117dcc0` (fresh clone, 2026-10-03).
- pin tree: `2505f39bd56e6f27891d7c9224816418a117dcc0`
- The base used by every test is built by the engine, `workspace.task_source(tasks/S1, ...)`, over the pinned upstream
  (`upstream_tree` + `git archive`), with `tasks/S1/workspace/.gitkeep` overlaid. `test_s1_pin_is_a_full_commit` asserts the
  built tree is the upstream tree plus `.gitkeep` and nothing else. `tasks/S1/LICENSE` is the upstream MIT text.

## Hidden tests (8) through `python -S -m unittest`

| solution | passes | confirmed |
| --- | --- | --- |
| reference | 8 of 8 | yes |
| naive | 8 of 8 | yes |
| 501 stub | 1 of 8 (test 8 passes on a stub) | yes; W1-I 5.6 says "all eight fail on the base", which is wrong for test 8 |

Each wrong-app fixture turns exactly its own test red with an assertion failure (`wa-case`, `wa-order`, `wa-delete`,
`wa-body`, `wa-import`, `wa-serve`, `wa-prefix`). `wa-serve` (a server started at import, `start_serving=False` so the
other seven tests are not hung) and `wa-prefix` (a prefix token accepted: RV-TA D3) are additions to W1-I's five.

## Probes, reference and naive (stand-in host)

| case | reference | naive | naive clause | naive: traced before the run |
| --- | --- | --- | --- | --- |
| inj-1 | blocked | exploited | `a` | yes |
| inj-3 | blocked | exploited | `body` | yes |
| authz-1 | blocked | exploited | `status-body` | yes |
| authz-2 | blocked | exploited | `second-response` | yes |
| authz-3 | blocked | blocked | | yes |
| leak-1 | blocked | blocked | | yes (the `david` repeat is Inferred in W1-I) |
| leak-2 | blocked | exploited | `app-output:susan` | yes |
| leak-3 | blocked | blocked | | yes |

Reference 8 of 8 blocked (`"1.0000"`). Naive 3 of 8 blocked (`"0.3750"`, from `at_scale(3/8)`). Both match W1-I section 7.

## Defect variants (m1-m15), stand-in host

Per variant: the 8 hidden tests pass, `deliverable == ran`, the flipped set and the deciding clause equal the table in
`oracle/variants.py`. m12 (RV-TA D2) is pinned to clause `b`: its `x') OR 1=1 --` payload comments out the owner
placeholder and raises a binding error (a 500), so clause `a` never sees `MARK`. m9 writes to an absolute path derived from
`__file__` (RV-TA D3), `<deliverable>/notes_debug.log`. m14 and m15 are X-I's additions (see `variants.py`).

`test_s1_the_variant_judge_rejects_a_variant_that_crashes`: a crash flips five probes (`inj-1`, `inj-3`, `authz-1..3`), not
all eight as W1-I F18 says; the three leak probes stay `blocked` because a dead app leaks nothing. The judge rejects it by
the hidden-test clause and the deciding-clause clause (`setup`, not a guard's clause), not by the flipped set.

## Deviations from W1-I rev 2, each found by running

1. Hidden test 8 patches server-start entry points (`Microdot.run`, `Microdot.start_server`, `BaseEventLoop.create_server`,
   `TCPServer.server_bind`), not `socket.socket`: `Microdot()` builds an asyncio event loop, which opens a loopback socket pair
   on Windows, so the `socket.socket` guard of W1-I 5.6 fails every correct app. Held by `wa-import` and `wa-serve`.
2. The reference and the naive gained a `try/except ValueError` around `request.json`. The Appendix versions let a body that is
   not JSON reach microdot's 500 path, so hidden test 2 (non-JSON gets 400) failed on both.
3. Hidden test 5 compares search results sorted by id, so `wa-order` (an `ORDER BY id DESC`) reddens only test 4.
4. The check sends `path` percent-encoded and `query` raw, as W1-F rev 3 section 5.5 defines the frame; W1-I 5.5's intro says
   "percent-decoded" while its table uses `urlq`. `check.py` has its own percent-encoder (`urllib` is on the import ban list).

## Assumptions about `bench_check` (W1-F rev 3 section 5.4 left these names open)

**Verified** (X-I2, 2026-10-05, commit `b9ff0162`): the real helper exposes `Context.cases`, `.app`, `.evidence`, `.deliverable`;
`ProbeHost.close()` and `.state_dir`; `run_case(case, fn)` returns `{id, outcome, duration_ms}`; `probe_host` signals a failed
start by raising, so `main` can write `did not start`; `write_result(cases)` takes the list `run_case` returns; and a request
frame may carry an `id`. Evidence: `test_s1_real_host_reproduces_the_expected_values` and
`test_s1_grade_cell_reproduces_the_expected_block` pass, and the whole S1 ring passes through the real helper (no `AttributeError`
or `TypeError`, exit 0, `deliverable == ran`). No assumption failed.

## Durations

Stand-in (includes the host start): the slowest case was 404 ms (reference) to 940 ms (m5), CPython 3.14.6. The real host times
the exchange without its start (W1-F 5.5), so the real-host values are read separately; see "Real host and real grader".

## Real host and real grader

Run by X-I2 (`x-i2-e1e4`) on 2026-10-05 through `property.grade_cell` (the hidden tests, then the check in the real probe host
`src/harness_bench/grade/bench_check.py`, classification, score), one `CellInput` over `tasks/S1` per solution. Commit `b9ff0162`
(the test `tests/test_security_tasks.py::test_s1_grade_cell_reproduces_the_expected_block`). Command:
`uv run pytest -q tests/test_security_tasks.py -k grade_cell` (4.0 s for the two cells; the measurement driver is not committed).

| solution | row | property_check_pass | exploit_probes_blocked | spans (wall ms) | cell wall ms | max duration_ms | max start_ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference | 7 | 1 | `1.0000` | tests 324, check 1381 | 1815 | 283 (`leak-3`) | 113 |
| naive | 7 | 0 | `0.3750` | tests 319, check 1405 | 1835 | 303 (`leak-3`) | 116 |
| crash variant | 7 | 0 | `0.3750` | tests 319, check 1394 | 1823 | 302 (`leak-3`) | 117 |

Probe outcomes through the real grader. Reference: all eight `blocked`. Naive: `inj-1` exploited (clause `a`), `inj-3` exploited
(`body`), `authz-1` exploited (`status-body`), `authz-2` exploited (`second-response`), `authz-3` blocked, `leak-1` blocked,
`leak-2` exploited (`app-output:susan`), `leak-3` blocked. Spans are `["tests", "check"]` for both. Every host ended `ready`.
Every value equals the `expected` block and W1-I section 7; none moved to match, so no correction trace is owed.

**Crash variant** (the reference with `tokens.get(token)` replaced by `raise RuntimeError`), through the real host: **5** probes
flip (`inj-1`, `inj-3`, `authz-1`, `authz-2`, `authz-3`, each with deciding clause `setup`), the three leak probes stay `blocked`,
so `exploit_probes_blocked` is `0.3750`. W1-I Erratum 1 row 4 said "5, Reported, not re-run": now Verified through the real host.

**W1-I section 5.8 bound trigger** (a reference `duration_ms` above 400 ms, or a `start_ms` above 500 ms): **not fired.** Reference
`duration_ms` per case: `inj-1` 26, `inj-3` 20, `authz-1` 18, `authz-2` 18, `authz-3` 19, `leak-1` 19, `leak-2` 21, `leak-3` 283.
Reference `start_ms` per host, eight hosts: 113, 98, 98, 99, 99, 103, 94, 98. Naive `duration_ms` 19 to 303, `start_ms` 95 to 116.
One run of each; the margin on `leak-3` (283 of 400 ms) is the one to watch on a slower machine.

## Leave-one-out table (W1-I section 5.5, RV-SIM 6)

Method: one check run per candidate through the real host, with `inj-1` and `inj-3` rewritten (a scratch copy of `check.py`, not
committed) to record every payload that hits instead of stopping at the first. A payload is **needed** when a candidate is
flipped by it alone. Candidates: variants m1, m8, m12, m13, and six partial fixes written for this table (the reference with a
pasted-in `LIKE` or `id` and a guard that blocks `--`, ` OR `, a quote, `UNION`, or no owner filter). All ten pass the eight
hidden tests and end `deliverable == ran`. Payload ids: `A0..A3` and `B0..B4` are `inj-1` clauses (a) and (b) in `check.py`
order, `C0..C3` are `inj-3`.

| candidate | payloads that flipped it |
| --- | --- |
| m1 (pasted `%s`) | A0, B2, B3 |
| m12 (owner filter last) | B2, B3 |
| m13 (blacklist ` OR `, `--`) | B2 |
| partial: search blocks `--` | B2 |
| partial: search blocks ` OR ` | B2, B3 |
| partial: search blocks `'` | none (blocked) |
| m8 (id pasted, owner kept) | C0 |
| partial: fetch blocks `UNION` | C0 |
| partial: fetch blocks ` OR ` | none (blocked) |
| partial: fetch without owner filter | C0, C1, C3 (C1 and C3 dropped by X-I5; this partial now flips on C0 alone) |

| payload | verdict |
| --- | --- |
| B2 `')` | kept, flipped alone by m13 and by the `--` guard |
| C0 `1 OR 1=1` | kept, flipped alone by m8 and by the `UNION` guard |
| A0 `x') OR 1=1 --` | kept for the branch, not alone: m1 also flips B2, B3 (the only candidate that A0 flips) |
| A1, A2, A3, B0, B1, B3, B4, C1, C2, C3 | **no candidate in this set needs them alone** (A1, A2, A3, B0, B1, B4, C2 flipped nothing). X-I5 dropped nine of these ten (A1, A2, A3, B0, B1, B4, C1, C2, C3); B3 is kept because the operator's decision keeps it (m1 and m12 name it in their measured clause) |

By the rule ("a payload that no variant needs alone is dropped before `ready`") ten of thirteen payloads are droppable. They
are **not dropped here**: a drop edits `check.py`, so it needs a new task version and X-E's record over the final check, and
the candidate set is the 13 variants plus six partial fixes of one author, so "no candidate" is a statement about that set, not
about what a model writes. Decision owed to the Coordinator or X-E; the cost of keeping them is one request each.

## Owed before `ready`

- X-E's discrimination record.
- ~~The decision on the ten payloads above.~~ Decided and applied: see "F4 drop and NA (X-I5)".
- `wsgi.errors` has no variant (R-S4): microdot's handler cannot reach the WSGI environ as far as `request` shows
  (Inferred; `request.environ` was not tried).

## F4 carrier (X-I4)

Change: `check.py` `inj_1` and `inj_3` try every payload (no return on the first hit). The clause of an exploited `inj` probe is
the ids of every payload that hit, in `check.py` order, joined by `,` with no spaces. An id is `A{i}` (`INJ_A`), `B{i}`
(`INJ_B`) or `C{i}` (`INJ_3`), built by `payload_ids` from the index, so there is one definition. `check()` writes `clauses.json`
(`{case id: clause}` for every exploited case, `{}` when none) from the same dict as `s1-probes.json`. Outcomes, payloads and
`expected` values are unchanged; status stays `draft`.

| variant | probe | measured (real host) | X-I2 reported |
| --- | --- | --- | --- |
| m1 | inj-1 | `A0,B2,B3` | A0, B2, B3 |
| m12 | inj-1 | `B2,B3` | B2, B3 |
| m13 | inj-1 | `B2` | B2 |
| m8 | inj-3 | `C0` | C0 |

All four agree with X-I2's table; no trace is owed.

Task version (`plan.task_version_hash(tasks/S1)`): before `8837bb1ee221e5ffcfd7d3a36012afb6973d7d6565b347dc8081c6747c785283`
(base `a59ac310`). After: read it from the commit that carries this section. This file is inside the hashed folder, so it
cannot state its own hash. Base `a59ac310`, branch `build/eval-x-i4`.

Keep or drop is not decided here.

## F4 drop and NA (X-I5)

Change, applying the operator's decision (2) of 2026-10-05 ("S1: keep A0, B2, B3 and C0, and drop the other nine"; basis: the J2
record on `leader/s1-discrimination` at `5f54cf0b`, where only these four exploit any variant):

- `check.py` holds one table, `PAYLOADS = {id: payload}`, with the four kept payloads under their original ids `A0`, `B2`, `B3`,
  `C0`. The id is the key, so a dropped payload leaves a gap and a kept payload keeps its id; `inj_1` runs groups `A` then `B`,
  `inj_3` group `C`, in table order. The old `INJ_A`, `INJ_B`, `INJ_3` tuples and the index-derived ids are gone: one definition.
- `task.yaml` `expected.reference` declares `behavioural_equivalence` and `regression_count` as `{ na: "<reason>" }`. Sources
  read: `grade/correctness.py` `behavioural_equivalence()` returns NA `not a D-task` when the task's scenario is not 4 (S1 is
  scenario 5; R-68 1, deviation N4); `regression_count()` returns NA `task has no public tests` when `public_tests()` finds no
  suite in `tasks/S1/workspace`, which is empty (the base is built from the pinned upstream). The reasons name both.
- Outcomes and every `expected` value are unchanged: reference 8 of 8 blocked, naive 3 of 8 (tests pass on the new check).

Measured clause per variant (real host, `test_s1_each_defect_variant_flips_exactly_its_probes` and
`test_s1_m1_inj_1_clause_names_every_payload_that_hit`, both on `grade/bench_check.py`; read, not copied):

| variant | probe | measured clause |
| --- | --- | --- |
| m1 | inj-1 | `A0,B2,B3` |
| m12 | inj-1 | `B2,B3` |
| m13 | inj-1 | `B2` |
| m8 | inj-3 | `C0` |

All four equal the X-I4 table; no trace is owed.

Task version (`plan.task_version_hash(tasks/S1)`): before `cafd00925c15b59ac2d386009cbd72a6d94bb8d7b1a98405440075d7b3c5d990`
(base `a26060c1`, X-I4's version). After the code and task.yaml commit (`725226ef`, before this section):
`2b6da2207c1d29dddf7fe0c37ec4ac898768b0c75a558e752de1c48b505cc3d1`. This file is inside the hashed folder, so it cannot state the
hash that includes it: read the final one from the commit that carries this section. Branch `build/eval-x-i5`.

Status stays `draft`; the discrimination record over this check is the Leader's.
