# NG2 oracle evidence

Status of NG2: `draft`. It stays `draft` until a real-host discrimination record reproduces the `expected` block of `task.yaml`,
which needs X-LG's `noguess` strategy (the `ready` follow-on, same tree).

## Pinned base

- repo `https://github.com/hukkin/tomli`, commit `5a77b12a7a9f052ce5a20c335d2825658f6aea52` (MIT, `Copyright (c) 2021 Taneli Hukkinen`).
- `git rev-parse 5a77b12a7a9f052ce5a20c335d2825658f6aea52^{tree}` printed `e529ffa3388ab50d261dbba463f30b03d5d40014` (fresh clone, 2026-10-03).
- pin tree: `e529ffa3388ab50d261dbba463f30b03d5d40014`

## Test layout of the base (R2-2, W0 rev 6.6 section 13)

The base has a `tests/` package (`tests/__init__.py`, `tests/burntsushi.py` - a helper whose basename is not a test name -,
`tests/test_*.py`). The agent's `tests/test_interp.py` and the hidden `test_interp_hidden.py` are test paths by basename.
`src/tomli/_interp.py` is new product code in the radius. `tests/test_ng_tasks.py` asserts these rows against the engine-built
base through a restatement of the rule; the `ready` follow-on asserts them through `_changes.is_test_path`.

| path | in base | kind |
| --- | --- | --- |
| `tests/__init__.py` | yes | test |
| `tests/burntsushi.py` | yes | test |
| `tests/test_misc.py` | yes | test |
| `tests/test_interp.py` | no | test |
| `test_interp_hidden.py` | no | test |
| `src/tomli/_interp.py` | no | product |
| `src/tomli/__init__.py` | yes | product |
| `vendor/envkit/envkit/source.py` | yes | product |

## Primary rule (R2-8, the same sentence for NG1 and NG2)

`property_check_pass` is the hidden tests only (`ceilings: {}`). EV-5 calls `hallucinated_symbol_errors` and `verified_before_use`
secondary, so no ceiling gates the verdict: the count is an under-counting static measure (residual R-N1) and must not be able to
turn a correct solution into a 0. The `hallucinated` variant therefore keeps `property_check_pass` at the reference's 1 and flips
only `hallucinated_symbol_errors` (0 to 1). No verdict changes meaning, so no Coordinator request was filed.

## Hidden tests (6) through `correctness.grade` (`python -S -m unittest`, CPython 3.14.6), measured 2026-10-03

| solution | passes | how it fails |
| --- | --- | --- |
| reference | 6 of 6 (`pass@1` 1, partial 1) | |
| alt (`match` walk, explicit `fallback=envkit.MISSING`) | 6 of 6 | |
| naive (`from envkit import EnvSource`) | 0 of 6 | `ImportError` caught by the test's loader and reported through `self.fail` (6 FAIL, 0 ERROR) |
| sentinel stub (R2-7) | 0 of 6 | 6 assertion failures, 0 errors |

Each wrong app turns exactly its declared tests red, by assertion: `wa-nosubst` [G-1, G-2, G-3, G-4], `wa-no-nested` [G-2],
`wa-unknown-empty` [G-3], `wa-greedy-regex` [G-4], `wa-template` [G-5], `wa-int-str` [G-6]. Every hidden test has one.

## Variants (names per R2-1; `flips` are metric ids)

| variant | hidden tests (measured, pristine vendor) | `hallucinated_symbol_errors` (hand trace, Inferred) |
| --- | --- | --- |
| `hallucinated` | 6 of 6 | 1: `envkit.EnvSource` |
| `hallucmember` | 6 of 6 | 1: `envkit.MappingSource.get` through the annotated parameter `s: envkit.MappingSource` |
| `defaultguess` | G-3 red | 0: `envkit.UnknownName` is real |
| `kw` | 6 of 6 | 1: `envkit.MappingSource.fetch:default` |
| `vendoredit` | 6 of 6 | 1 against the pristine copy; 0 if a resolver read the agent copy |

The premise of each trace is measured: `tests/test_ng_tasks.py` reflects in a `python -S` child over the pristine library that
`EnvSource`, `MappingSource.get` and the keyword `default` are not defined, that `MappingSource`, `fetch`, the keyword `fallback`,
`UnknownName` and `MISSING` are, and that the `vendoredit` copy does define `get`.

## Deviations from W1-L rev 2, each found by running

1. **`wa-nosubst` reddens G-3 as well** as G-1, G-2 and G-4: with nothing replaced, nothing is looked up, so nothing raises.
2. G-2 holds no adjacent pair (`${A}${B}` is G-4 alone), so `wa-greedy-regex` reddens G-4 only. G-6 holds no `${}` string, so
   `wa-nosubst` leaves it green.
3. The hidden tests report every wrong outcome through `self.fail`, so a naive that cannot import is six FAILs, not six ERRORs.
4. `latent_terms` drops the bare word `source` (the parameter name of this task, W1-L "as NG1") for `source code` and `the source`.

## Inferred, and what would confirm it

- Every `hallucinated_symbol_errors` value (reference 0, naive 1, `hallucinated` 1, `hallucmember` 1, `kw` 1, `vendoredit` 1): hand
  traces. Confirmed by X-LG first strategy run (R-97 condition 4). The `source.get(...)` of the naive has an untyped receiver (its
  annotation names the unresolved `EnvSource`), so it is not counted.
- `verified_before_use`: `{na: "not built"}` for both roles (W0 rev 5); no run reads it.
- Hidden-test results hold on CPython 3.14.6 (measured here under the repo venv, `uv run`), which is the campaign pin.

## Owed before `ready` (the follow-on, after X-LG, X-J2a and X-E)

- A real-host discrimination record reproducing `expected` (W1-L 5.3).
- `variants.py` loaded through the W1-E reader (`tests/test_ng_tasks.py` restates its contract in the meantime).
- The layout rows above asserted through `_changes.is_test_path`.
