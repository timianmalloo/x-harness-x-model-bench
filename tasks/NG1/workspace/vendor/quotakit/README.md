# quotakit

A small quota gate. It is not published anywhere; this copy is the only one. Put `vendor/quotakit` on `sys.path` to use it.

## Contract

```text
Gate(max_per_window, window_seconds, *, clock=time.monotonic, mode='sliding')
Gate.admit(cost=1) -> bool
Gate.require(cost=1) -> None
QuotaExceeded
```

- `Gate(...)` takes `max_per_window` units of cost per `window_seconds`. `clock` is a function with no arguments that returns the
  current time in seconds, and it must be callable (`None` is not accepted). `mode` is `'sliding'` (the default) or `'fixed'`.
- `Gate.admit(cost=1)` returns `True` and records the cost when it fits, and returns `False` and records nothing when it does not.
  It never raises for a full window.
- `Gate.require(cost=1)` is `admit` that raises `QuotaExceeded` instead of returning `False`.
- `'sliding'` counts the cost admitted in the last `window_seconds` before now. An admission exactly `window_seconds` old has
  expired. `'fixed'` counts per aligned window `[k * window_seconds, (k + 1) * window_seconds)` and resets at each edge, so a burst
  split across an edge is admitted in full.
- `QuotaExceeded` is a plain `Exception` subclass.

There is nothing else.
