# RS2 oracle evidence

Status of RS2: `ready` (K5, part 7): eight cases on X-LB1's `bench_check.listen()` and the real `parse_result`, Ruling 111 case `g-lost-then-grow` and variant `growid` in; `bench discriminate RS2` reproduced the expected values (reference 1, naive 0), and the naive's two timeouts (g-slow-first, g-hang) are declared in `task.yaml` as `expected.naive.timeouts` (CR47-7).

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

## Variant run (measured on the real path, 8 cases, 8 variants; K5, part 6; Windows 11, Python 3.12)

The reference now holds one pending `(batch_id, records)` pair (Ruling 111 (i)): the pending batch first, then the records buffered since as a
new batch, one budget per flush, the sum of accepted counts on success. The prompt lost "in one batch" (ii). Every variant passes all five hidden
tests (real `correctness.grade`) and flips exactly the cases and clause below; `tests/test_rs2_task.py` asserts each row against `PREDICTED`.

| Variant | Flipped (measured) | Clause (measured) | Hand re-trace before the run | Match |
|---|---|---|---|---|
| noretry | g-5xx-burst | effect | g-5xx-burst, effect | yes |
| notimeout | g-slow-first, g-hang | time | same | yes |
| retry5 | g-5xx-persistent, g-hang, g-lost-then-grow, g-ordering | requests | traced as the old three plus g-lost-then-grow (requests: five fast resets) | yes |
| batchidattempt | g-slow-first, g-lost-response, g-lost-then-grow | effect | the old two plus g-lost-then-grow (effect) | yes |
| clearearly | g-5xx-persistent, g-lost-then-grow, g-ordering | result | the old two plus g-lost-then-grow (result) | yes |
| requeuetail | g-lost-then-grow, g-ordering | result | redefined for the freeze (newer records first, pending records after, a new id); traced g-ordering and g-lost-then-grow | yes |
| retry4xx | g-4xx | requests | same | yes |
| growid | g-lost-then-grow | result | g-lost-then-grow alone, result | yes |

The compile expected `batchidattempt` and `clearearly` to gain the new case; both did, and `retry5` and `requeuetail` also gained it (traced after the
compile). The variant edits were rewritten for the new reference text (their `old` anchors changed); the wrong-app anchors changed the same way
(`wa-keep`, `wa-sendempty`, `wa-reverse`), each still turning exactly its one hidden test red (finding: Ruling 111 (vi) says unchanged; only the anchor text moved).

Reference passes 8 of 8 and alt 8 of 8, `idempotency_violations` 0. Naive passes 4 of 8 (g-5xx-persistent, g-lost-response, g-4xx, g-ordering), so
`fault_suite_pass` is "0.5000" (asserted by the test). `idempotency_violations` is the count of deliveries (requests the collector applied) that applied at least one record already applied, summed over the case's requests (CR47-8; check.py :71 and :203). It replaces part 6's per-record count, which counted a duplicated batch of k records as k; g-ordering's two batches of distinct records count 0. Measured on the real path: reference 0, alt 0, naive 1 (red 3a818e7f: 2 under the per-record count), `batchidattempt` 5 (was 10), `requeuetail` 1, every other variant 0. Naive's value is read from the record, not here (EV-7).

Reference `duration_ms` per case, three runs on the real path (run 0/1/2; slowest in bold): g-5xx-burst 252/236/236, g-5xx-persistent 182/192/177, g-slow-first 1126/1129/1118, g-hang 3044/3036/**3051**, g-lost-response 142/143/151, g-4xx 136/145/131, g-lost-then-grow 179/180/**196**, g-ordering 183/199/196. `g-lost-then-grow` bound_ms is 1000 (196 ms x 1.25 = 245; the alt measured 304 ms). `g-slow-first` and `g-hang` keep 4500 (reference slowest 1129 and 3051; 4500 is 299 and 47 percent above them, both over the 25 percent floor). The other cases use the loopback default 5000.

## Check authoring rules (ADR-0018 section 3, B7)

1. Every socket comes from `bench_check.listen()`: `check.py:183` opens it, `:186` hands it to `bc.probe_host`; `serve` wraps that socket only (`server.socket = sock`, :141).
2. `passed` comes from the fake's counters: `Call.requests` and `Call.effects` are differences of `len(fake.requests)` and `fake.effects` (:84-:93); `clause_of` (:153-:180) judges on them and on `fake.names()`.
3. The serve thread is joined inside every case: `close()` (:145-:148) sets stop, calls `server.shutdown()` and `thread.join(5)`; `run_probe` calls it in `finally` (:202).
4. Untrusted bytes are bounded: handler `timeout = 10` (:106); the body is read only for an all-digit `Content-Length` of at most `MAX_BODY` 65536 (:110); otherwise `fake.malformed()` (:39) counts a request with no effect; a body that is not JSON is `{}` (a counted request, no effect), and nothing is evaluated beyond `json.loads`.

