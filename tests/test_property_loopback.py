"""X-LB1: the loopback fake. `bench_check.listen()` (W0 R6-17, ADR-0018 s3, W1-L F15) and, in K2, the shape (b) path."""

import socket
import sys
import threading

import pytest

from harness_bench import errors
from harness_bench.grade import bench_check as bc

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the check runner is Windows-only (ADR-0018 s8)")


def test_hb_chk_005_is_a_run_code():
    assert "127.0.0.1" in errors.RUN_CODES["HB-CHK-005"]


def test_two_listeners_in_parallel_get_distinct_loopback_ports():
    """EV-3 parallel-port isolation (F15): port 0 per case, so two cases never collide."""
    with bc.listen() as a, bc.listen() as b:
        assert a.getsockname()[0] == b.getsockname()[0] == "127.0.0.1"
        assert a.getsockname()[1] != b.getsockname()[1]


def test_many_parallel_listeners_never_collide():
    ports, gate = [], threading.Barrier(8)

    def one():
        with bc.listen() as s:
            gate.wait(10)
            ports.append(s.getsockname()[1])
            gate.wait(10)

    threads = [threading.Thread(target=one) for _ in range(8)]
    [t.start() for t in threads]
    [t.join(20) for t in threads]
    assert len(ports) == 8 and len(set(ports)) == 8


def test_a_bind_to_any_other_address_is_refused_with_hb_chk_005_and_leaves_no_socket(monkeypatch):
    made = []
    real = socket.socket

    def spy(*a, **k):
        made.append(real(*a, **k))
        return made[-1]

    monkeypatch.setattr(bc, "_BIND", ("0.0.0.0", 0))  # noqa: S104 - the point of the test
    monkeypatch.setattr(bc.socket, "socket", spy)
    with pytest.raises(bc.ListenerError, match="HB-CHK-005"), bc.listen():
        pass
    assert made and all(s.fileno() == -1 for s in made)


def test_the_listener_socket_is_closed_when_its_case_ends():
    with bc.listen() as s:
        port = s.getsockname()[1]
        assert s.fileno() != -1
    assert s.fileno() == -1
    with bc.listen() as again:  # the closed port is free to a fresh listener
        assert again.getsockname()[0] == "127.0.0.1"
    assert isinstance(port, int)


def test_the_listener_is_exclusive_on_its_port():
    with bc.listen() as s:
        other = socket.socket()
        try:
            with pytest.raises(OSError):
                other.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                other.bind(s.getsockname())
        finally:
            other.close()
