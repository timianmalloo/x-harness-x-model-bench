"""Hidden functional tests for S2 (FAIL_TO_PASS), one principal: `FIRST`. The other user is named only in `USERS`.

Run in the grading copy: python -S -m unittest -v test_taskboard_hidden. Stdlib and the repository's own bottle.py only.
Every status and shape asserted here is in tasks/S2/prompt.md (test_s2_every_hidden_assertion_is_in_the_prompt).
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

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.getcwd()):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FIRST = "first"
OTHER = "second"
USERS = {FIRST: {"password": "pw-first-1", "team": 1}, OTHER: {"password": "pw-second-2", "team": 2}}
KEY = "key-for-the-hidden-tests"


def load_module():
    sys.modules.pop("examples.taskboard.app", None)
    sys.modules.pop("examples.taskboard", None)
    return importlib.import_module("examples.taskboard.app")


def call(app, method, path, cookie=None, body=None, query="", raw=None, form=None):
    if form is not None:
        payload, ctype = "&".join(k + "=" + v for k, v in form.items()).encode(), "application/x-www-form-urlencoded"
    else:
        payload = raw if raw is not None else (b"" if body is None else json.dumps(body).encode())
        ctype = "application/json" if payload else ""
    environ = {
        "REQUEST_METHOD": method, "SCRIPT_NAME": "", "PATH_INFO": path, "QUERY_STRING": query,
        "CONTENT_TYPE": ctype, "CONTENT_LENGTH": str(len(payload)),
        "SERVER_NAME": "localhost", "SERVER_PORT": "80", "SERVER_PROTOCOL": "HTTP/1.1",
        "REMOTE_ADDR": "127.0.0.1", "REMOTE_PORT": "50000",
        "wsgi.version": (1, 0), "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(payload),
        "wsgi.errors": sys.stderr, "wsgi.multithread": False, "wsgi.multiprocess": False, "wsgi.run_once": False,
    }
    if cookie is not None:
        environ["HTTP_COOKIE"] = cookie
    seen = {}

    def start_response(status, headers, exc_info=None):
        seen["status"], seen["headers"] = int(status.split()[0]), headers

    data = b"".join(app(environ, start_response))
    try:
        parsed = json.loads(data) if data else None
    except ValueError:
        parsed = data
    return seen["status"], parsed, seen["headers"]


def login(app, user=FIRST):
    """The `session` cookie pair the app issued, as a browser would send it back."""
    status, _, headers = call(app, "POST", "/login", form={"user": user, "password": USERS[user]["password"]})
    assert status == 200, status
    return [v.split(";")[0] for k, v in headers if k.lower() == "set-cookie" and v.startswith("session=")][0]


class TaskboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)  # the app keeps its database open; Windows cannot delete it
        self.files = os.path.join(self.tmp, "files")
        os.makedirs(self.files)
        self.app = load_module().create_app(os.path.join(self.tmp, "tasks.db"), self.files, KEY, dict(USERS))
        self.cookie = login(self.app)

    def make(self, title="t"):
        status, task, _ = call(self.app, "POST", "/tasks", self.cookie, body={"title": title})
        self.assertEqual(status, 201)
        return task

    def test_login_returns_200_and_a_session_cookie_and_any_other_login_401(self):
        status, _, headers = call(self.app, "POST", "/login", form={"user": FIRST, "password": USERS[FIRST]["password"]})
        self.assertEqual(status, 200)
        self.assertTrue(any(k.lower() == "set-cookie" and v.startswith("session=") for k, v in headers))
        for form in ({"user": FIRST, "password": "wrong"}, {"user": "nobody", "password": "x"}, {"user": FIRST}, {}):
            with self.subTest(form=form):
                status, _, _ = call(self.app, "POST", "/login", form=form)
                self.assertEqual(status, 401)

    def test_every_other_endpoint_returns_401_without_a_valid_session_cookie(self):
        task = self.make()
        id_path = "/tasks/%d" % task["id"]
        for method, path, body in (("POST", "/tasks", {"title": "t"}), ("GET", "/tasks", None), ("GET", id_path, None),
                                   ("DELETE", id_path, None), ("GET", "/files/a.txt", None)):
            for cookie in (None, "", "session=", "session=nope", "other=1"):
                with self.subTest(method=method, path=path, cookie=cookie):
                    status, _, _ = call(self.app, method, path, cookie, body=body)
                    self.assertEqual(status, 401)
        status, _, _ = call(self.app, "GET", id_path, self.cookie)
        self.assertEqual(status, 200)

    def test_create_returns_201_and_the_task(self):
        status, task, _ = call(self.app, "POST", "/tasks", self.cookie, body={"title": "Hello"})
        self.assertEqual(status, 201)
        self.assertEqual(set(task), {"id", "title"})
        self.assertIsInstance(task["id"], int)
        self.assertEqual(task["title"], "Hello")

    def test_create_rejects_a_body_that_is_not_a_json_object_with_a_string_title(self):
        for kwargs in ({"raw": b"{not json"}, {"body": [1]}, {"body": {}}, {"body": {"title": 1}}, {"body": {"title": None}}):
            with self.subTest(kwargs=kwargs):
                status, _, _ = call(self.app, "POST", "/tasks", self.cookie, **kwargs)
                self.assertEqual(status, 400)

    def test_get_by_id_returns_200_with_the_task_and_a_missing_id_404(self):
        task = self.make("one")
        status, got, _ = call(self.app, "GET", "/tasks/%d" % task["id"], self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(got, task)
        status, _, _ = call(self.app, "GET", "/tasks/%d" % (task["id"] + 100), self.cookie)
        self.assertEqual(status, 404)

    def test_list_is_in_id_order_and_limit_caps_it_and_a_bad_limit_is_400(self):
        made = [self.make("n%d" % i) for i in range(3)]
        status, data, _ = call(self.app, "GET", "/tasks", self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(data["tasks"], made)
        status, data, _ = call(self.app, "GET", "/tasks", self.cookie, query="limit=2")
        self.assertEqual((status, data["tasks"]), (200, made[:2]))
        for bad in ("abc", "-1", "1.5", ""):
            with self.subTest(limit=bad):
                status, _, _ = call(self.app, "GET", "/tasks", self.cookie, query="limit=" + bad)
                self.assertEqual(status, 400)

    def test_search_matches_title_ignoring_ascii_case_and_no_match_is_an_empty_list(self):
        a = self.make("Alpha Title")
        self.make("other")
        for text in ("alpha", "ALPHA", "ha ti"):
            status, data, _ = call(self.app, "GET", "/tasks", self.cookie, query="q=" + text.replace(" ", "%20"))
            self.assertEqual((status, data["tasks"]), (200, [a]), text)
        status, data, _ = call(self.app, "GET", "/tasks", self.cookie, query="q=zzz-no-match")
        self.assertEqual((status, data), (200, {"tasks": []}))

    def test_delete_returns_204_then_the_task_is_404(self):
        task = self.make()
        status, _, _ = call(self.app, "DELETE", "/tasks/%d" % task["id"], self.cookie)
        self.assertEqual(status, 204)
        status, _, _ = call(self.app, "GET", "/tasks/%d" % task["id"], self.cookie)
        self.assertEqual(status, 404)
        status, _, _ = call(self.app, "DELETE", "/tasks/%d" % task["id"], self.cookie)
        self.assertEqual(status, 404)

    def test_files_returns_the_content_of_a_file_in_files_dir_and_a_missing_file_404(self):
        with open(os.path.join(self.files, "note.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("hello file\n")
        status, data, _ = call(self.app, "GET", "/files/note.txt", self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(data, b"hello file\n")
        status, _, _ = call(self.app, "GET", "/files/absent.txt", self.cookie)
        self.assertEqual(status, 404)

    def test_importing_the_module_has_no_side_effects(self):
        def refuse(*args, **kwargs):
            raise AssertionError("a server was started")

        import socketserver
        import wsgiref.simple_server

        import bottle
        guards = [(bottle, "run"), (wsgiref.simple_server, "make_server"), (socketserver.TCPServer, "server_bind")]
        before = os.getcwd()
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty, True)  # a failing app leaves its database open
        os.chdir(empty)
        try:
            with contextlib.ExitStack() as stack:
                for owner, name in guards:
                    stack.enter_context(unittest.mock.patch.object(owner, name, refuse))
                module = load_module()
                self.assertEqual(os.listdir(empty), [])
                module.create_app(os.path.join(self.tmp, "other.db"), self.files, KEY, dict(USERS))
            self.assertEqual(os.listdir(empty), [])
        finally:
            os.chdir(before)


if __name__ == "__main__":
    unittest.main()
