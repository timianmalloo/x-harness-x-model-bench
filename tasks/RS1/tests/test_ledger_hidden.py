"""Hidden functional tests for RS1 (FAIL_TO_PASS): `prometheus_client.ledger.post_event`.

Run in the grading copy: python -m unittest -v test_ledger_hidden. Stdlib only; the service is a local http.server on
127.0.0.1 inside each test (W1-L assume A3). Every behaviour asserted here is in tasks/RS1/prompt.md or
docs/ledger-service.md. Six tests, one per hidden-test id H-1..H-6; tasks/RS1/oracle/wrong_apps.py names the fixture that
turns each one red. A call that raises where a value is wanted fails the test with an assertion (`self.fail`), so a red
test is always a failure and never an error. Fault behaviour (delay, retry, repeat) is not tested here: the check owns it.
"""

import http.server
import importlib
import json
import socket
import sys
import threading
import unittest
from unittest import mock


class Service:
    """A one-reply ledger fake: every request gets `status` and `body`; the requests are kept."""

    def __init__(self, status=201, body=None):
        self.status, self.body, self.requests = status, {"id": 7} if body is None else body, []
        service = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                size = int(self.headers.get("Content-Length") or 0)
                # the raw request target: http.server rewrites a leading `//` in `self.path`, which would hide a doubled slash
                target = self.requestline.split()[1]
                service.requests.append((target, self.headers.get("Content-Type"), self.rfile.read(size)))
                data = json.dumps(service.body).encode()
                self.send_response(service.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def load():
    from prometheus_client import ledger
    return ledger


class LedgerTests(unittest.TestCase):
    def call(self, ledger, *args):
        try:
            return ledger.post_event(*args)
        except Exception as exc:  # noqa: BLE001 - a raise is a failed assertion, never an error
            self.fail("post_event raised %s: %s" % (type(exc).__name__, exc))

    def test_returns_the_new_event_id_as_an_int(self):
        ledger = load()
        with Service(201, {"id": 7}) as service:
            got = self.call(ledger, service.url, "jobs", 3)
        self.assertEqual(got, 7)
        self.assertIs(type(got), int)

    def test_posts_name_and_value_as_json_to_v1_events(self):
        ledger = load()
        with Service() as service:
            self.call(ledger, service.url, "jobs", 3)
        self.assertGreaterEqual(len(service.requests), 1)
        path, _, body = service.requests[0]
        self.assertEqual(path, "/v1/events")
        self.assertEqual(json.loads(body), {"name": "jobs", "value": 3})

    def test_a_400_reply_raises_ledger_error(self):
        ledger = load()
        with Service(400, {"error": "bad"}) as service:
            try:
                got = ledger.post_event(service.url, "jobs", 3)
            except ledger.LedgerError:
                return
            except Exception as exc:  # noqa: BLE001
                self.fail("raised %s, not LedgerError" % type(exc).__name__)
        self.fail("a 400 reply returned %r" % (got,))

    def test_an_unreachable_service_raises_ledger_error(self):
        ledger = load()
        # Port 0 is never listening, and a connect to it fails at once on every platform. A closed port is not used: on
        # Windows a connect to one is retried by the OS for about two seconds, so the call ends in a timeout, not a refusal.
        try:
            got = ledger.post_event("http://127.0.0.1:0", "jobs", 3)
        except ledger.LedgerError:
            return
        except Exception as exc:  # noqa: BLE001
            self.fail("raised %s, not LedgerError" % type(exc).__name__)
        self.fail("an unreachable service returned %r" % (got,))

    def test_a_trailing_slash_on_base_url_is_accepted(self):
        ledger = load()
        with Service() as service:
            self.call(ledger, service.url + "/", "jobs", 3)
        self.assertEqual([r[0] for r in service.requests][:1], ["/v1/events"])

    def test_importing_the_module_has_no_side_effect(self):
        sys.modules.pop("prometheus_client.ledger", None)
        started, connected, opened = [], [], []
        with mock.patch.object(threading.Thread, "start", lambda self, *a, **k: started.append(self)), \
                mock.patch.object(socket.socket, "connect", lambda self, *a, **k: connected.append(a)), \
                mock.patch("urllib.request.OpenerDirector.open", lambda self, *a, **k: opened.append(a)):
            try:
                importlib.import_module("prometheus_client.ledger")
            except Exception as exc:  # noqa: BLE001
                self.fail("the import raised %s" % type(exc).__name__)
        self.assertEqual((started, connected, opened), ([], [], []))
        with Service() as service:  # the module still works after a quiet import: one call, one request
            self.call(load(), service.url, "jobs", 3)
        self.assertEqual(len(service.requests), 1)


if __name__ == "__main__":
    unittest.main()
