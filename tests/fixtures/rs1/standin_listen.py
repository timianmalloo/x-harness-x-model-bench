"""Stand-in for X-LB1's `bench_check.listen` and `probe_host(case, sock)` until that work joins. Test fixture, never src/.

`tests/test_rs1_task.py` appends this file's text to a copy of the real `grade/bench_check.py`, so RS1's `check.py` sees the
interface X-LB1 built: `listen()` is a no-argument context manager yielding a bound `127.0.0.1:0` socket, and
`probe_host(case, sock)` substitutes `{fake_url}` (http://127.0.0.1:<port>) in the frame's args and kwargs. The check owns
the fake and accepts on the socket. K4 deletes this file and the append; `check.py` does not change.

  assume: X-LB1's `listen()` and `probe_host(case, sock)` behave as the coordinator's seam answer says (not read in code).
  confirm: the merged `bench_check.py` (K4 reads its signatures).
  breaks if false: check.py raises at `bc.listen()` or `bc.probe_host(case, sock)`, exit 5, and the RS1 test fails loudly.
"""

import contextlib as _contextlib
import socket as _socket

_real_probe_host = probe_host   # noqa: F821 - defined above in the real bench_check text this file is appended to


@_contextlib.contextmanager
def listen():
    sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(16)
        yield sock
    finally:
        sock.close()


def _fill(value, url):
    if isinstance(value, str):
        return value.replace("{fake_url}", url)
    if isinstance(value, list):
        return [_fill(v, url) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, url) for k, v in value.items()}
    return value


def probe_host(case, sock=None):
    host = _real_probe_host(case)
    if sock is not None:
        url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        request = host.request
        host.request = lambda frame: request(_fill(frame, url))
    return host
