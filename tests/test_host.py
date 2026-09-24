"""A failed host query is not recorded (None), never a zero reading (residual 6)."""

import ctypes

import pytest

from harness_bench import host

pytestmark = pytest.mark.native


def _fail(out):
    ctypes.set_last_error(6)
    return 0


def test_a_failed_query_unbiased_interrupt_time_is_not_recorded(monkeypatch):
    monkeypatch.setattr(host._k32, "QueryUnbiasedInterruptTime", _fail)
    assert host.unbiased_seconds() is None


def test_sleep_detector_returns_false_on_a_none_reading(monkeypatch):
    detector = host.SleepDetector(60)
    monkeypatch.setattr(host, "unbiased_seconds", lambda: None)
    assert detector.slept() is False


def test_a_failed_global_memory_status_ex_is_not_recorded(monkeypatch):
    monkeypatch.setattr(host._k32, "GlobalMemoryStatusEx", _fail)
    monkeypatch.setattr(ctypes.windll.kernel32, "GlobalMemoryStatusEx", _fail)
    assert host.available_memory() is None


def test_available_memory_and_unbiased_seconds_return_real_positive_values():
    memory = host.available_memory()
    assert isinstance(memory, int)
    assert memory > 0

    unbiased = host.unbiased_seconds()
    assert isinstance(unbiased, float)
    assert unbiased > 0


def test_sleep_detector_recovers_after_a_missing_first_reading(monkeypatch):
    """The first unbiased reading is missing (None); the next good reading becomes the anchor,
    and a gap detected against the reading after that still trips slept()."""
    walls = iter([50.0, 100.0, 200.0])
    unbiaseds = iter([None, 1000.0, 1090.0])
    monkeypatch.setattr(host.time, "time", lambda: next(walls))
    monkeypatch.setattr(host, "unbiased_seconds", lambda: next(unbiaseds))

    detector = host.SleepDetector(5.0)
    assert detector.slept() is False  # first good reading anchors; nothing to compare yet
    assert detector.slept() is True  # wall advanced 100s, unbiased only 90s: a 10s gap > 5s
