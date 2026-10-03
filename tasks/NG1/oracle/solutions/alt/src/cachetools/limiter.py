"""Limit how often a function may be called."""

import functools
import time

import quotakit

_GATES = {}


class LimitExceeded(Exception):
    """Raised by a limited function when a call would exceed its limit."""


def _gate_for(func, max_calls, per_seconds, clock):
    if func not in _GATES:
        _GATES[func] = quotakit.Gate(max_calls, per_seconds, clock=clock if clock is not None else time.monotonic)
    return _GATES[func]


def limit_calls(max_calls, per_seconds, clock=None):
    """Let the decorated function run at most ``max_calls`` times in any window of ``per_seconds``."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            gate = _gate_for(func, max_calls, per_seconds, clock)
            try:
                gate.require()
            except quotakit.QuotaExceeded as exc:
                raise LimitExceeded(str(exc)) from exc
            return func(*args, **kwargs)

        return wrapper

    return decorator
