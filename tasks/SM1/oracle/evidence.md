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
