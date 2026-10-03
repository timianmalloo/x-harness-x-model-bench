# SM1 oracle evidence

Status of SM1: `draft`. It stays `draft` until X-LG's `diffstats` measures `size_reference_lines` and the ceilings (B-SM1,
HASH-A), X-J2b's create edit form and `variants.py` reader joined, and a real-host discrimination record reproduces every
value in `expected` (W1-L 5.3). Every number below was produced by the **stand-in** counter
(`tests/fixtures/property_tasks/standin_diffstats.py`), through the real `correctness.grade` for the hidden tests.

## Pinned base

- repo `https://github.com/msiemens/tinydb`, commit `18d73a15066a04c77f19ae9a8c03d582bd344c0d` (MIT, `Copyright (C) 2013 Markus Siemens`).
- `git rev-parse 18d73a15066a04c77f19ae9a8c03d582bd344c0d^{tree}` printed `c388dbe522af1cf69a162b73c65cb18668c8adec` (fresh clone, 2026-10-03).
- pin tree: `c388dbe522af1cf69a162b73c65cb18668c8adec`
- The base used by every test is built by the engine, `workspace.task_source(tasks/SM1, ...)`, over the pinned upstream,
  with `tasks/SM1/workspace/.gitkeep` overlaid. `tasks/SM1/LICENSE` is the upstream MIT text.

## Test layout of the base (R2-2: W0 rev 6.6 `is_test_path(path, base_paths)`)

The base already has a top-level `tests/` directory, so a file in the base under it is a test path, and a **new** file under
`tests/` whose basename is not a test name is a product file (an agent's `tests/_helpers.py` counts as product code outside
the radius, against the allowance of 4). `tinydb/tests/` does not exist in the base, so `laundertest` adds product code
there. One row per path: `base` or `new` against the base tree, then the classification. Asserted by
`test_base_test_layout_is_recorded_and_classified_by_is_test_path`; the `ready` follow-on asserts it through the real
`is_test_path`.

- `tests/test_tables.py` base test
- `tests/conftest.py` base test
- `tests/__init__.py` base test
- `tests/test_first_extra.py` new test
- `tests/_helpers.py` new product
- `tinydb/table.py` base product
- `tinydb/_first.py` new product
- `tinydb/tests/_first.py` new product

## Measured by the stand-in counter (2026-10-03; CPython 3.14.6 under the repo venv)

Inferred until X-LG's `diffstats` reproduces them (B-SM1, HASH-A). "in" and "out" are added product lines inside and outside
`tinydb/table.py`; every row passes the 5 hidden tests through `correctness.grade`. `size_reference_lines: 2` is the reference's
"in" value (`test_frozen_reference_size_equals_function_output`).

| solution | in | out | size_vs_reference | new_abstractions | new_dependencies | clause | property_check_pass |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference | 2 | 0 | 1.0000 | 0 | 0 | | 1 |
| naive | 19 | 0 | 9.5000 | 3 | 0 | size | 0 |
| alt (6-line loop) | 6 | 0 | 3.0000 | 0 | 0 | | 1 |
| bloat | 7 | 0 | 3.5000 | 0 | 0 | size | 0 |
| class | 4 | 0 | 2.0000 | 1 | 0 | abstractions | 0 |
| dep | 4 | 0 | 2.0000 | 0 | 1 | dependencies | 0 |
| docstring | 2 | 0 | 1.0000 | 0 | 0 | | 1 |
| launderlines | 3 | 25 | 1.5000 | 0 | 0 | scope | 0 |
| launderclass | 2 | 2 | 1.0000 | 2 | 0 | abstractions | 0 |
| laundertest | 2 | 25 | 1.0000 | 0 | 0 | scope | 0 |

The design's "naive about 25 lines" is 19 here, and "v-laundered-class: one empty class" is two classes in two lines (W0 rev
6.6). Hidden tests: 5 of 5 pass on reference, naive and alt; the sentinel stub fails 5 of 5 (`failed`, none `errored`); each
wrong app (`wa-last`, `wa-raises`, `wa-empty-raises`, `wa-dict`) fails exactly its declared tests by assertion.

## Variants and `flips` (deviation to be ruled)

`flips` lists every metric id whose value differs from the reference's, as W1-E section 7 (3') defines it for a check-less
task, so `launderlines` lists `size_vs_reference` as well as `property_check_pass` (its three in-radius lines give 1.5000,
not 1.0000). The brief and W0 rev 6.6 write `flips: [property_check_pass]` for it. Raised to the Coordinator as a request.
