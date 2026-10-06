---
id: plan-eval-x-rs
title: "X-RS: the two resilience property tasks, RS1 and RS2"
type: doc
status: proposed
owner: "@timianmalloo"
summary: "RS1 (prometheus_client) and RS2 (structlog) ready, with discrimination records, declared naive timeouts, the RS2 delivery-count measure and the variant tables measured on the real path."
tags: [evaluation, property, execution-plan]
links:
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-20"
---

# X-RS execution plan (K2-K5)

Goal: RS1 and RS2 are `ready`, each with a committed discrimination record. Done when each record reproduces
`expected` (reference 1, naive 0) through the engine and readiness accepts it with no HB-RDY-003, HB-RDY-010 or
HB-RDY-011 item. Not in scope: `src/`, `bench_check.py`, `grade/property.py`, the design docs, ADR-0018, other tasks.
Tier T2; fan-out cap zero. Parts 4, 5, 6 and 7 of the session `x-rs-e1e4`; parts 5 and 6 stopped before this record.

Closing audit entries: part 4 `al-01M492A0RG3PRGBX7DR29E73VD`, part 5 `al-01M493KYHFD935SBA0KNPMRCY9`,
part 6 `al-01M499BDK9D1CHZJ179JX8WTV9`, part 7 (this part) in the audit log under `x-rs-e1e4`.

## Per-task result

| Task | State | Record | Declared = measured |
|---|---|---|---|
| RS1 | ready (`b466281c`) | `bench/discrimination/RS1/4abce7b6c4b932d6-b7d0b01779496991-win32.json` | reference: property_check_pass 1, fault_suite_pass 1.0000, idempotency_violations 0; naive: 0, 0.4286, 0, timeouts f-hang, f-recover, f-slow-first |
| RS2 | ready (`eed3bed1`) | `bench/discrimination/RS2/ce78c3a1eb92fd5e-af46dc82a3f6bf4f-win32.json` | reference: 1, 1.0000, 0; naive: 0, 0.5000, 1, timeouts g-slow-first, g-hang |

Both trials ran `uv run bench discriminate <ID> --runs C:\t\rs-runs --cells-root C:\t\rs-cells`, exit 0, `readiness_failures` empty.
RS1's second trial (credentials unset) printed `confirmed`: byte-equal to the first record.

## The RS2 measure (CR47-8)

`idempotency_violations` counts deliveries: one request the collector applied that applied at least one record already
applied counts 1, summed over the case's requests (`check.py:71`, `:203`). Red `3a818e7f` (naive 2 under the old per-record
count), green `651f87a0`. RS1 keeps its per-call sum of `max(0, effects - 1)` (`tasks/RS1/oracle/check/check.py:177`); for a
client that sends one request per logical call it is the same quantity. Measured: reference 0, alt 0, naive 1,
`batchidattempt` 5 (was 10), `requeuetail` 1, other variants 0.

## Declared naive timeouts (CR47-7)

The naive's `urlopen` has no timeout by design. Observed on the real path (the trial and `tests/test_*_task.py`, outcome
`timeout`, clause `time`): RS1 f-hang, f-recover, f-slow-first; RS2 g-slow-first, g-hang. Each is declared in `task.yaml` as
`expected.naive.timeouts` with a provenance comment; none on the reference.

## Variant tables, measured on the real path through the engine

RS1 (the engine record's `flips`, equal to `tests/test_rs1_task.py`'s measured rows):

| Variant | Flipped cases | idempotency_violations |
|---|---|---|
| noretry | f-5xx-burst (effect) | 0 |
| notimeout | f-slow-first, f-hang, f-recover (time) | 0 |
| attempt3s | f-hang, f-recover (time) | 0 |
| retry5 | f-5xx-persistent, f-hang, f-recover (requests) | 0 |
| nokey | f-slow-first, f-lost-response (effect) | 2 |
| retry4xx | f-4xx (requests) | 0 |
| cacheerror | f-recover (result) | 0 |

RS2 (the engine record; the cell is the clause that decides):

| Variant | Flipped cases | idempotency_violations |
|---|---|---|
| noretry | g-5xx-burst (effect) | 0 |
| notimeout | g-slow-first, g-hang (time) | 0 |
| retry5 | g-5xx-persistent, g-hang, g-lost-then-grow, g-ordering (requests) | 0 |
| batchidattempt | g-slow-first, g-lost-response, g-lost-then-grow (effect) | 5 |
| clearearly | g-5xx-persistent, g-lost-then-grow, g-ordering (result) | 0 |
| requeuetail | g-lost-then-grow, g-ordering (result) | 1 |
| retry4xx | g-4xx (requests) | 0 |
| growid | g-lost-then-grow (result) | 0 |

Every case of both tasks is flipped by at least one variant.

## Reference duration_ms per case (three runs, the real check)

| Task | Case: run 0 / 1 / 2 (ms) |
|---|---|
| RS1 | f-5xx-burst 57/56/61, f-5xx-persistent 52/37/56, f-slow-first 1012/1011/1017, f-hang 2924/2918/2923, f-lost-response 43/13/40, f-4xx 12/36/14, f-recover 2946/2945/2945 |
| RS2 | g-5xx-burst 252/236/236, g-5xx-persistent 182/192/177, g-slow-first 1126/1129/1118, g-hang 3044/3036/3051, g-lost-response 142/143/151, g-4xx 136/145/131, g-lost-then-grow 179/180/196, g-ordering 183/199/196 |

Bounds: RS2 `g-lost-then-grow` `bound_ms` 1000 (slowest 196 ms x 1.25 = 245; the alt measured 304 ms). The `bound_ms: 4500` of
the slow and hang cases (RS1 f-slow-first, f-hang, f-recover; RS2 g-slow-first, g-hang) are at least 47 percent above the
reference's slowest run (RS1 f-recover 2946, RS2 g-hang 3051), so none changed (W1-L 9.1 upgrade trigger).

## Check authoring rules and the lines that meet them

| Rule | RS1 `check.py` | RS2 `check.py` |
|---|---|---|
| 1. every socket from `bench_check.listen()` | :162, :165 | :183, :186 |
| 2. `passed` from the fake's counters | :71, :78, :136-:154 | :84-:93, :153-:180 |
| 3. serve thread joined inside the case | :128-:131, :176 | :145-:148, :202 |
| 4. untrusted bytes bounded, malformed counted with no effect | :89, :93, :32 | :106, :110, :39 |

Each task's `oracle/evidence.md` states the four rules in full.

## CR47-9: anchors and variants moved by the reference freeze (Ruling 111)

S-1..S-5 (`tasks/RS2/tests/test_shipper_hidden.py`) are byte-identical to `cb7ba428` (`git diff --exit-code cb7ba428 --` the
file, exit 0; the same for `tasks/RS1/tests`). The frozen reference moved the text three wrong-apps edit, so their `old`
anchor changed (commit `3bad8cda`, from `c44c11e5`); each still turns exactly its one hidden test red
(`test_each_wrong_app_turns_exactly_its_reds_red` passed in the final gate).

| Wrong app | Old anchor | New anchor |
|---|---|---|
| wa-keep | `del self._buffer[:len(records)]` line | `self._pending = None` then `return sent` |
| wa-sendempty | `if not self._buffer:` then `return 0` | `if not self._buffer:` then `break` in the flush loop |
| wa-reverse | `records = list(self._buffer)` | `self._pending = (uuid.uuid4().hex, self._buffer[:])` |

`requeuetail` was redefined for the freeze: it no longer adds a `_held` list; it puts the newer records first and the
pending records after, under a new batch id, so it flips g-lost-then-grow and g-ordering (was g-ordering alone).

## Finding and validation (not fixed here)

- Working-copy line endings. Eight RS1 and RS2 files were CRLF in the working tree although the index holds LF. The
  engine's `_variant_overlay` (`discriminate.py:142`) applies `bytes.replace` with an LF `old`, so six RS2 variants
  silently changed nothing and read as HB-RDY-003 in the first trial. The files were rewritten as LF (no git diff, and
  `tree_hash` reads CRLF as LF, so no record key moves); the trial was re-run and the first record deleted before commit.
  `_variant_overlay` should fail when `old` is absent from the bytes. This is for `src/`, so it is a seam request.
- `uv run bench validate` on the final tree prints one line, `ok: bom, metrics, example matrix and every task folder are valid`: no line names RS1 or RS2, and no HB-RDY-002 appears.
