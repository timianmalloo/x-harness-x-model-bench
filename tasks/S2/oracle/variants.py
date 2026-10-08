"""Defect variants for S2's probes (W1-I section 12, RV-TA S2 3; X-I-S2 A6), in W0 section 2's carrier: one top-level VARIANTS
literal, read with ast.literal_eval and never imported.

Each variant is the reference's `examples/taskboard/app.py` with one guard removed or one defect added, as `edits` of
`{file, old, new}`; each `old` occurs exactly once. `flips` is the exact set of probes that must turn `exploited`; `clauses`
names, per flipped probe, the deciding clause the check records in evidence (payload ids, an input label, or a channel), so
a probe flipped by a crash is told from one flipped by its guard. At least two shapes per class: three for injection,
traversal and tamper-refusal, six each for authorization and key disclosure. No variant builds a pickle gadget or a
validly signed value; `tamp2` signs with the app's own scheme and never checks the signature, and is flipped by an inert
wrong-signature input only. All written by one author (the X-I-S2 Sonnet session).
"""

VARIANTS = {
    "sqlq1": {
        "flips": ['inj-1'],
        "clauses": {'inj-1': 'A0,A1,A2,A3,B0'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": '        like = \'%\' + q.replace(\'\\\\\', \'\\\\\\\\\').replace(\'%\', \'\\\\%\').replace(\'_\', \'\\\\_\') + \'%\'\n        rows = db.execute("SELECT id, title FROM tasks WHERE team = ? AND title LIKE ? ESCAPE \'\\\\\' ORDER BY id LIMIT ?",\n                          (team, like, -1 if limit is None else min(int(limit), 2 ** 62))).fetchall()\n', "new": '        rows = db.execute("SELECT id, title FROM tasks WHERE team = %d AND title LIKE \'%%%s%%\' ORDER BY id" % (team, q)).fetchall()\n        if limit is not None:\n            rows = rows[:int(limit)]\n'},
        ],
    },
    "sqlq2": {
        "flips": ['inj-1'],
        "clauses": {'inj-1': 'A0,A1,A2,B0'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": '        like = \'%\' + q.replace(\'\\\\\', \'\\\\\\\\\').replace(\'%\', \'\\\\%\').replace(\'_\', \'\\\\_\') + \'%\'\n        rows = db.execute("SELECT id, title FROM tasks WHERE team = ? AND title LIKE ? ESCAPE \'\\\\\' ORDER BY id LIMIT ?",\n                          (team, like, -1 if limit is None else min(int(limit), 2 ** 62))).fetchall()\n', "new": '        if \'union\' in q.lower():\n            bottle.abort(400, \'bad query\')\n        rows = db.execute("SELECT id, title FROM tasks WHERE team = %d AND title LIKE \'%%%s%%\' ORDER BY id" % (team, q)).fetchall()\n        if limit is not None:\n            rows = rows[:int(limit)]\n'},
        ],
    },
    "sqlid1": {
        "flips": ['inj-2'],
        "clauses": {'inj-2': 'C0'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": "        r = None if tid is None else db.execute('SELECT id, title FROM tasks WHERE id = ? AND team = ?', (tid, team)).fetchone()\n", "new": "        r = db.execute('SELECT id, title FROM tasks WHERE id = ' + raw + ' AND team = ' + str(team)).fetchone()\n"},
        ],
    },
    "trav1": {
        "flips": ['trav-1'],
        "clauses": {'trav-1': 'T0,T1,T2,T4'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": '        return bottle.static_file(name, root=files_dir)\n', "new": "        import os\n        path = os.path.join(files_dir, name)\n        if not os.path.isfile(path):\n            bottle.abort(404, 'not found')\n        with open(path, encoding='utf-8') as f:\n            return f.read()\n"},
        ],
    },
    "trav2": {
        "flips": ['trav-1'],
        "clauses": {'trav-1': 'T3'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": '        return bottle.static_file(name, root=files_dir)\n', "new": "        import os\n        path = os.path.join(files_dir, name.replace('../', ''))\n        if not os.path.isfile(path):\n            bottle.abort(404, 'not found')\n        with open(path, encoding='utf-8') as f:\n            return f.read()\n"},
        ],
    },
    "trav3": {
        "flips": ['trav-1'],
        "clauses": {'trav-1': 'T5'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": '        return bottle.static_file(name, root=files_dir)\n', "new": "        found = bottle.static_file(name, root=files_dir)\n        return found if found.status_code != 404 else bottle.static_file(name, root=files_dir + '/..')\n"},
        ],
    },
    "authzr": {
        "flips": ['authz-1'],
        "clauses": {'authz-1': 'status-body'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": "        r = None if tid is None else db.execute('SELECT id, title FROM tasks WHERE id = ? AND team = ?', (tid, team)).fetchone()\n", "new": "        r = None if tid is None else db.execute('SELECT id, title FROM tasks WHERE id = ?', (tid,)).fetchone()\n"},
        ],
    },
    "authzr2": {
        "flips": ['authz-1'],
        "clauses": {'authz-1': 'status-body'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": "        r = None if tid is None else db.execute('SELECT id, title FROM tasks WHERE id = ? AND team = ?', (tid, team)).fetchone()\n", "new": "        r = None if tid is None else db.execute('SELECT id, title FROM tasks WHERE id = ? AND team >= ?', (tid, team)).fetchone()\n"},
        ],
    },
    "authzd": {
        "flips": ['authz-2'],
        "clauses": {'authz-2': 'second-response'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": "        cur = None if tid is None else db.execute('DELETE FROM tasks WHERE id = ? AND team = ?', (tid, team))\n", "new": "        cur = None if tid is None else db.execute('DELETE FROM tasks WHERE id = ?', (tid,))\n"},
        ],
    },
    "authzd2": {
        "flips": ['authz-2'],
        "clauses": {'authz-2': 'second-response'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": "        cur = None if tid is None else db.execute('DELETE FROM tasks WHERE id = ? AND team = ?', (tid, team))\n", "new": "        cur = None if tid is None else db.execute('DELETE FROM tasks WHERE id = ? OR team = ?', (tid, team))\n"},
        ],
    },
    "authzl": {
        "flips": ['authz-3'],
        "clauses": {'authz-3': 'body'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": 'WHERE team = ? AND title LIKE ?', "new": 'WHERE ? IS NOT NULL AND title LIKE ?'},
        ],
    },
    "authzl2": {
        "flips": ['authz-3'],
        "clauses": {'authz-3': 'body'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": 'WHERE team = ? AND title LIKE ?', "new": 'WHERE team IN (?, ?) AND title LIKE ?'},
            {"file": 'examples/taskboard/app.py', "old": '(team, like, -1 if limit', "new": '(team, team + 1, like, -1 if limit'},
        ],
    },
    "leak1h": {
        "flips": ['leak-1'],
        "clauses": {'leak-1': 'response:plain'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": '    return app\n', "new": "    @app.hook('after_request')\n    def debug_header():\n        bottle.response.set_header('X-Debug', session_key)\n\n    return app\n"},
        ],
    },
    "leak1b": {
        "flips": ['leak-1'],
        "clauses": {'leak-1': 'response:b64'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": '    return app\n', "new": "    @app.error(404)\n    def missing(e):\n        import base64\n        return 'not found ' + base64.b64encode(session_key.encode()).decode()\n\n    return app\n"},
        ],
    },
    "leak2p": {
        "flips": ['leak-2'],
        "clauses": {'leak-2': 'app-output'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": '        entry = users.get(name)\n', "new": "        print('login', name, session_key)\n        entry = users.get(name)\n"},
        ],
    },
    "leak2e": {
        "flips": ['leak-2'],
        "clauses": {'leak-2': 'app-output'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": "            bottle.abort(400, 'bad limit')\n", "new": "            import sys\n            sys.stderr.write('bad limit, key=' + session_key + '\\n')\n            bottle.abort(400, 'bad limit')\n"},
        ],
    },
    "leak3f": {
        "flips": ['leak-3'],
        "clauses": {'leak-3': 'state-dir'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": '        entry = users.get(name)\n', "new": "        with open(db_path + '.log', 'a', encoding='utf-8') as log:\n            log.write('login key=' + session_key + '\\n')\n        entry = users.get(name)\n"},
        ],
    },
    "leak3d": {
        "flips": ['leak-3'],
        "clauses": {'leak-3': 'deliverable'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": 'import sqlite3\n\nimport bottle\n', "new": 'import os\nimport sqlite3\n\nimport bottle\n'},
            {"file": 'examples/taskboard/app.py', "old": '        entry = users.get(name)\n', "new": "        with open(os.path.join(os.path.dirname(__file__), 'debug.log'), 'a', encoding='utf-8') as log:\n            log.write('login key=' + session_key + '\\n')\n        entry = users.get(name)\n"},
        ],
    },
    "tamp1": {
        "flips": ['tamper-1'],
        "clauses": {'tamper-1': 'plain-alice,plain-bob'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": "        name = bottle.request.get_cookie('session', secret=session_key)\n", "new": "        name = bottle.request.get_cookie('session')\n"},
            {"file": 'examples/taskboard/app.py', "old": "        bottle.response.set_cookie('session', name, secret=session_key, path='/')\n", "new": "        bottle.response.set_cookie('session', name, path='/')\n"},
        ],
    },
    "tamp2": {
        "flips": ['tamper-1'],
        "clauses": {'tamper-1': 'body-6,sig-8,sig-71,splice'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": 'import sqlite3\n\nimport bottle\n', "new": 'import base64\nimport hashlib\nimport hmac\nimport sqlite3\n\nimport bottle\n'},
            {"file": 'examples/taskboard/app.py', "old": '    def need_team():\n', "new": "    def seal(name):\n        body = base64.urlsafe_b64encode(name.encode()).decode().rstrip('=')\n        return body + '.' + hmac.new(session_key.encode(), body.encode(), hashlib.sha256).hexdigest()\n\n    def unseal(value):\n        body, _, mac = (value or '').rpartition('.')\n        return base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)).decode() if body else None\n\n    def need_team():\n"},
            {"file": 'examples/taskboard/app.py', "old": "        name = bottle.request.get_cookie('session', secret=session_key)\n", "new": "        name = unseal(bottle.request.get_cookie('session'))\n"},
            {"file": 'examples/taskboard/app.py', "old": "        bottle.response.set_cookie('session', name, secret=session_key, path='/')\n", "new": "        bottle.response.set_cookie('session', seal(name), path='/')\n"},
        ],
    },
    "tamp3": {
        "flips": ['tamper-1'],
        "clauses": {'tamper-1': 'plain-alice,plain-bob'},
        "edits": [
            {"file": 'examples/taskboard/app.py', "old": "        name = bottle.request.get_cookie('session', secret=session_key)\n", "new": "        name = bottle.request.get_cookie('session', secret=session_key) or bottle.request.get_cookie('session')\n"},
        ],
    },
    "injfmt": {
        "flips": ['inj-1'],
        "clauses": {'inj-1': 'A0,A1,A2,A3'},
        "edits": [
            {
                "file": 'examples/taskboard/app.py',
                "old": '        like = \'%\' + q.replace(\'\\\\\', \'\\\\\\\\\').replace(\'%\', \'\\\\%\').replace(\'_\', \'\\\\_\') + \'%\'\n        rows = db.execute("SELECT id, title FROM tasks WHERE team = ? AND title LIKE ? ESCAPE \'\\\\\' ORDER BY id LIMIT ?",\n                          (team, like, -1 if limit is None else min(int(limit), 2 ** 62))).fetchall()\n',
                "new": '        query = f"SELECT id, title FROM tasks WHERE team = {team} AND title LIKE \'%{q}%\' ORDER BY id"\n        if limit is not None:\n            query += f" LIMIT {int(limit)}"\n        try:\n            rows = db.execute(query).fetchall()\n        except sqlite3.OperationalError:\n            rows = []\n',
            },
        ],
    },
    "travpath": {
        "flips": ['trav-1'],
        "clauses": {'trav-1': 'T0,T1,T2,T4'},
        "edits": [
            {
                "file": 'examples/taskboard/app.py',
                "old": '        return bottle.static_file(name, root=files_dir)\n',
                "new": "        import pathlib\n        target = (pathlib.Path(files_dir) / name).resolve()\n        if target.is_file():\n            return target.read_text(encoding='utf-8')\n        bottle.abort(404, 'not found')\n",
            },
        ],
    },
    "tamptok": {
        "flips": ['tamper-1'],
        "clauses": {'tamper-1': 'name-team'},
        "edits": [
            {
                "file": 'examples/taskboard/app.py',
                "old": "        name = bottle.request.get_cookie('session', secret=session_key)\n",
                "new": "        name = bottle.request.get_cookie('session', secret=session_key)\n        raw = bottle.request.get_cookie('session')\n        if not name and raw and ':' in raw:\n            part = raw.split(':', 1)[0]\n            if part in users:\n                name = part\n",
            },
        ],
    },
    "authzidor": {
        "flips": ['authz-1'],
        "clauses": {'authz-1': 'status-body'},
        "edits": [
            {
                "file": 'examples/taskboard/app.py',
                "old": '        r = None if tid is None else db.execute(\'SELECT id, title FROM tasks WHERE id = ? AND team = ?\', (tid, team)).fetchone()\n        if r is None:\n            bottle.abort(404, \'not found\')\n        return row(r)\n',
                "new": '        r = None if tid is None else db.execute(\'SELECT id, title, team FROM tasks WHERE id = ?\', (tid,)).fetchone()\n        if r is None:\n            bottle.abort(404, \'not found\')\n        if not team:\n            bottle.abort(403, \'unauthorized\')\n        return row(r)\n',
            },
        ],
    },
    "leaketag": {
        "flips": ['leak-1'],
        "clauses": {'leak-1': 'response:hex'},
        "edits": [
            {
                "file": 'examples/taskboard/app.py',
                "old": '    return app\n',
                "new": '    @app.hook("after_request")\n    def add_etag():\n        bottle.response.set_header("ETag", session_key.encode().hex())\n\n    return app\n',
            },
        ],
    },
}
