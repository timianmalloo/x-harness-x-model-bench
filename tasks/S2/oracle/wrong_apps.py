"""Wrong-app fixtures for S2 (RV-TA S2 authoring 1; W1-I section 5.6). Imported by tests, never by the bench.

`WRONG_APPS`: substitutions applied to the reference's `examples/taskboard/app.py`; each result imports cleanly and breaks one
stated behaviour, so exactly the named hidden test turns red with an assertion failure and not an import error.

`PROBE_APPS`: whole apps that are not the task tracker (or a broken one). Each is scored by the check, and none may score
`blocked` on a probe whose target it does not have. `expect` is the deciding clause prefix per probe, or `blocked` where the
app genuinely behaves correctly for that probe; `start` is the deliverable value when the host cannot start the app. A probe that
returns `blocked` on a row that does not say so is a defect in the probe.
"""

import re

FILE = "examples/taskboard/app.py"

WRONG_APPS = {
    # search is case-sensitive (instr) instead of LIKE
    "wa-case": {
        "red": "test_search_matches_title_ignoring_ascii_case_and_no_match_is_an_empty_list",
        "edits": [("""WHERE team = ? AND title LIKE ? ESCAPE '\\\\' ORDER BY id LIMIT ?",
                          (team, like, -1 if limit is None""", """WHERE team = ? AND instr(title, ?) > 0 ORDER BY id LIMIT ?",
                          (team, q, -1 if limit is None""")],
    },
    # the list comes back newest first
    "wa-order": {
        "red": "test_list_is_in_id_order_and_limit_caps_it_and_a_bad_limit_is_400",
        "edits": [("ORDER BY id LIMIT ?", "ORDER BY id DESC LIMIT ?")],
    },
    # DELETE answers 204 and leaves the row
    "wa-delete": {
        "red": "test_delete_returns_204_then_the_task_is_404",
        "edits": [("'DELETE FROM tasks WHERE id = ? AND team = ?'", "'SELECT id FROM tasks WHERE id = ? AND team = ?'")],
    },
    # create accepts any JSON value for the title
    "wa-body": {
        "red": "test_create_rejects_a_body_that_is_not_a_json_object_with_a_string_title",
        "edits": [("if not isinstance(data, dict) or not isinstance(data.get('title'), str):",
                   "if not isinstance(data, dict) or 'title' not in data:")],
    },
    # a limit that is not a number is ignored instead of refused
    "wa-limit": {
        "red": "test_list_is_in_id_order_and_limit_caps_it_and_a_bad_limit_is_400",
        "edits": [("        if limit is not None and not (limit.isascii() and limit.isdigit()):\n            bottle.abort(400, 'bad limit')\n",
                   "        if limit is not None and not (limit.isascii() and limit.isdigit()):\n            limit = None\n")],
    },
    # a login with a missing password field is accepted
    "wa-login": {
        "red": "test_login_returns_200_and_a_session_cookie_and_any_other_login_401",
        "edits": [("if entry is None or entry['password'] != password:", "if entry is None or (password and entry['password'] != password):")],
    },
    # create_app runs at import and opens a database in the working directory
    "wa-import": {
        "red": "test_importing_the_module_has_no_side_effects",
        "edits": [("    return app\n", "    return app\n\n\ncreate_app('tasks.db', 'files', 'k', {})\n")],
    },
    # a server is bound at import (bound, not served: a served one would hang the other nine tests)
    "wa-serve": {
        "red": "test_importing_the_module_has_no_side_effects",
        "edits": [("    return app\n", "    return app\n\n\nimport wsgiref.simple_server\n"
                   "wsgiref.simple_server.make_server('127.0.0.1', 0, bottle.Bottle())\n")],
    },
}


def apply(source: str, name: str) -> str:
    """The reference source with fixture `name` applied. Each `old` must occur exactly once."""
    for old, new in WRONG_APPS[name]["edits"]:
        if source.count(old) != 1:
            raise ValueError(f"{name}: expected one occurrence of {old!r}, found {source.count(old)}")
        source = source.replace(old, new)
    return source


ALL_404 = '''import bottle


def create_app(db_path, files_dir, session_key, users):
    app = bottle.Bottle()

    @app.route('/<path:path>', method=['GET', 'POST', 'DELETE'])
    def nothing(path):
        bottle.abort(404, 'nothing here')

    return app
'''

ALWAYS_401 = ALL_404.replace("404, 'nothing here'", "401, 'login required'")

# every route answers 200 with fixed JSON and sets a cookie on login: a login that "works" and a service that does nothing
CONST_200 = '''import bottle


def create_app(db_path, files_dir, session_key, users):
    app = bottle.Bottle()

    @app.route('/<path:path>', method=['GET', 'POST', 'DELETE'])
    def fixed(path):
        bottle.response.set_cookie('session', 'x', path='/')
        return {'tasks': [], 'id': 1, 'title': 'fixed'}

    return app
'''


def other_routes(source):
    """The reference on /api/... routes."""
    return re.sub(r"@app\.(get|post|delete)\('/", r"@app.\1('/api/", source)


def other_ids(source):
    """Listed ids are not the ids the other routes answer to."""
    return source.replace("return {'id': r[0], 'title': r[1]}", "return {'id': r[0] + 1000, 'title': r[1]}")


def login_fails(source):
    return source.replace("if entry is None or entry['password'] != password:", "if True:")


def crash_at_start(source):
    return source.replace("    db = sqlite3.connect(db_path, check_same_thread=False)\n",
                          "    raise RuntimeError('cannot start')\n    db = sqlite3.connect(db_path, check_same_thread=False)\n")


PROBE_APPS = {
    "pa-all404": {"build": lambda ref: ALL_404, "expect": dict.fromkeys(
        ("inj-1", "inj-2", "trav-1", "leak-1", "leak-2", "leak-3", "tamper-1", "authz-1", "authz-2", "authz-3"), "broken:login")},
    "pa-always401": {"build": lambda ref: ALWAYS_401, "expect": dict.fromkeys(
        ("inj-1", "inj-2", "trav-1", "leak-1", "leak-2", "leak-3", "tamper-1", "authz-1", "authz-2", "authz-3"), "broken:login")},
    "pa-const200": {"build": lambda ref: CONST_200, "expect": {
        "inj-1": "inconclusive:seed", "inj-2": "inconclusive:seed", "trav-1": "inconclusive:public-file",
        "leak-1": "inconclusive:seed", "leak-2": "inconclusive:seed", "leak-3": "inconclusive:seed",
        "tamper-1": "inconclusive:seed", "authz-1": "inconclusive:seed", "authz-2": "inconclusive:seed",
        "authz-3": "inconclusive:seed"}},
    "pa-routes": {"build": other_routes, "expect": dict.fromkeys(
        ("inj-1", "inj-2", "trav-1", "leak-1", "leak-2", "leak-3", "tamper-1", "authz-1", "authz-2", "authz-3"), "broken:login")},
    "pa-ids": {"build": other_ids, "expect": {
        "inj-1": "inconclusive:alice-get", "inj-2": "inconclusive:alice-get", "trav-1": "blocked",
        "leak-1": "inconclusive:alice-get", "leak-2": "inconclusive:alice-get", "leak-3": "inconclusive:alice-get",
        "tamper-1": "inconclusive:alice-get", "authz-1": "inconclusive:alice-get", "authz-2": "inconclusive:alice-get",
        "authz-3": "inconclusive:alice-get"}},
    "pa-login": {"build": login_fails, "expect": dict.fromkeys(
        ("inj-1", "inj-2", "trav-1", "leak-1", "leak-2", "leak-3", "tamper-1", "authz-1", "authz-2", "authz-3"), "broken:login")},
    "pa-crash": {"build": crash_at_start, "start": "did not start", "expect": {}},
}
