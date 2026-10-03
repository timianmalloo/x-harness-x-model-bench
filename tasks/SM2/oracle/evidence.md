# SM2 oracle evidence

Status of SM2: `draft`. It stays `draft` until X-LG's `diffstats` measures `size_reference_lines` and the ceilings (B-SM2,
HASH-A), X-J2b's create edit form and `variants.py` reader joined, and a real-host discrimination record reproduces every
value in `expected` (W1-L 5.3). Every number below was produced by the **stand-in** counter
(`tests/fixtures/property_tasks/standin_diffstats.py`), through the real `correctness.grade` for the hidden tests.

## Pinned base

- repo `https://github.com/jmespath/jmespath.py`, commit `2812594e69d43098ef60f81f4efc404c071b0418` (MIT, `Copyright (c) 2013 Amazon.com, Inc. or its affiliates`).
- `git rev-parse 2812594e69d43098ef60f81f4efc404c071b0418^{tree}` printed `9c54fa72fc42fbef72011798bc3eba3610934541` (fresh clone, 2026-10-03).
- pin tree: `9c54fa72fc42fbef72011798bc3eba3610934541`
- The base used by every test is built by the engine, `workspace.task_source(tasks/SM2, ...)`, over the pinned upstream,
  with `tasks/SM2/workspace/.gitkeep` overlaid. `tasks/SM2/LICENSE` is the upstream MIT text.

## Test layout of the base (R2-2: W0 rev 6.6 `is_test_path(path, base_paths)`)

The base has a top-level `tests/` directory (so `laundertest` applies to SM2 too). A file already in the base under it is a
test path; a **new** file under `tests/` whose basename is not a test name is a product file. `jmespath/tests/` does not
exist in the base, so `laundertest` adds product code there. One row per path: `base` or `new` against the base tree, then
the classification. Asserted by `test_base_test_layout_is_recorded_and_classified_by_is_test_path`; the `ready` follow-on
asserts it through the real `is_test_path`.

- `tests/test_search.py` base test
- `tests/test_functions.py` base test
- `tests/__init__.py` base test
- `tests/test_search_many.py` new test
- `tests/_helpers.py` new product
- `jmespath/__init__.py` base product
- `jmespath/_batch.py` new product
- `jmespath/tests/_batch.py` new product

## Measured by the stand-in counter (2026-10-03; CPython 3.14.6 under the repo venv)

Inferred until X-LG's `diffstats` reproduces them (B-SM2, HASH-A). "in" and "out" are added product lines inside and outside
`jmespath/__init__.py`; every row passes the 5 hidden tests through `correctness.grade`. `size_reference_lines: 3` is the
reference's "in" value (`test_frozen_reference_size_equals_function_output`).

| solution | in | out | size_vs_reference | new_abstractions | new_dependencies | clause | property_check_pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference | 3 | 0 | 1.0000 | 0 | 0 | | 1 |
| naive | 25 | 0 | 8.3333 | 3 | 0 | size | 0 |
| alt (9-line loop) | 9 | 0 | 3.0000 | 0 | 0 | | 1 |
| bloat | 13 | 0 | 4.3333 | 0 | 0 | size | 0 |
| class | 5 | 0 | 1.6667 | 1 | 0 | abstractions | 0 |
| dep | 5 | 0 | 1.6667 | 0 | 1 | dependencies | 0 |
| docstring | 3 | 0 | 1.0000 | 0 | 0 | | 1 |
| launderlines | 4 | 25 | 1.3333 | 0 | 0 | scope | 0 |
| launderclass | 3 | 2 | 1.0000 | 2 | 0 | abstractions | 0 |
| laundertest | 3 | 25 | 1.0000 | 0 | 0 | scope | 0 |

Hidden tests: 5 of 5 pass on reference, naive and alt; the sentinel stub fails 5 of 5 (`failed`, none `errored`); each wrong
app (`wa-reversed`, `wa-none-empty`, `wa-noopts`, `wa-reparse`, `wa-lazy`) fails exactly its declared test by assertion.
`wa-reparse` is the red fixture for the recorder's target `jmespath.parser.Parser.parse` (W1-L assume A4): it makes four calls
where the reference makes one.

## Latent terms: a correction to the design

The design's `option` latent term hits SM2's own prompt (`options=None` is the API's parameter), so SM2 carries `"extra option"`
and `"new option"` instead; `test_prompt_has_no_latent_term` and `test_latent_scan_names_the_term_and_the_line` hold it.

## Variants and `flips` (deviation to be ruled)

As SM1: `flips` lists every metric id whose value differs from the reference's (W1-E section 7 (3')), so `launderlines`
includes `size_vs_reference` (1.3333). Raised to the Coordinator as a request.
