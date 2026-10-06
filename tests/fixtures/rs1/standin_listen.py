"""Stand-in for `bench_check.listen` (W1-L section 4, seam 3) until X-LB1's real listener joins. Test fixture, never src/.

`tests/test_rs1_task.py` appends this file's text to a copy of the real `grade/bench_check.py`, so RS1's `check.py` finds
`bc.listen` in its own check copy. The real listener binds the literal 127.0.0.1 with SO_EXCLUSIVEADDRUSE and asserts
`getsockname` (HB-CHK-005); this one binds `("127.0.0.1", 0)` and nothing more.

  assume: the real `listen` takes one handler and returns an object with `.url` and `.close()`, and `handle(method, path,
          headers, body)` returns a dict: {"status", "json", "delay"?} | {"hang": True} | {"drop": True}.
  confirm: X-LB1's merged `listen` (the ready K-item reads its signature and deletes this file).
  breaks if false: check.py raises at `bc.listen(...)`, exit 5, and the RS1 test fails loudly.
"""


def listen(handle):
    import http.server
    import json
    import threading

    stop = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(size)
            headers = {k.lower(): v for k, v in self.headers.items()}
            reply = handle("POST", self.path, headers, body)
            if reply.get("drop"):
                self.close_connection = True
                return
            if reply.get("hang"):
                stop.wait(60)
                return
            if reply.get("delay"):
                stop.wait(reply["delay"])
            data = json.dumps(reply["json"]).encode()
            self.send_response(reply["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except OSError:
                pass

        def log_message(self, *args):
            pass

    class Server(http.server.ThreadingHTTPServer):
        allow_reuse_address = False
        daemon_threads = True

    server = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    class Listener:
        url = "http://127.0.0.1:%d" % server.server_address[1]

        def close(self):
            stop.set()
            server.shutdown()
            server.server_close()

    return Listener()
