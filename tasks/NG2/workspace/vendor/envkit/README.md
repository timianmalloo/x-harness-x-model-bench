# envkit

Named values for configuration. It is not published anywhere; this copy is the only one. Put `vendor/envkit` on `sys.path` to use it.

## Contract

```text
MappingSource(mapping)
MappingSource.fetch(name, *, fallback=MISSING)
UnknownName
MISSING
```

- `MappingSource(mapping)` holds a copy of `mapping` (names to string values).
- `MappingSource.fetch(name, *, fallback=MISSING)` returns the value of `name`. For a name the source does not hold it raises
  `UnknownName`, unless `fallback` is given, in which case it returns `fallback` (any object, including `None` and `''`).
  `fallback` can only be passed by keyword.
- `UnknownName` is a plain `Exception` subclass. `MISSING` is the marker that means "no fallback given".

There is nothing else.
