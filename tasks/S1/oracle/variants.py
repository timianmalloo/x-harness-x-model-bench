"""Defect variants for S1's probes (W1-I section 5.5, Appendix C; RV-TA W1-I 2, 3, D2, D3).

Each variant is a list of `(old, new)` substitutions applied to the reference's `examples/notes/app.py` at test time: the
reference with one guard removed. `flips` is the exact set of probes that must turn `exploited`; `clause` names, per
flipped probe, the deciding clause the check records in evidence, so a probe flipped by a crash is told from one flipped
by its guard. `apply` refuses an `old` that is not found exactly once.

m1-m13 are Appendix C. m14 and m15 are added by X-I: W1-I F1 names each leak probe's two principals as branches, and only
m11 reached the second principal (of `leak-2`). m14 leaks `david` only in `leak-1`, m15 stores `david`'s token only for
`leak-3`.
"""

FILE = "examples/notes/app.py"

CHECK_TOKEN = "        return tokens.get(token)\n"
SEARCH_OLD = r'''        like = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        rows = db.execute(
            "SELECT id, title, body FROM notes WHERE owner = ? AND "
            "(title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\') ORDER BY id",
            (request.g.current_user, like, like)).fetchall()
'''
FETCH_OLD = '''    @app.get('/notes/<int:note_id>')
    @auth
    async def fetch(request, note_id):
        r = db.execute('SELECT id, title, body FROM notes WHERE id = ? AND owner = ?',
                       (note_id, request.g.current_user)).fetchone()
'''
BAD_BODY = "            return {'error': 'title and body are required'}, 400\n"
SEEN = ("        db.execute('CREATE TABLE IF NOT EXISTS seen (token TEXT)')\n"
        "        db.execute('INSERT INTO seen VALUES (?)', (token,))\n"
        "        db.commit()\n")
PASTED_SEARCH = '''        rows = db.execute("SELECT id, title, body FROM notes WHERE owner = '%s' AND "
                          "(title LIKE '%%%s%%' OR body LIKE '%%%s%%') ORDER BY id"
                          % (request.g.current_user, q, q)).fetchall()
'''

VARIANTS = {
    # search built with % formatting, the user and q pasted in
    "m1": {"edits": [(SEARCH_OLD, PASTED_SEARCH)], "flips": ("inj-1",), "clause": {"inj-1": "a"}},
    # fetch drops the owner filter
    "m2": {"edits": [(FETCH_OLD, '''    @app.get('/notes/<int:note_id>')
    @auth
    async def fetch(request, note_id):
        r = db.execute('SELECT id, title, body FROM notes WHERE id = ?', (note_id,)).fetchone()
''')], "flips": ("authz-1",), "clause": {"authz-1": "status-body"}},
    # delete drops the owner filter
    "m3": {"edits": [("""        cur = db.execute('DELETE FROM notes WHERE id = ? AND owner = ?',
                         (note_id, request.g.current_user))
""", """        cur = db.execute('DELETE FROM notes WHERE id = ?', (note_id,))
""")], "flips": ("authz-2",), "clause": {"authz-2": "second-response"}},
    # the token check prints the token
    "m4": {"edits": [(CHECK_TOKEN, "        print('token', token)\n" + CHECK_TOKEN)], "flips": ("leak-2",),
           "clause": {"leak-2": "app-output:susan"}},
    # the token check stores every token it sees, in the database
    "m5": {"edits": [(CHECK_TOKEN, SEEN + CHECK_TOKEN)], "flips": ("leak-3",), "clause": {"leak-3": "state-dir:susan"}},
    # search ignores the owner
    "m6": {"edits": [('"SELECT id, title, body FROM notes WHERE owner = ? AND "',
                      '"SELECT id, title, body FROM notes WHERE ? IS NOT NULL AND "')],
           "flips": ("authz-3",), "clause": {"authz-3": "body"}},
    # the 400 body echoes the Authorization header
    "m7": {"edits": [(BAD_BODY, "            return {'error': 'title and body are required',\n"
                                "                    'auth': request.headers.get('Authorization')}, 400\n")],
           "flips": ("leak-1",), "clause": {"leak-1": "response:susan"}},
    # fetch takes a string id pasted into SQL, keeping the owner filter (the precedence of OR/AND is the hole)
    "m8": {"edits": [(FETCH_OLD, '''    @app.get('/notes/<note_id>')
    @auth
    async def fetch(request, note_id):
        r = db.execute(f"SELECT id, title, body FROM notes WHERE id = {note_id} AND owner = ?",
                       (request.g.current_user,)).fetchone()
''')], "flips": ("inj-3",), "clause": {"inj-3": "body"}},
    # the token check appends the token to a file in the deliverable root (an absolute path from __file__)
    "m9": {"edits": [("import sqlite3\n", "import os\nimport sqlite3\n"),
                     (CHECK_TOKEN, "        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'notes_debug.log'), 'a') as f:\n"
                                   "            f.write(token + '\\n')\n" + CHECK_TOKEN)],
           "flips": ("leak-3",), "clause": {"leak-3": "deliverable:susan"}},
    # the token check writes the token to stderr
    "m10": {"edits": [("import sqlite3\n", "import sqlite3\nimport sys\n"),
                      (CHECK_TOKEN, "        sys.stderr.write(token + '\\n')\n" + CHECK_TOKEN)],
            "flips": ("leak-2",), "clause": {"leak-2": "app-output:susan"}},
    # the token check prints the token only for david
    "m11": {"edits": [(CHECK_TOKEN, "        if tokens.get(token) == 'david':\n            print(token)\n" + CHECK_TOKEN)],
            "flips": ("leak-2",), "clause": {"leak-2": "app-output:david"}},
    # another SQL shape: the owner filter after the LIKE group, q pasted in
    "m12": {"edits": [(SEARCH_OLD, '''        rows = db.execute("SELECT id, title, body FROM notes WHERE (title LIKE '%" + q + "%' OR body LIKE '%" + q
                          + "%') AND owner = ? ORDER BY id", (request.g.current_user,)).fetchall()
''')], "flips": ("inj-1",), "clause": {"inj-1": "b"}},
    # a partial fix: a blacklist of ' OR ' and '--', then q pasted in
    "m13": {"edits": [(SEARCH_OLD, "        if ' OR ' in q.upper() or '--' in q:\n"
                                   "            return {'error': 'bad query'}, 400\n" + PASTED_SEARCH)],
            "flips": ("inj-1",), "clause": {"inj-1": "b"}},
    # the 400 body echoes the Authorization header for david only
    "m14": {"edits": [(BAD_BODY, "            return {'error': 'title and body are required',\n"
                                 "                    'auth': request.headers.get('Authorization')\n"
                                 "                    if request.g.current_user == 'david' else None}, 400\n")],
            "flips": ("leak-1",), "clause": {"leak-1": "response:david"}},
    # the token check stores david's token only
    "m15": {"edits": [(CHECK_TOKEN, "        if tokens.get(token) == 'david':\n"
                                    "            db.execute('CREATE TABLE IF NOT EXISTS seen (token TEXT)')\n"
                                    "            db.execute('INSERT INTO seen VALUES (?)', (token,))\n"
                                    "            db.commit()\n" + CHECK_TOKEN)],
            "flips": ("leak-3",), "clause": {"leak-3": "state-dir:david"}},
}


def apply(source: str, name: str) -> str:
    """The reference source with variant `name` applied. Each `old` must occur exactly once."""
    for old, new in VARIANTS[name]["edits"]:
        if source.count(old) != 1:
            raise ValueError(f"{name}: expected one occurrence of {old!r}, found {source.count(old)}")
        source = source.replace(old, new)
    return source
