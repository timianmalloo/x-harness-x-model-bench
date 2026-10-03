"""Hidden functional tests for S1 (FAIL_TO_PASS), one principal: the first entry of `tokens`.

Run in the grading copy: python -m unittest -v test_notes_hidden. Stdlib only. Every status and shape asserted here
is in tasks/S1/prompt.md (test_s1_every_hidden_assertion_is_in_the_prompt).
"""

import contextlib
import importlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(HERE, "src"), HERE, os.getcwd(), os.path.join(os.getcwd(), "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TOKEN = "tok-first-0001"
OTHER = "tok-second-0002"
TOKENS = {TOKEN: "first", OTHER: "second"}


def load_module():
    sys.modules.pop("examples.notes.app", None)
    sys.modules.pop("examples.notes", None)
    return importlib.import_module("examples.notes.app")


def call(app, method, path, token=TOKEN, body=None, query="", raw=None, auth=None):
    payload = raw if raw is not None else (b"" if body is None else json.dumps(body).encode())
    environ = {
        "REQUEST_METHOD": method, "SCRIPT_NAME": "", "PATH_INFO": path, "QUERY_STRING": query,
        "CONTENT_TYPE": "application/json" if payload else "", "CONTENT_LENGTH": str(len(payload)),
        "SERVER_NAME": "localhost", "SERVER_PORT": "80", "SERVER_PROTOCOL": "HTTP/1.1",
        "REMOTE_ADDR": "127.0.0.1", "REMOTE_PORT": "50000",
        "wsgi.version": (1, 0), "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(payload),
        "wsgi.errors": sys.stderr, "wsgi.multithread": False, "wsgi.multiprocess": False, "wsgi.run_once": False,
    }
    if auth is not None:
        environ["HTTP_AUTHORIZATION"] = auth
    elif token is not None:
        environ["HTTP_AUTHORIZATION"] = "Bearer " + token
    seen = {}

    def start_response(status, headers, exc_info=None):
        seen["status"] = int(status.split()[0])

    chunks = list(app(environ, start_response))
    data = b"".join(chunks)
    try:
        return seen["status"], (json.loads(data) if data else None)
    except ValueError:
        return seen["status"], data


class NotesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)  # the app keeps its database open; Windows cannot delete it
        self.app = load_module().create_app(dict(TOKENS), os.path.join(self.tmp, "notes.db"))

    def make(self, title="t", body="b"):
        status, note = call(self.app, "POST", "/notes", body={"title": title, "body": body})
        self.assertEqual(status, 201)
        return note

    def test_create_returns_201_and_the_note(self):
        status, note = call(self.app, "POST", "/notes", body={"title": "Hello", "body": "World"})
        self.assertEqual(status, 201)
        self.assertEqual(set(note), {"id", "title", "body"})
        self.assertIsInstance(note["id"], int)
        self.assertEqual((note["title"], note["body"]), ("Hello", "World"))

    def test_create_rejects_a_body_that_is_not_a_json_object_with_two_string_fields(self):
        for kwargs in ({"raw": b"{not json"}, {"body": [1]}, {"body": {"title": "x"}}, {"body": {"body": "x"}},
                       {"body": {"title": 1, "body": "x"}}, {"body": {"title": "x", "body": None}}):
            with self.subTest(kwargs=kwargs):
                status, _ = call(self.app, "POST", "/notes", **kwargs)
                self.assertEqual(status, 400)

    def test_get_by_id_returns_200_with_the_note_and_a_missing_id_404(self):
        note = self.make("one", "two")
        status, got = call(self.app, "GET", "/notes/%d" % note["id"])
        self.assertEqual(status, 200)
        self.assertEqual(got, note)
        status, _ = call(self.app, "GET", "/notes/%d" % (note["id"] + 100))
        self.assertEqual(status, 404)

    def test_list_is_in_id_order(self):
        made = [self.make("n%d" % i, "x") for i in range(3)]
        status, data = call(self.app, "GET", "/notes")
        self.assertEqual(status, 200)
        self.assertEqual([n["id"] for n in data["notes"]], sorted(n["id"] for n in made))
        self.assertEqual(data["notes"], made)

    def test_search_matches_title_or_body_ignoring_ascii_case_and_no_match_is_an_empty_list(self):
        a = self.make("Alpha Title", "nothing")
        b = self.make("plain", "has ALPHA inside")
        self.make("other", "other")
        status, data = call(self.app, "GET", "/notes", query="q=" + quote("alpha"))
        self.assertEqual(status, 200)
        self.assertEqual(data["notes"], [a, b])
        status, data = call(self.app, "GET", "/notes", query="q=" + quote("ALPHA"))
        self.assertEqual(data["notes"], [a, b])
        status, data = call(self.app, "GET", "/notes", query="q=" + quote("zzz-no-match"))
        self.assertEqual((status, data), (200, {"notes": []}))

    def test_delete_returns_204_then_the_note_is_404(self):
        note = self.make()
        status, _ = call(self.app, "DELETE", "/notes/%d" % note["id"])
        self.assertEqual(status, 204)
        status, _ = call(self.app, "GET", "/notes/%d" % note["id"])
        self.assertEqual(status, 404)
        status, _ = call(self.app, "DELETE", "/notes/%d" % note["id"])
        self.assertEqual(status, 404)

    def test_missing_unknown_or_near_miss_token_gets_401_on_every_endpoint(self):
        note = self.make()
        id_path = "/notes/%d" % note["id"]
        bad = (None, "nope", TOKEN + "x", TOKEN[:-1])
        for method, path, body in (("POST", "/notes", {"title": "t", "body": "b"}), ("GET", "/notes", None),
                                   ("GET", id_path, None), ("DELETE", id_path, None)):
            for token in bad:
                with self.subTest(method=method, path=path, token=token):
                    status, _ = call(self.app, method, path, token=token, body=body)
                    self.assertEqual(status, 401)
        status, _ = call(self.app, "GET", id_path)
        self.assertEqual(status, 200)

    def test_importing_the_module_has_no_side_effects(self):
        def refuse(*args, **kwargs):
            raise AssertionError("a server was started")

        # Server-start entry points, not socket.socket: asyncio's own event loop opens a loopback socket pair on
        # Windows, so a socket.socket guard would fail every correct app (observed, X-I).
        import asyncio.base_events
        import microdot.microdot
        import socketserver
        guards = [(microdot.microdot.Microdot, "run"), (microdot.microdot.Microdot, "start_server"),
                  (asyncio.base_events.BaseEventLoop, "create_server"), (socketserver.TCPServer, "server_bind")]
        before = os.getcwd()
        with tempfile.TemporaryDirectory() as empty:
            os.chdir(empty)
            try:
                with contextlib.ExitStack() as stack:
                    for owner, name in guards:
                        stack.enter_context(unittest.mock.patch.object(owner, name, refuse))
                    module = load_module()
                    self.assertEqual(os.listdir(empty), [])
                    module.create_app(dict(TOKENS), os.path.join(self.tmp, "other.db"))
                self.assertEqual(os.listdir(empty), [])
            finally:
                os.chdir(before)


if __name__ == "__main__":
    unittest.main()
