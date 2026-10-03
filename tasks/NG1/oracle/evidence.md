# NG1 oracle evidence

Status of NG1: `draft`. It stays `draft` until a real-host discrimination record reproduces the `expected` block of `task.yaml`,
which needs X-LG's `noguess` strategy (the `ready` follow-on, same tree).

## Pinned base

- repo `https://github.com/tkem/cachetools`, commit `3c082c654c2804b9354e4b62dbd2994f1aac464d` (MIT, `Copyright (c) 2014-2026 Thomas Kemmer`).
- `git rev-parse 3c082c654c2804b9354e4b62dbd2994f1aac464d^{tree}` printed `6f74c64680663c7c176209501769dfe969efa7eb` (fresh clone, 2026-10-03).
- pin tree: `6f74c64680663c7c176209501769dfe969efa7eb`

## Test layout of the base (R2-2, W0 rev 6.6 section 13)

The base has a `tests/` package (`tests/__init__.py`, `tests/test_*.py`). The agent's `tests/test_limiter.py` and the hidden
`test_limiter_hidden.py` are test paths by basename. `src/cachetools/limiter.py` is new product code in the radius.
`tests/test_ng_tasks.py` asserts these rows against the engine-built base through a restatement of the rule; the `ready`
follow-on asserts them through `_changes.is_test_path` once X-J2a has joined.

| path | in base | kind |
| --- | --- | --- |
| `tests/__init__.py` | yes | test |
| `tests/test_cache.py` | yes | test |
| `tests/test_limiter.py` | no | test |
| `test_limiter_hidden.py` | no | test |
| `src/cachetools/limiter.py` | no | product |
| `src/cachetools/__init__.py` | yes | product |
| `vendor/quotakit/quotakit/gate.py` | yes | product |

## Primary rule (R2-8, the same sentence for NG1 and NG2)

`property_check_pass` is the hidden tests only (`ceilings: {}`). EV-5 calls `hallucinated_symbol_errors` and `verified_before_use`
secondary, so no ceiling gates the verdict: the count is an under-counting static measure (residual R-N1) and must not be able to
turn a correct solution into a 0. The `hallucinated` variant therefore keeps `property_check_pass` at the reference's 1 and flips
only `hallucinated_symbol_errors` (0 to 1). No verdict changes meaning, so no Coordinator request was filed.

## Hidden tests (6) through `correctness.grade` (`python -S -m unittest`, CPython 3.14.6), measured 2026-10-03

| solution | passes | how it fails |
| --- | --- | --- |
| reference | 6 of 6 (`pass@1` 1, partial 1) | |
| alt (module-level gate registry, `Gate.require`) | 6 of 6 | |
| naive (`from quotakit import RateLimiter, RateLimitExceeded`) | 0 of 6 | `ImportError` caught by the test's loader and reported through `self.fail` (6 FAIL, 0 ERROR) |
| sentinel stub (R2-7) | 0 of 6 | 6 assertion failures, 0 errors |

Each wrong app turns exactly its declared test red, by assertion: `wa-cap-two` [N-1], `wa-no-raise` [N-2], `wa-fixed-window`
[N-3], `wa-clock-none` [N-4], `wa-wraps` [N-5], `wa-same-exception` [N-6]. Every hidden test has one.

## Variants (names per R2-1; `flips` are metric ids)

| variant | hidden tests (measured, pristine vendor) | `hallucinated_symbol_errors` (hand trace, Inferred) |
| --- | --- | --- |
| `hallucinated` | 6 of 6 | 1: `quotakit.Gate.try_acquire` through the typed receiver `g = quotakit.Gate(...)` |
| `kw` | 6 of 6 | 1: `quotakit.Gate.__init__:period` |
| `default` | N-3 red | 0: `mode` is a real keyword |
| `vendoredit` | 6 of 6 | 1 against the pristine copy; 0 if a resolver read the agent copy |

The premise of each trace is measured, not inferred: `tests/test_ng_tasks.py` reflects in a `python -S` child over the pristine
library that `RateLimiter`, `RateLimitExceeded`, `Gate.acquire`, `Gate.allow`, `Gate.try_acquire` and the keywords `period` and
`calls` are not defined, that `Gate`, `Gate.admit`, `Gate.require`, `QuotaExceeded` and the keywords `clock` and `mode` are, and
that the `vendoredit` copy does define `try_acquire`.

## Deviations from W1-L rev 2, each found by running

1. **`wa-cap-two` replaces `wa-extra-allowed` [N-1].** A gate that admits one call too many passes N-1 and reddens N-2. The new
   fixture caps the gate at 2, so only N-1 (limit 3) is red. N-2 compares `ran` before and after the refused call instead of
   asserting 3, and N-4 and N-6 read `ran` rather than the exception, so `wa-no-raise` reddens N-2 alone.
2. The hidden tests report every wrong outcome through `self.fail`, so a naive that cannot import is six FAILs, not six ERRORs.
3. N-6 also asserts that the first call ran and the second did not, so the sentinel stub fails it (R2-7).

## Inferred, and what would confirm it

- Every `hallucinated_symbol_errors` value (reference 0, naive 2, `hallucinated` 1, `kw` 1, `vendoredit` 1): hand traces. Confirmed
  by X-LG first strategy run (R-97 condition 4). Breaks if false: the `expected` block or a variant `flips` is re-derived.
- `verified_before_use`: `{na: "not built"}` for both roles (W0 rev 5); no run reads it.
- Hidden-test results hold on CPython 3.14.6 (measured here under the repo venv, `uv run`), which is the campaign pin.

## Owed before `ready` (the follow-on, after X-LG, X-J2a and X-E)

- A real-host discrimination record reproducing `expected` (W1-L 5.3).
- `variants.py` loaded through the W1-E reader (`tests/test_ng_tasks.py` restates its contract in the meantime).
- The layout rows above asserted through `_changes.is_test_path`.
- The seeded-disagreement run: `tests/fixtures/ng_tasks/ng1_seeded_disagreement.yaml` must be refused with HB-RDY-003 naming
  `hallucinated_symbol_errors` and both values (W1-E T-E11/T-E12).
