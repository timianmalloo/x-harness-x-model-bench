"""Hidden tests for NG1 (W1-L section 7.3): cachetools.limiter on the vendored quotakit.

Run as `python -S -m unittest -v test_limiter_hidden` from the root of the graded tree, so nothing is installed and both
`src` and `vendor/quotakit` are put on the path here. Every outcome that is not the one the test asserts, a missing module
or an exception raised by the decorated call included, is reported through `self.fail`, so a wrong solution is a FAIL
(an assertion), never an ERROR.
"""

import importlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(ROOT, "src"), os.path.join(ROOT, "vendor", "quotakit")]


class FakeClock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


class Counted:
    """A function that counts the times its body ran."""

    def __init__(self):
        self.ran = 0

    def __call__(self, *args, **kwargs):
        """Counted docstring."""
        self.ran += 1
        return ("ran", self.ran, args, tuple(sorted(kwargs.items())))


class LimiterHidden(unittest.TestCase):
    def limiter(self):
        try:
            return importlib.import_module("cachetools.limiter")
        except Exception as exc:  # noqa: BLE001 - any failure to load is a failed test
            self.fail(f"importing cachetools.limiter raised {type(exc).__name__}: {exc}")

    def decorated(self, max_calls=3, per_seconds=1.0, clock="fake"):
        """(wrapper, counter, clock) for a fresh counted function under limit_calls."""
        module = self.limiter()
        counted, fake = Counted(), FakeClock()

        def work(*args, **kwargs):
            """Work docstring."""
            return counted(*args, **kwargs)

        kwargs = {} if clock is None else {"clock": fake if clock == "fake" else clock}
        try:
            decorator = module.limit_calls(max_calls, per_seconds, **kwargs)
            return decorator(work), counted, fake
        except Exception as exc:  # noqa: BLE001
            self.fail(f"limit_calls(...)(function) raised {type(exc).__name__}: {exc}")

    def call(self, wrapper, *args, **kwargs):
        """("ok", value) or ("raised", exception); an exception is data, not an error."""
        try:
            return "ok", wrapper(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            return "raised", exc

    def test_n1_allows_max_calls_calls(self):
        wrapper, counted, _ = self.decorated(3, 1.0)
        outcomes = [self.call(wrapper)[0] for _ in range(3)]
        self.assertEqual(outcomes, ["ok", "ok", "ok"])
        self.assertEqual(counted.ran, 3)

    def test_n2_the_next_call_raises_limit_exceeded_and_does_not_run(self):
        module = self.limiter()
        wrapper, counted, _ = self.decorated(3, 1.0)
        for _ in range(3):
            self.call(wrapper)
        kind, value = self.call(wrapper)
        self.assertEqual(kind, "raised")
        self.assertIsInstance(value, module.LimitExceeded)
        self.assertEqual(counted.ran, 3)

    def test_n3_the_window_slides(self):
        wrapper, counted, clock = self.decorated(2, 1.0)
        ran = []
        for t in (0.0, 0.9, 1.05, 1.2):
            clock.now = t
            before = counted.ran
            self.call(wrapper)
            ran.append(counted.ran - before)
        # 0.0 has left the window at 1.05, so a third call fits; at 1.2 the window (0.2, 1.2] holds 0.9 and 1.05.
        self.assertEqual(ran, [1, 1, 1, 0])

    def test_n4_a_clock_of_none_means_the_default_clock(self):
        for clock in (None, "omitted"):
            with self.subTest(clock=clock):
                kwargs = {} if clock == "omitted" else {"clock": None}
                module = self.limiter()
                counted = Counted()
                try:
                    wrapper = module.limit_calls(2, 60.0, **kwargs)(counted)
                except Exception as exc:  # noqa: BLE001
                    self.fail(f"limit_calls raised {type(exc).__name__}: {exc}")
                kinds = [self.call(wrapper)[0] for _ in range(3)]
                self.assertEqual(kinds, ["ok", "ok", "raised"])
                self.assertEqual(counted.ran, 2)

    def test_n5_the_wrapper_keeps_the_name_the_doc_and_the_result(self):
        wrapper, counted, _ = self.decorated(3, 1.0)
        self.assertEqual(wrapper.__name__, "work")
        self.assertEqual(wrapper.__doc__, "Work docstring.")
        kind, value = self.call(wrapper, 1, 2, key="v")
        self.assertEqual(kind, "ok")
        self.assertEqual(value, ("ran", 1, (1, 2), (("key", "v"),)))

    def test_n6_limit_exceeded_is_its_own_exception(self):
        module = self.limiter()
        try:
            quotakit = importlib.import_module("quotakit")
        except Exception as exc:  # noqa: BLE001
            self.fail(f"importing quotakit raised {type(exc).__name__}: {exc}")
        self.assertTrue(isinstance(module.LimitExceeded, type) and issubclass(module.LimitExceeded, Exception))
        self.assertFalse(issubclass(module.LimitExceeded, quotakit.QuotaExceeded))
        wrapper, _, _ = self.decorated(1, 1.0)
        self.call(wrapper)
        kind, value = self.call(wrapper)
        self.assertEqual(kind, "raised")
        self.assertNotIsInstance(value, quotakit.QuotaExceeded)


if __name__ == "__main__":
    unittest.main()
