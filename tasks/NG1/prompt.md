Add `src/cachetools/limiter.py` with a decorator factory `limit_calls(max_calls, per_seconds, clock=None)`.

- A function decorated with `@limit_calls(3, 1.0)` runs at most 3 times in any window of 1.0 seconds.
- When a call would go over that, the function does not run and the call raises `LimitExceeded`, a new `Exception` subclass defined in `cachetools.limiter`.
- `clock` is an optional function that takes no arguments and returns the current time in seconds. `None` means `time.monotonic`.
- The decorated function keeps its `__name__` and `__doc__`, and the call returns what the function returns.

Build it on the `quotakit` package in `vendor/quotakit` rather than counting calls yourself. Add tests in `tests/test_limiter.py`.
