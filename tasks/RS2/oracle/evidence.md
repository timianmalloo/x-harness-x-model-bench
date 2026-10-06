# RS2 oracle evidence

Status of RS2: `draft` (K1 design statement, K3 draft with the measurements below; ready waits for X-LB1's join).

Base: structlog at `91f44ae9031c80ad9c6045172f182803543ba6ba`, tree `f23e1352e410a6d67fab660e10a4e0c89fa53c16` (fresh clone, 2026-10-06).

## `g-ordering`: fault schedule (W1-L Erratum 1, R2-6)

Schedule, one probe host, one shipper, a check-owned collector fake on `127.0.0.1` (port 0):

1. `processor` buffers `r1`, then `r2`.
2. Flush 1 runs while the fault is on: **every request is answered 503 until the check clears the fault** (the reference sends
   exactly three, so this is "three 503s" for the reference; a client that sends a fourth also gets a 503). Expected: the flush
   raises `ShipError`, `requests <= 3`, `effects == 0`, within 3.5 s. Clause order: time, requests, effect.
3. The check clears the fault. `processor` buffers `r3`.
4. Flush 2 runs against the healthy collector. Expected: it returns 3, and the collector's applied records read `r1, r2, r3` in
   that order, each once. This is the `result` clause (the `then` call).

`g-5xx-persistent` uses the same fault but adds **no record** between the failed flush and the recovery flush, and its `result`
clause checks presence and once-only, not order. So only `g-ordering` sees a re-queued batch land behind a newer record.

## Re-trace of the seven variant rows against that schedule (hand-traced, Inferred until K3's first run)

| variant | cases it flips | clause | trace on `g-ordering` |
| --- | --- | --- | --- |
| `noretry` | `g-5xx-burst` | effect | flush 1: one 503, raises, effect 0, expected; recovery returns 3 in order: passes |
| `notimeout` | `g-slow-first`, `g-hang` | time | 503s answer at once; no wait: passes |
| `retry5` | `g-5xx-persistent`, `g-hang`, **`g-ordering`** | requests | **changed from rev 2**: flush 1 sends 5 requests, 503 each (the fault stays on), `requests <= 3` fails; the row in section 9.3 omitted `g-ordering` |
| `batchidattempt` | `g-slow-first`, `g-lost-response` | effect | 503 requests apply nothing, so a new id per attempt is harmless; recovery is one request: passes |
| `clearearly` | `g-5xx-persistent`, `g-ordering` | result | flush 1 empties the buffer before acceptance, so `r1, r2` are lost; the collector sees `r3` only |
| `requeuetail` | `g-ordering` | result | after flush 1 the buffer reads `r3, r1, r2`; the collector sees that order, not `r1, r2, r3`. `g-5xx-persistent` adds no newer record, so it reads `r1, r2` and passes |
| `retry4xx` | `g-4xx` | requests | 503s are not 4xx; the retry-on-every-status change does not alter flush 1: passes |

Each variant row's flip set is its full differing set. `g-ordering` is flipped on its own, among the order-only changes, by
`requeuetail` (the only variant whose `g-5xx-persistent` stays green and `g-ordering` goes red).

**Measured outcome:** see "Variant run" below; all seven rows match the re-trace above, including `retry5` flipping
`g-ordering` on `requests` and `requeuetail` flipping `g-ordering` alone, on `result`.

## Isolation

One fresh probe host per case (`bench_check.probe_host(case, sock)` in `run_probe`, closed in `finally`). The shipper lives in
the check's own frame handler `rs2_shim.py` inside that host, so no state crosses cases. A case with a `then` (`g-5xx-persistent`,
`g-ordering`) makes both flushes on the same host, because the second flush is the one that must see the kept records. The hidden
tests run in one process under `correctness.grade`; each builds its own `HttpShipper` and its own collector fake, so no state
crosses tests either.

## Shim

`HttpShipper` is a class, and a probe-host app is one callable, so `oracle/check/rs2_shim.py` is the app (`rs2_shim:handle`).
`cases.yaml` gives `paths: ["src"]` and the check appends its own folder to `ctx.app["paths"]` before each `probe_host(case, sock)`
(the host puts `root` and `root/<path>` on `sys.path`, and an absolute entry replaces the join). `handle("start", url)` builds the
shipper, `handle("add", names)` calls `processor` once per name, `handle("flush")` returns `flush()`; a raise reaches the check as
`{ok: false, error: <type>}`. Seeds `r1`, `r2` and the late record `r3` of `g-ordering` are constants in `check.py` (`SEED`,
`LATE`), so `cases.yaml` keeps RS1's field set.

## Hidden tests and A3 (W1-L assume A3, confirmed)

Real `correctness.grade`, Windows 11, Python 3.12, one run each. The sentinel stub: 0 of 5 pass, 5 red by assertion, no error
(`test_rs2_stub_fails_every_hidden_test`; the first run of that test found S-5 erroring on the stub with an `IndexError`, and the
test got a count assertion before the index; fixed before the table below). Reference, naive and alt: 5 of 5 pass. Each wrong app
turns exactly its declared test red and no other (`wa-nocopy` S-1, `wa-keep` S-2, `wa-ok4xx` S-3, `wa-sendempty` S-4, `wa-reverse`
S-5). Loopback sockets in the grading copy work, so A3 holds on this host and the hidden tests stay on `http.server`.

## Variant run (measured, stand-in listener, real probe host, Windows 11, Python 3.12)

Every variant passes all five hidden tests (real `correctness.grade`, `result.passed == 1`) and flips exactly the cases and clause
below; the measured set equals K1's re-trace in every row.

| Variant | Flipped (measured) | Clause (measured) | K1 re-trace | Match |
|---|---|---|---|---|
| noretry | g-5xx-burst | effect | g-5xx-burst, effect | yes |
| notimeout | g-slow-first, g-hang | time | same | yes |
| retry5 | g-5xx-persistent, g-hang, g-ordering | requests | same | yes |
| batchidattempt | g-slow-first, g-lost-response | effect | same | yes |
| clearearly | g-5xx-persistent, g-ordering | result | same | yes |
| requeuetail | g-ordering | result | g-ordering, result | yes |
| retry4xx | g-4xx | requests | same | yes |

Reference passes 7 of 7 and alt 7 of 7; naive passes 4 of 7 (g-5xx-persistent, g-lost-response, g-4xx, g-ordering) and fails
g-5xx-burst (effect), g-slow-first and g-hang (time, 5.2 s: the host's 5 s bound), so `fault_suite_pass` is "0.5714" as declared.
`idempotency_violations`: 0 for reference, naive, alt and every variant except `batchidattempt` (2: one duplicate effect in each of
its two flipped cases).

Reference `duration_ms` per case, slowest of three runs (each includes probe-host start): g-4xx 657, g-5xx-burst 783,
g-5xx-persistent 723, g-lost-response 678, g-ordering 736 (two flushes), g-slow-first 1631, g-hang 3125. Every `bound_ms: 4500` is
at least 25 percent above the slowest honest run (4500 against 1.25 x 3125 = 3906), and the quick cases sit far under the 5000 ms
interface bound, so no bound changes. These are three runs, not a distribution.

## Residual (stated, not tested)

A response lost in one flush, then a new record, then a second flush: the reference keeps the batch id and sends the grown batch,
so a collector that stored the first batch would drop the new record as a repeat. No case schedules it (`g-ordering` fails with a
503, which stores nothing). `simplify:` one kept id per pending batch; upgrade trigger: a case that loses a response across two flushes.
