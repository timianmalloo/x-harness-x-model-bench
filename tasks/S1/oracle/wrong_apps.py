"""Wrong-app fixtures for S1's hidden tests (W1-I section 5.6, RV-TA W1-I 1, D3).

Each fixture is a list of `(old, new)` substitutions applied to the reference's `examples/notes/app.py` at test time. The
result imports cleanly and breaks one stated behaviour, so exactly the named hidden test turns red, with an assertion
failure and not an import error. `apply` refuses an `old` that is not found exactly once.
"""

FILE = "examples/notes/app.py"

SEARCH_OLD = r'''        like = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        rows = db.execute(
            "SELECT id, title, body FROM notes WHERE owner = ? AND "
            "(title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\') ORDER BY id",
            (request.g.current_user, like, like)).fetchall()
'''

WRONG_APPS = {
    # search is case-sensitive (instr) instead of LIKE
    "wa-case": {
        "red": "test_search_matches_title_or_body_ignoring_ascii_case_and_no_match_is_an_empty_list",
        "edits": [(SEARCH_OLD, '''        rows = db.execute(
            "SELECT id, title, body FROM notes WHERE owner = ? AND "
            "(instr(title, ?) > 0 OR instr(body, ?) > 0) ORDER BY id",
            (request.g.current_user, q, q)).fetchall()
''')],
    },
    # the list comes back newest first
    "wa-order": {
        "red": "test_list_is_in_id_order",
        "edits": [(r'''OR body LIKE ? ESCAPE '\\') ORDER BY id",''', r'''OR body LIKE ? ESCAPE '\\') ORDER BY id DESC",''')],
    },
    # DELETE answers 204 and leaves the row
    "wa-delete": {
        "red": "test_delete_returns_204_then_the_note_is_404",
        "edits": [("'DELETE FROM notes WHERE id = ? AND owner = ?'", "'SELECT id FROM notes WHERE id = ? AND owner = ?'")],
    },
    # create accepts any JSON value for the two fields
    "wa-body": {
        "red": "test_create_rejects_a_body_that_is_not_a_json_object_with_two_string_fields",
        "edits": [('''        if not isinstance(data, dict) or not isinstance(data.get('title'), str) \\
                or not isinstance(data.get('body'), str):
''', '''        if not isinstance(data, dict) or 'title' not in data or 'body' not in data:
''')],
    },
    # create_app runs at import and opens a database in the working directory
    "wa-import": {
        "red": "test_importing_the_module_has_no_side_effects",
        "edits": [("    return app\n", "    return app\n\n\ncreate_app({}, 'notes.db')\n")],
    },
    # a server is started at import (start_serving=False: it listens, then returns, so the other seven tests are not hung)
    "wa-serve": {
        "red": "test_importing_the_module_has_no_side_effects",
        "edits": [("    return app\n", "    return app\n\n\nimport asyncio\n"
                   "asyncio.run(create_app({}, ':memory:').start_server(host='127.0.0.1', port=0, start_serving=False))\n")],
    },
    # a token that is a prefix of a real one is accepted
    "wa-prefix": {
        "red": "test_missing_unknown_or_near_miss_token_gets_401_on_every_endpoint",
        "edits": [("        return tokens.get(token)\n",
                   "        return next((u for t, u in tokens.items() if t.startswith(token)), None)\n")],
    },
}


def apply(source: str, name: str) -> str:
    """The reference source with fixture `name` applied. Each `old` must occur exactly once."""
    for old, new in WRONG_APPS[name]["edits"]:
        if source.count(old) != 1:
            raise ValueError(f"{name}: expected one occurrence of {old!r}, found {source.count(old)}")
        source = source.replace(old, new)
    return source
