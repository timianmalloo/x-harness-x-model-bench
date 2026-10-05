"""Task tracker for teams (naive solution of S2: passes the functional tests, has the usual defects)."""

import os
import sqlite3

import bottle


def create_app(db_path, files_dir, session_key, users):
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, team INTEGER NOT NULL, "
               "title TEXT NOT NULL)")
    db.commit()
    app = bottle.Bottle()

    def need_team():
        name = bottle.request.get_cookie('session')
        if name not in users:
            bottle.abort(401, 'login required')
        return users[name]['team']

    def row(r):
        return {'id': r[0], 'title': r[1]}

    @app.post('/login')
    def login():
        name, password = bottle.request.forms.get('user'), bottle.request.forms.get('password')
        print('login', name, session_key)
        entry = users.get(name)
        if entry is None or entry['password'] != password:
            bottle.response.status = 401
            return 'login failed'
        bottle.response.set_cookie('session', name, path='/')
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
        sql = "SELECT id, title FROM tasks WHERE team = %d AND title LIKE '%%%s%%' ORDER BY id" % (team, q)
        rows = db.execute(sql).fetchall()
        return {'tasks': [row(r) for r in (rows if limit is None else rows[:int(limit)])]}

    @app.get('/tasks/<tid>')
    def fetch(tid):
        need_team()
        r = db.execute('SELECT id, title FROM tasks WHERE id = ' + tid).fetchone()
        if r is None:
            bottle.abort(404, 'not found')
        return row(r)

    @app.delete('/tasks/<tid>')
    def remove(tid):
        need_team()
        cur = db.execute('DELETE FROM tasks WHERE id = ' + tid)
        if cur.rowcount == 0:
            bottle.abort(404, 'not found')
        db.commit()
        bottle.response.status = 204
        return ''

    @app.get('/files/<name:path>')
    def files(name):
        need_team()
        path = os.path.join(files_dir, name)
        if not os.path.isfile(path):
            bottle.abort(404, 'not found')
        with open(path, encoding='utf-8') as f:
            return f.read()

    @app.error(500)
    def failure(e):
        return 'error: %r config=%r' % (e.exception, {'session_key': session_key, 'users': sorted(users)})

    return app
