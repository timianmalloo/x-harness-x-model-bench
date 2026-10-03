"""Limit how often a function may be called."""

import functools
import time

import quotakit


class LimitExceeded(Exception):
    """Raised by a limited function when a call would exceed its limit."""


def limit_calls(max_calls, per_seconds, clock=None):
    """Let the decorated function run at most ``max_calls`` times in any window of ``per_seconds``."""

    def decorator(func):
        gate = quotakit.Gate(max_calls, per_seconds, clock=clock or time.monotonic)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not gate.admit():
                raise LimitExceeded(f"{getattr(func, '__name__', 'call')}: more than {max_calls} calls in {per_seconds}s")
            return func(*args, **kwargs)

        return wrapper

    return decorator
