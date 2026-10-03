"""Limit how often a function may be called."""

import functools

from quotakit import RateLimiter, RateLimitExceeded


class LimitExceeded(Exception):
    """Raised by a limited function when a call would exceed its limit."""


def limit_calls(max_calls, per_seconds, clock=None):
    """Let the decorated function run at most ``max_calls`` times in any window of ``per_seconds``."""

    def decorator(func):
        limiter = RateLimiter(max_calls, per_seconds)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                limiter.acquire()
            except RateLimitExceeded as exc:
                raise LimitExceeded(str(exc)) from exc
            return func(*args, **kwargs)

        return wrapper

    return decorator
