"""Defect variants for S1's probes (W1-I section 5.5, Appendix C; RV-TA W1-I 2, 3, D2, D3), in W0 section 2's carrier: one
top-level VARIANTS literal, read with ast.literal_eval and never imported.

Each variant is the reference's `examples/notes/app.py` with one guard removed, as `edits` of `{file, old, new}`; each `old` occurs
exactly once. `flips` is the exact set of probes that must turn `exploited`; `clauses` names, per flipped probe, the deciding
clause the check records in evidence, so a probe flipped by a crash is told from one flipped by its guard.

m1-m13 are Appendix C. m14 and m15 are added by X-I: W1-I F1 names each leak probe's two principals as branches, and only
m11 reached the second principal (of `leak-2`). m14 leaks `david` only in `leak-1`, m15 stores `david`'s token only for
`leak-3`.
"""

VARIANTS = {
    "m1": {
        "flips": ['inj-1'],
        "clauses": {'inj-1': 'a'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": '        like = \'%\' + q.replace(\'\\\\\', \'\\\\\\\\\').replace(\'%\', \'\\\\%\').replace(\'_\', \'\\\\_\') + \'%\'\n        rows = db.execute(\n            "SELECT id, title, body FROM notes WHERE owner = ? AND "\n            "(title LIKE ? ESCAPE \'\\\\\' OR body LIKE ? ESCAPE \'\\\\\') ORDER BY id",\n            (request.g.current_user, like, like)).fetchall()\n', "new": '        rows = db.execute("SELECT id, title, body FROM notes WHERE owner = \'%s\' AND "\n                          "(title LIKE \'%%%s%%\' OR body LIKE \'%%%s%%\') ORDER BY id"\n                          % (request.g.current_user, q, q)).fetchall()\n'},
        ],
    },
    "m2": {
        "flips": ['authz-1'],
        "clauses": {'authz-1': 'status-body'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": "    @app.get('/notes/<int:note_id>')\n    @auth\n    async def fetch(request, note_id):\n        r = db.execute('SELECT id, title, body FROM notes WHERE id = ? AND owner = ?',\n                       (note_id, request.g.current_user)).fetchone()\n", "new": "    @app.get('/notes/<int:note_id>')\n    @auth\n    async def fetch(request, note_id):\n        r = db.execute('SELECT id, title, body FROM notes WHERE id = ?', (note_id,)).fetchone()\n"},
        ],
    },
    "m3": {
        "flips": ['authz-2'],
        "clauses": {'authz-2': 'second-response'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": "        cur = db.execute('DELETE FROM notes WHERE id = ? AND owner = ?',\n                         (note_id, request.g.current_user))\n", "new": "        cur = db.execute('DELETE FROM notes WHERE id = ?', (note_id,))\n"},
        ],
    },
    "m4": {
        "flips": ['leak-2'],
        "clauses": {'leak-2': 'app-output:susan'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": '        return tokens.get(token)\n', "new": "        print('token', token)\n        return tokens.get(token)\n"},
        ],
    },
    "m5": {
        "flips": ['leak-3'],
        "clauses": {'leak-3': 'state-dir:susan'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": '        return tokens.get(token)\n', "new": "        db.execute('CREATE TABLE IF NOT EXISTS seen (token TEXT)')\n        db.execute('INSERT INTO seen VALUES (?)', (token,))\n        db.commit()\n        return tokens.get(token)\n"},
        ],
    },
    "m6": {
        "flips": ['authz-3'],
        "clauses": {'authz-3': 'body'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": '"SELECT id, title, body FROM notes WHERE owner = ? AND "', "new": '"SELECT id, title, body FROM notes WHERE ? IS NOT NULL AND "'},
        ],
    },
    "m7": {
        "flips": ['leak-1'],
        "clauses": {'leak-1': 'response:susan'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": "            return {'error': 'title and body are required'}, 400\n", "new": "            return {'error': 'title and body are required',\n                    'auth': request.headers.get('Authorization')}, 400\n"},
        ],
    },
    "m8": {
        "flips": ['inj-3'],
        "clauses": {'inj-3': 'body'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": "    @app.get('/notes/<int:note_id>')\n    @auth\n    async def fetch(request, note_id):\n        r = db.execute('SELECT id, title, body FROM notes WHERE id = ? AND owner = ?',\n                       (note_id, request.g.current_user)).fetchone()\n", "new": '    @app.get(\'/notes/<note_id>\')\n    @auth\n    async def fetch(request, note_id):\n        r = db.execute(f"SELECT id, title, body FROM notes WHERE id = {note_id} AND owner = ?",\n                       (request.g.current_user,)).fetchone()\n'},
        ],
    },
    "m9": {
        "flips": ['leak-3'],
        "clauses": {'leak-3': 'deliverable:susan'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": 'import sqlite3\n', "new": 'import os\nimport sqlite3\n'},
            {"file": 'examples/notes/app.py', "old": '        return tokens.get(token)\n', "new": "        with open(os.path.join(os.path.dirname(__file__), '..', '..', 'notes_debug.log'), 'a') as f:\n            f.write(token + '\\n')\n        return tokens.get(token)\n"},
        ],
    },
    "m10": {
        "flips": ['leak-2'],
        "clauses": {'leak-2': 'app-output:susan'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": 'import sqlite3\n', "new": 'import sqlite3\nimport sys\n'},
            {"file": 'examples/notes/app.py', "old": '        return tokens.get(token)\n', "new": "        sys.stderr.write(token + '\\n')\n        return tokens.get(token)\n"},
        ],
    },
    "m11": {
        "flips": ['leak-2'],
        "clauses": {'leak-2': 'app-output:david'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": '        return tokens.get(token)\n', "new": "        if tokens.get(token) == 'david':\n            print(token)\n        return tokens.get(token)\n"},
        ],
    },
    "m12": {
        "flips": ['inj-1'],
        "clauses": {'inj-1': 'b'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": '        like = \'%\' + q.replace(\'\\\\\', \'\\\\\\\\\').replace(\'%\', \'\\\\%\').replace(\'_\', \'\\\\_\') + \'%\'\n        rows = db.execute(\n            "SELECT id, title, body FROM notes WHERE owner = ? AND "\n            "(title LIKE ? ESCAPE \'\\\\\' OR body LIKE ? ESCAPE \'\\\\\') ORDER BY id",\n            (request.g.current_user, like, like)).fetchall()\n', "new": '        rows = db.execute("SELECT id, title, body FROM notes WHERE (title LIKE \'%" + q + "%\' OR body LIKE \'%" + q\n                          + "%\') AND owner = ? ORDER BY id", (request.g.current_user,)).fetchall()\n'},
        ],
    },
    "m13": {
        "flips": ['inj-1'],
        "clauses": {'inj-1': 'b'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": '        like = \'%\' + q.replace(\'\\\\\', \'\\\\\\\\\').replace(\'%\', \'\\\\%\').replace(\'_\', \'\\\\_\') + \'%\'\n        rows = db.execute(\n            "SELECT id, title, body FROM notes WHERE owner = ? AND "\n            "(title LIKE ? ESCAPE \'\\\\\' OR body LIKE ? ESCAPE \'\\\\\') ORDER BY id",\n            (request.g.current_user, like, like)).fetchall()\n', "new": '        if \' OR \' in q.upper() or \'--\' in q:\n            return {\'error\': \'bad query\'}, 400\n        rows = db.execute("SELECT id, title, body FROM notes WHERE owner = \'%s\' AND "\n                          "(title LIKE \'%%%s%%\' OR body LIKE \'%%%s%%\') ORDER BY id"\n                          % (request.g.current_user, q, q)).fetchall()\n'},
        ],
    },
    "m14": {
        "flips": ['leak-1'],
        "clauses": {'leak-1': 'response:david'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": "            return {'error': 'title and body are required'}, 400\n", "new": "            return {'error': 'title and body are required',\n                    'auth': request.headers.get('Authorization')\n                    if request.g.current_user == 'david' else None}, 400\n"},
        ],
    },
    "m15": {
        "flips": ['leak-3'],
        "clauses": {'leak-3': 'state-dir:david'},
        "edits": [
            {"file": 'examples/notes/app.py', "old": '        return tokens.get(token)\n', "new": "        if tokens.get(token) == 'david':\n            db.execute('CREATE TABLE IF NOT EXISTS seen (token TEXT)')\n            db.execute('INSERT INTO seen VALUES (?)', (token,))\n            db.commit()\n        return tokens.get(token)\n"},
        ],
    },
}
