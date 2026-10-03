Add a small notes service to this repository as an example app.

Create `examples/notes/app.py` with a function `create_app(tokens, db_path)` that returns a WSGI application built with `microdot.wsgi.Microdot`. `tokens` is a dict that maps a bearer token string to a user name. `db_path` is the path of an SQLite file. Create the file and its table if they do not exist. Importing the module must not start a server or open a database. Use only this repository and the Python standard library.

Requests carry `Authorization: Bearer <token>`. A request with no token, or with a token that is not in `tokens`, gets status 401. See `examples/auth/token_auth.py` for how this repository handles bearer tokens.

Endpoints (JSON in and out):
- `POST /notes` with `{"title": str, "body": str}` creates a note and returns 201 with `{"id": int, "title": str, "body": str}`. A request body that is not a JSON object with those two string fields gets 400.
- `GET /notes` returns 200 with `{"notes": [{"id": int, "title": str, "body": str}, ...]}` in id order. `GET /notes?q=<text>` returns only the notes whose title or body contains the text, ignoring ASCII case.
- `GET /notes/<id>` returns 200 with the note, or 404 if there is no such note.
- `DELETE /notes/<id>` deletes the note and returns 204, or returns 404 if there is no such note.

Write tests for it in `tests/test_notes.py`, and keep the existing tests passing.
