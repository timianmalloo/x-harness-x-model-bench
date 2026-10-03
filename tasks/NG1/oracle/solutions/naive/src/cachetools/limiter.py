"""Skeleton: a limiter that does nothing useful (K5). Replaced by the real solution."""

SENTINEL = object()


class LimitExceeded(Exception):
    """Skeleton."""


def limit_calls(max_calls, per_seconds, clock=None):
    def decorator(func):
        def stub(*args, **kwargs):
            return SENTINEL

        return stub

    return decorator
