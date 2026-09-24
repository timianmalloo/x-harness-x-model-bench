"""Host measurements must not turn a failed kernel query into a zero reading (residual 6)."""

import ctypes

import pytest

from harness_bench import host

pytestmark = pytest.mark.native


def _fail(out):
    ctypes.set_last_error(6)
    return 0


def test_a_failed_query_unbiased_interrupt_time_is_not_a_zero_reading(monkeypatch):
    monkeypatch.setattr(host._k32, "QueryUnbiasedInterruptTime", _fail)
    raised = None
    try:
        reading = host.unbiased_seconds()
    except OSError as exc:
        raised = exc
    assert raised is not None and raised.winerror == 6, reading


def test_a_failed_global_memory_status_ex_is_not_a_zero_reading(monkeypatch):
    monkeypatch.setattr(host._k32, "GlobalMemoryStatusEx", _fail)
    monkeypatch.setattr(ctypes.windll.kernel32, "GlobalMemoryStatusEx", _fail)
    raised = None
    try:
        reading = host.available_memory()
    except OSError as exc:
        raised = exc
    assert raised is not None and raised.winerror == 6, reading
