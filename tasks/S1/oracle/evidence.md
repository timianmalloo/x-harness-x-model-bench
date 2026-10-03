# S1 oracle evidence

Status of S1: `stub`. It stays `stub` until (a) a run through X-F's real probe host reproduces the `expected` block of
`task.yaml` and the `leak-2` clause `app-output` (`test_s1_real_host_reproduces_the_expected_values`, skipped today because
`grade/bench_check.py` does not exist), and (b) X-E's discrimination record exists (RV-TA W1-I D1, D4). Every number
below was produced by the **stand-in** host (`tests/fixtures/s1/standin_bench_check.py`), not the real one.

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

## Assumptions about `bench_check` (W1-F rev 3 section 5.4 leaves these names open)

`assume:` the real helper exposes `Context.cases`, `.app`, `.evidence`, `.deliverable`; `ProbeHost.close()` and
`.state_dir`; `run_case(case, fn)` returns `{id, outcome, duration_ms}`; `probe_host` signals a failed start by raising, so
`main` can write `did not start`; `write_result(cases)` takes the list `run_case` returns; and a request frame may carry an `id`.
*Confirm:* `test_s1_real_host_reproduces_the_expected_values` when `grade/bench_check.py` lands. *Breaks if false:*
`check.py` raises `AttributeError` or `TypeError` (exit 5) and the real-host test fails; the fix is in `check.py`'s
adapter calls only (`Client.send`, `run_probe`, `check`, `leak_3`).

## Durations (stand-in, includes the host start)

The slowest case through the stand-in was 404 ms (reference) to 940 ms (m5), CPython 3.14.6 under the repo venv, with
`probe_host()` inside the timed span. The real host times the exchange without its start (W1-F 5.5), so this is not the
`bound_ms` trigger of W1-I 5.8 (a reference `duration_ms` above 400 ms, or `start_ms` above 500 ms). That trigger is read
from the real host's `hosts.jsonl` and `property.json` in the follow-on.

## Owed before `ready`

- The real-host run (above) and X-E's discrimination record.
- The leave-one-out table of W1-I 5.5 (per payload, the variant or partial fix that only it flips; drop a payload no
  variant needs alone). Not run: it needs the real host's per-payload evidence to be worth its cost.
- `wsgi.errors` has no variant (R-S4): microdot's handler cannot reach the WSGI environ as far as `request` shows
  (Inferred; `request.environ` was not tried).
