"""Task tracker for teams (reference solution of S2)."""

import sqlite3

import bottle


def create_app(db_path, files_dir, session_key, users):
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, team INTEGER NOT NULL, "
               "title TEXT NOT NULL)")
    db.commit()
    app = bottle.Bottle()

    def need_team():
        name = bottle.request.get_cookie('session', secret=session_key)
        if not isinstance(name, str) or name not in users:
            bottle.abort(401, 'login required')
        return users[name]['team']

    def row(r):
        return {'id': r[0], 'title': r[1]}

    def task_id(raw):
        return int(raw) if raw.isascii() and raw.isdigit() and len(raw) < 19 else None

    @app.post('/login')
    def login():
        name, password = bottle.request.forms.get('user'), bottle.request.forms.get('password')
        entry = users.get(name)
        if entry is None or entry['password'] != password:
            bottle.response.status = 401
            return 'login failed'
        bottle.response.set_cookie('session', name, secret=session_key, path='/')
        return 'ok'

    @app.post('/tasks')
    def create():
        team = need_team()
        data = bottle.request.json
        if not isinstance(data, dict) or not isinstance(data.get('title'), str):
            bottle.abort(400, 'title is required')
        cur = db.execute('INSERT INTO tasks (team, title) VALUES (?, ?)', (team, data['title']))
        db.commit()
        bottle.response.status = 201
        return {'id': cur.lastrowid, 'title': data['title']}

    @app.get('/tasks')
    def listing():
        team = need_team()
        q = bottle.request.query.getunicode('q', '')
        limit = bottle.request.query.getunicode('limit')
        if limit is not None and not (limit.isascii() and limit.isdigit()):
            bottle.abort(400, 'bad limit')
        like = '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        rows = db.execute("SELECT id, title FROM tasks WHERE team = ? AND title LIKE ? ESCAPE '\\' ORDER BY id LIMIT ?",
                          (team, like, -1 if limit is None else min(int(limit), 2 ** 62))).fetchall()
        return {'tasks': [row(r) for r in rows]}

    @app.get('/tasks/<raw>')
    def fetch(raw):
        team = need_team()
        tid = task_id(raw)
        r = None if tid is None else db.execute('SELECT id, title FROM tasks WHERE id = ? AND team = ?', (tid, team)).fetchone()
        if r is None:
            bottle.abort(404, 'not found')
        return row(r)

    @app.delete('/tasks/<raw>')
    def remove(raw):
        team = need_team()
        tid = task_id(raw)
        cur = None if tid is None else db.execute('DELETE FROM tasks WHERE id = ? AND team = ?', (tid, team))
        if cur is None or cur.rowcount == 0:
            bottle.abort(404, 'not found')
        db.commit()
        bottle.response.status = 204
        return ''

    @app.get('/files/<name:path>')
    def files(name):
        need_team()
        return bottle.static_file(name, root=files_dir)

    return app
