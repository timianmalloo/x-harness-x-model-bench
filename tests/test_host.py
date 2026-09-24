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
