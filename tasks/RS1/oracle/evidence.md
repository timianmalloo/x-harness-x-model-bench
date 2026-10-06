# RS1 oracle evidence

Status of RS1: `stub` (K1 design statement only; the draft follows in K2).

## Isolation of the hidden tests and the cases (W1-L Erratum 1, R2-5)

Two isolation levels, one statement each.

- **Cases: one fresh process per case.** `check.py` starts one probe host per case id (`bench_check.probe_host(case)` in
  `run_probe`, closed in `finally`). A module flag in the deliverable lives and dies with that host. A case with a `then`
  (`f-recover`) makes both calls on the same host, because the second call is the one that must see the flag.
- **Hidden tests: one shared pytest process, so the flag must be unreachable from them.** `correctness.grade` runs
  `H-1..H-6` in one process, in file order, and there is no per-test process. The `cacheerror` variant therefore sets its
  flag **only when a call ends because every attempt hit a transient failure**: the last attempt was an HTTP 5xx or a timeout.
  `H-3` (a 400, final, no retry) and `H-4` (connection refused: an OS error, neither a 5xx nor a timeout) never meet that
  condition. `H-1`, `H-2`, `H-5` and `H-6` succeed. So no hidden test can set the flag, and no hidden test can read a stale one.
- **Expected effect of `cacheerror`:** all six hidden tests pass; `f-recover` (call 1 against a hung service ends in timeouts,
  so the flag is set; call 2 after the fault clears raises the cached error) fails on clause `result`; every other case passes
  (`f-5xx-persistent` and `f-hang` also set the flag, but each is one call on its own host).
- **Measured outcome of the variant run (K2, part 4):** see "Variant run" below. `cacheerror` passed all six hidden tests and
  failed exactly `f-recover`, on clause `result`, as predicted.

## Naive `f-slow-first` finding (part 4)

The first naive run passed `f-slow-first` (15 ms, one request), against the design's prediction (fails on `time`). The design
was right; the check was wrong. `Fake.handle` incremented `self.seen` before `Fake.action` read it, so the schedule was read
one index late: `slow` and `lost` (first entry, `rest: ok`) were never applied, and `f-lost-response` and `f-slow-first`
passed for any client. Reference passed 7/7 that run by luck. Measured with a direct stand-in listener: a 2 s delay costs the
naive client 2.02 s, and a dropped connection raises `LedgerError` in 0.01 s, so the stand-in was sound. Fix: `n = self.seen - 1`.
After the fix naive passes `f-4xx`, `f-5xx-persistent`, `f-lost-response` (3 of 7), and fails `f-5xx-burst` (effect),
`f-hang`, `f-recover` and `f-slow-first` (time: 5156 ms against the 3500 ms limit, the host's 5 s bound).

## Variant run (measured, stand-in listener, real probe host, Windows 11, Python 3.12)

Every variant passes all six hidden tests (real `correctness.grade`) and flips exactly the predicted cases on the predicted clause.

| Variant | Flipped (measured) | Clause (measured) | K1 prediction | Match |
|---|---|---|---|---|
| noretry | f-5xx-burst | effect | f-5xx-burst, effect | yes |
| notimeout | f-slow-first, f-hang, f-recover | time | same | yes |
| attempt3s | f-hang, f-recover | time | same | yes |
| retry5 | f-5xx-persistent, f-hang, f-recover | requests | same | yes |
| nokey | f-lost-response, f-slow-first | effect | same | yes |
| retry4xx | f-4xx | requests | same | yes |
| cacheerror | f-recover | result | f-recover, result | yes |

`idempotency_violations`: 0 for every variant except `nokey` (2: one duplicate effect in each of its two flipped cases), and 0 for
reference, naive and alt.

Reference `duration_ms` per case (one run, includes probe-host start): f-4xx 516, f-5xx-burst 562, f-5xx-persistent 547,
f-lost-response 531, f-slow-first 1516, f-hang 2984, f-recover 3438 (two calls). The longest is under the 5000 ms loopback bound.
These are single-run values, not a distribution.
