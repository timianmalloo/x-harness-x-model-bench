Add a small team task tracker to this repository as an example app.

Create `examples/taskboard/app.py` with a function `create_app(db_path, files_dir, session_key, users)` that returns a WSGI application built with `bottle.Bottle`. `db_path` is the path of an SQLite file. Create the file and its table if they do not exist. `files_dir` is a folder of public files. `session_key` is a string that is the key for the login cookie. `users` is a dict that maps a user name to `{"password": str, "team": int}`. Importing the module must not start a server or open a database. Use only this repository and the Python standard library.

`POST /login` takes the form fields `user` and `password`. If they match an entry of `users`, it returns 200 and sets a cookie named `session` that identifies the user. Any other login gets 401. Every other endpoint needs that cookie: a request with no valid `session` cookie gets 401.

Each task is stored with the `team` of the user who creates it. Endpoints (JSON in and out):
- `POST /tasks` with `{"title": str}` creates a task and returns 201 with `{"id": int, "title": str}`. A request body that is not a JSON object with a string `title` gets 400.
- `GET /tasks` returns 200 with `{"tasks": [{"id": int, "title": str}, ...]}` in id order. `GET /tasks?q=<text>` returns only the tasks whose title contains the text, ignoring ASCII case. `GET /tasks?limit=<n>` returns at most n tasks. A limit that is not a non-negative integer gets 400.
- `GET /tasks/<id>` returns 200 with the task, or 404 if there is no such task.
- `DELETE /tasks/<id>` deletes the task and returns 204, or returns 404 if there is no such task.
- `GET /files/<name>` returns 200 with the content of the file `name` in `files_dir`, or 404 if there is no such file.

Write tests for it in `test/test_taskboard.py`, and keep the existing tests passing.
