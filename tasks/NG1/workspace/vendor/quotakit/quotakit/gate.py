"""Gate: admit or refuse units of work against a quota."""

import math
import time
from collections import deque


class QuotaExceeded(Exception):
    """Raised by Gate.require() when the quota has no room for the cost."""


class Gate:
    """Allow at most ``max_per_window`` units of cost in any ``window_seconds``.

    mode "sliding" (the default) counts the cost admitted since ``now - window_seconds``
    (an admission exactly ``window_seconds`` old has expired). mode "fixed" counts per
    aligned window [k * window_seconds, (k + 1) * window_seconds) and resets at its edge.
    """

    def __init__(self, max_per_window, window_seconds, *, clock=time.monotonic, mode="sliding"):
        if mode not in ("sliding", "fixed"):
            raise ValueError(f"unknown mode {mode!r}")
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds
        self.mode = mode
        self._clock = clock
        self._events = deque()
        self._slot = None
        self._used = 0

    def _in_window(self, now):
        if self.mode == "fixed":
            slot = math.floor(now / self.window_seconds)
            if slot != self._slot:
                self._slot, self._used = slot, 0
            return self._used
        while self._events and self._events[0][0] <= now - self.window_seconds:
            self._used -= self._events.popleft()[1]
        return self._used

    def admit(self, cost=1):
        """Record ``cost`` and return True if it fits in the window; otherwise record nothing and return False."""
        now = self._clock()
        if self._in_window(now) + cost > self.max_per_window:
            return False
        self._used += cost
        if self.mode == "sliding":
            self._events.append((now, cost))
        return True

    def require(self, cost=1):
        """Like admit(), but raise QuotaExceeded instead of returning False."""
        if not self.admit(cost):
            raise QuotaExceeded(f"{cost} does not fit in {self.max_per_window} per {self.window_seconds}s")
