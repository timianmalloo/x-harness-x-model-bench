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
