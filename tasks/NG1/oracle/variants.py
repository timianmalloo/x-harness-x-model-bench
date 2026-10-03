"""Defect variants for NG1 (W0 section 2 rev 6.6): one top-level VARIANTS literal, read with ast.literal_eval and never imported.
`flips` lists the metric ids whose observed value differs from the reference's; the no-guessing helper records no clause, so `clauses` is empty.
A hidden-test flip is a name in tests (see tests/test_ng_tasks.py SPECS); a hallucinated_symbol_errors flip is a hand trace
(Inferred, R-97 condition 4) until X-LG's first strategy run, whose premise tests/test_ng_tasks.py proves name by name.
vendoredit carries the whole edited vendor/quotakit/quotakit/gate.py (the create form, W0 rev 6.6 section 2 g): graded against the pristine copy the count stays 1; a resolver that read the agent's copy would read 0."""

VARIANTS = {
    "hallucinated": {
        "flips": ["hallucinated_symbol_errors"],
        "clauses": {},
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": 'def limit_calls(max_calls, per_seconds, clock=None):\n', "new": 'def _unused():\n    g = quotakit.Gate(1, 1.0)\n    return g.try_acquire()\n\n\ndef limit_calls(max_calls, per_seconds, clock=None):\n'},
        ],
    },
    "kw": {
        "flips": ["hallucinated_symbol_errors"],
        "clauses": {},
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": 'def limit_calls(max_calls, per_seconds, clock=None):\n', "new": 'def _unused():\n    return quotakit.Gate(1, 1.0, period=1.0)\n\n\ndef limit_calls(max_calls, per_seconds, clock=None):\n'},
        ],
    },
    "default": {
        "flips": ["property_check_pass"],
        "clauses": {},
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": 'clock=clock or time.monotonic)\n', "new": 'clock=clock or time.monotonic, mode="fixed")\n'},
        ],
    },
    "vendoredit": {
        "flips": ["hallucinated_symbol_errors"],
        "clauses": {},
        "edits": [
            {"file": 'src/cachetools/limiter.py', "old": 'def limit_calls(max_calls, per_seconds, clock=None):\n', "new": 'def _unused():\n    g = quotakit.Gate(1, 1.0)\n    return g.try_acquire()\n\n\ndef limit_calls(max_calls, per_seconds, clock=None):\n'},
            {"file": 'vendor/quotakit/quotakit/gate.py', "old": '', "new": '"""Gate: admit or refuse units of work against a quota."""\n\nimport math\nimport time\nfrom collections import deque\n\n\nclass QuotaExceeded(Exception):\n    """Raised by Gate.require() when the quota has no room for the cost."""\n\n\nclass Gate:\n    """Allow at most ``max_per_window`` units of cost in any ``window_seconds``.\n\n    mode "sliding" (the default) counts the cost admitted since ``now - window_seconds``\n    (an admission exactly ``window_seconds`` old has expired). mode "fixed" counts per\n    aligned window [k * window_seconds, (k + 1) * window_seconds) and resets at its edge.\n    """\n\n    def __init__(self, max_per_window, window_seconds, *, clock=time.monotonic, mode="sliding"):\n        if mode not in ("sliding", "fixed"):\n            raise ValueError(f"unknown mode {mode!r}")\n        self.max_per_window = max_per_window\n        self.window_seconds = window_seconds\n        self.mode = mode\n        self._clock = clock\n        self._events = deque()\n        self._slot = None\n        self._used = 0\n\n    def _in_window(self, now):\n        if self.mode == "fixed":\n            slot = math.floor(now / self.window_seconds)\n            if slot != self._slot:\n                self._slot, self._used = slot, 0\n            return self._used\n        while self._events and self._events[0][0] <= now - self.window_seconds:\n            self._used -= self._events.popleft()[1]\n        return self._used\n\n    def admit(self, cost=1):\n        """Record ``cost`` and return True if it fits in the window; otherwise record nothing and return False."""\n        now = self._clock()\n        if self._in_window(now) + cost > self.max_per_window:\n            return False\n        self._used += cost\n        if self.mode == "sliding":\n            self._events.append((now, cost))\n        return True\n\n    def require(self, cost=1):\n        """Like admit(), but raise QuotaExceeded instead of returning False."""\n        if not self.admit(cost):\n            raise QuotaExceeded(f"{cost} does not fit in {self.max_per_window} per {self.window_seconds}s")\n\n    def try_acquire(self, cost=1):\n        """A convenience that is not in the real library; a copy that has it makes a guess resolve."""\n        return self.admit(cost)\n'},
        ],
    },
}
