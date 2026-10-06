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
- **Measured outcome of the first variant run:** not yet run (K2 records it here).
