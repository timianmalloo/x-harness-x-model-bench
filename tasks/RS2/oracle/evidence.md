# RS2 oracle evidence

Status of RS2: `stub` (K1 design statement only; the draft follows in K3).

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

**Measured outcome:** not yet run (K3 records the measured flip sets here).
