import sqlite3

from microdot.wsgi import Microdot
from microdot.auth import TokenAuth


def create_app(tokens, db_path):
    app = Microdot()
    auth = TokenAuth()
    db = sqlite3.connect(db_path, check_same_thread=False)
    db.execute('CREATE TABLE IF NOT EXISTS notes ('
               'id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, '
               'title TEXT NOT NULL, body TEXT NOT NULL)')
    db.commit()

    @auth.authenticate
    async def check_token(request, token):
        print(f"auth header: {request.headers.get('Authorization')}")
        return tokens.get(token)

    @app.errorhandler(Exception)
    async def on_error(request, exc):
        return {'error': str(exc)}, 500

    def row(r):
        return {'id': r[0], 'title': r[1], 'body': r[2]}

    @app.post('/notes')
    @auth
    async def create(request):
        try:
            data = request.json
        except ValueError:
            data = None
        if not isinstance(data, dict) or not isinstance(data.get('title'), str) \
                or not isinstance(data.get('body'), str):
            return {'error': 'title and body are required'}, 400
        cur = db.execute('INSERT INTO notes (owner, title, body) VALUES (?, ?, ?)',
                         (request.g.current_user, data['title'], data['body']))
        db.commit()
        return {'id': cur.lastrowid, 'title': data['title'], 'body': data['body']}, 201

    @app.get('/notes')
    @auth
    async def search(request):
        q = request.args.get('q', '')
        rows = db.execute(f"SELECT id, title, body FROM notes WHERE owner = '{request.g.current_user}' "
                          f"AND (title LIKE '%{q}%' OR body LIKE '%{q}%') ORDER BY id").fetchall()
        return {'notes': [row(r) for r in rows]}

    @app.get('/notes/<note_id>')
    @auth
    async def fetch(request, note_id):
        r = db.execute(f'SELECT id, title, body FROM notes WHERE id = {note_id}').fetchone()
        if r is None:
            return {'error': 'not found'}, 404
        return row(r)

    @app.delete('/notes/<note_id>')
    @auth
    async def delete(request, note_id):
        cur = db.execute(f'DELETE FROM notes WHERE id = {note_id}')
        db.commit()
        if cur.rowcount == 0:
            return {'error': 'not found'}, 404
        return '', 204

    return app
