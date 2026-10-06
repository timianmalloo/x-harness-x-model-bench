"""Hidden functional tests for RS2 (FAIL_TO_PASS): `structlog.shipper.HttpShipper`.

Run in the grading copy: python -S -m unittest -v test_shipper_hidden. Stdlib only; the collector is a local http.server on
127.0.0.1 inside each test (W1-L assume A3). Every behaviour asserted here is in tasks/RS2/prompt.md or docs/collector.md.
Five tests, one per hidden-test id S-1..S-5; tasks/RS2/oracle/wrong_apps.py names the fixture that turns each one red. A call
that raises where a value is wanted fails the test with an assertion (`self.fail`), so a red test is always a failure and
never an error. Fault behaviour (delay, retry, repeat, order across a failure) is not tested here: the check owns it.
"""

import http.server
import json
import os
import sys
import threading
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(ROOT, "src")]


class Collector:
    """A one-reply collector fake: every request gets `status`; a 200 reply counts the records. The batches are kept."""

    def __init__(self, status=200):
        self.status, self.batches = status, []
        collector = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                size = int(self.headers.get("Content-Length") or 0)
                batch = json.loads(self.rfile.read(size))
                collector.batches.append((self.path, batch))
                reply = {"accepted": len(batch.get("records", []))} if collector.status == 200 else {"error": "refused"}
                data = json.dumps(reply).encode()
                self.send_response(collector.status)
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
    from structlog import shipper
    return shipper


class ShipperTests(unittest.TestCase):
    def flush(self, shipper):
        try:
            return shipper.flush()
        except Exception as exc:  # noqa: BLE001 - a raise is a failed assertion, never an error
            self.fail("flush raised %s: %s" % (type(exc).__name__, exc))

    def test_processor_returns_event_dict_unchanged_and_buffers_a_copy(self):
        module = load()
        with Collector() as collector:
            shipper = module.HttpShipper(collector.url)
            event = {"event": "a", "n": 1}
            out = shipper.processor(None, "info", event)
            self.assertIs(out, event)
            self.assertEqual(out, {"event": "a", "n": 1})
            event["n"] = 2  # a change after the processor ran must not reach the buffered copy
            self.flush(shipper)
        self.assertEqual(len(collector.batches), 1)
        self.assertEqual(collector.batches[0][1]["records"], [{"event": "a", "n": 1}])

    def test_flush_returns_the_accepted_count_and_empties_the_buffer(self):
        module = load()
        with Collector() as collector:
            shipper = module.HttpShipper(collector.url)
            shipper.processor(None, "info", {"event": "a"})
            shipper.processor(None, "info", {"event": "b"})
            self.assertEqual(self.flush(shipper), 2)
            shipper.processor(None, "info", {"event": "c"})
            self.assertEqual(self.flush(shipper), 1)
        self.assertEqual(len(collector.batches), 2)
        self.assertEqual(collector.batches[1][1]["records"], [{"event": "c"}])  # the first two records were sent once

    def test_a_refused_batch_raises_ship_error(self):
        module = load()
        with Collector(400) as collector:
            shipper = module.HttpShipper(collector.url)
            shipper.processor(None, "info", {"event": "a"})
            try:
                got = shipper.flush()
            except module.ShipError:
                return
            except Exception as exc:  # noqa: BLE001
                self.fail("raised %s, not ShipError" % type(exc).__name__)
        self.fail("a 400 reply returned %r" % (got,))

    def test_an_empty_buffer_sends_nothing(self):
        module = load()
        with Collector() as collector:
            shipper = module.HttpShipper(collector.url)
            got = self.flush(shipper)
        self.assertEqual(got, 0)
        self.assertEqual(collector.batches, [])

    def test_records_are_sent_in_the_order_they_were_buffered(self):
        module = load()
        with Collector() as collector:
            shipper = module.HttpShipper(collector.url)
            for name in ("a", "b", "c"):
                shipper.processor(None, "info", {"event": name})
            self.flush(shipper)
        self.assertEqual(len(collector.batches), 1)
        self.assertEqual(collector.batches[0][0], "/v1/logs")
        self.assertEqual([r["event"] for r in collector.batches[0][1]["records"]], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
