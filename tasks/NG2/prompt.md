Add `loads_env(text, source)` in `src/tomli/_interp.py` and export it from `tomli`.

- It parses `text` as TOML, the way `tomli.loads` does, and returns the result with `${NAME}` replaced in every string value, including strings inside arrays, inline tables and tables. `NAME` starts with a letter or underscore and continues with letters, digits and underscores.
- Each `${NAME}` becomes the value that `source` holds for `NAME`. `source` is an `envkit.MappingSource` from the `envkit` package in `vendor/envkit`.
- A name that `source` does not hold is an error: let the error that `source` raises reach the caller.
- Text that is not of the form `${NAME}`, such as `$HOME` or `{NAME}`, stays as it is. Values that are not strings are returned unchanged.

Add tests in `tests/test_interp.py`.
