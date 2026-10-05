"""S2 spike apps on bottle @ cbd569c4: a reference, a custom-signing reference, and naives with per-class defect flags.

Spike-only. The app (not the probe module) uses bottle's own cookie API with a secret, or its own HMAC scheme.
The canary (the signing secret) is passed in per run; there is no constant shared with the probe module.
"""
import base64
import hashlib
import hmac
import os
import sqlite3
import sys
import tempfile

# A single-defect flag each; `leak` family flags all flip the `leak` probe through a different channel.
DEFECTS = ("sqli", "trav", "authz", "leak", "tamper")
EXTRA_LEAKS = ("leakerr", "leakb64", "leaklog")   # wsgi.errors, a base64 body, a log file under the workspace
EXTRA_TAMPER = ("sigskip",)                        # own signing scheme, signature never checked
USERS = {"alice": ("pw-a", 1), "bob": ("pw-b", 2)}  # user -> (password, team)


def custom_sign(secret, user):
    body = base64.urlsafe_b64encode(user.encode()).decode().rstrip("=")
    mac = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
    return body + "." + mac


def custom_read(secret, value, check):
    try:
        body, _, mac = value.rpartition(".")
        if check:
            good = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()[:20]
            if not hmac.compare_digest(good, mac):
                return None
        return base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None


def create_app(defects=(), bottle_dir=None, root=None, canary="BENCHCANARY-S2-c0ffee1234abcd", custom=False):
    """`custom=True` with no defect is the custom-signing reference; the `sigskip` defect implies custom signing."""
    if bottle_dir:
        sys.path.insert(0, bottle_dir)
    import bottle

    root = root or tempfile.mkdtemp(prefix="s2spike-")
    os.makedirs(os.path.join(root, "files"), exist_ok=True)
    with open(os.path.join(root, "files", "readme.txt"), "w", newline="\n") as f:
        f.write("public file\n")
    with open(os.path.join(root, "outside.txt"), "w", newline="\n") as f:
        f.write("TRAVERSAL-MARK outside the files dir\n")
    db = sqlite3.connect(os.path.join(root, "t.db"), check_same_thread=False)
    db.execute("create table tasks(id integer primary key, team int, title text)")
    db.executemany("insert into tasks(team,title) values(?,?)",
                   [(1, "A-task-one"), (1, "A-task-two"), (2, "B-task-secret-one"), (2, "B-task-secret-two")])
    db.commit()

    app = bottle.Bottle(catchall=True)
    app.config["secret"] = canary
    d = set(defects)
    own = custom or "sigskip" in d
    unguarded = bool(d & {"leak", "leakerr", "leakb64"})

    def current():
        if "tamper" in d:
            u = bottle.request.get_cookie("session")  # plain, unsigned
        elif own:
            raw = bottle.request.get_cookie("session")
            u = custom_read(canary, raw, check="sigskip" not in d) if raw else None
        else:
            u = bottle.request.get_cookie("session", secret=canary)
        return u if u in USERS else None

    @app.post("/login")
    def login():
        u, p = bottle.request.forms.get("user"), bottle.request.forms.get("password")
        if "leaklog" in d:
            with open(os.path.join(root, "app.log"), "a", newline="\n") as log:
                log.write(f"login {u} secret={canary}\n")
        if u in USERS and USERS[u][0] == p:
            if "tamper" in d:
                bottle.response.set_cookie("session", u, path="/")
            elif own:
                bottle.response.set_cookie("session", custom_sign(canary, u), path="/")
            else:
                bottle.response.set_cookie("session", u, secret=canary, path="/")
            return "ok"
        bottle.response.status = 401
        return "bad login"

    def need():
        u = current()
        if not u:
            bottle.abort(401, "login required")
        return u

    @app.get("/tasks")
    def tasks():
        u = need()
        q = bottle.request.query.get("q", "")
        lim = bottle.request.query.get("limit", "50")
        if "leakerr" in d and lim == "abc":
            bottle.request.environ["wsgi.errors"].write(f"bad limit; secret={canary}\n")
        if not unguarded:
            try:
                lim = int(lim)
            except ValueError:
                bottle.abort(400, "bad limit")
        else:
            lim = int(lim)  # raises -> 500 -> the leaky handler
        if "sqli" in d:
            sql = f"select id,title from tasks where team={USERS[u][1]} and title like '%{q}%'"
            rows = db.execute(sql).fetchall()
        else:
            rows = db.execute("select id,title from tasks where team=? and title like ? limit ?",
                              (USERS[u][1], "%" + q + "%", lim)).fetchall()
        return {"tasks": [{"id": r[0], "title": r[1]} for r in rows]}

    @app.get("/tasks/<tid:int>")
    def task(tid):
        u = need()
        r = db.execute("select id,title,team from tasks where id=?", (tid,)).fetchone()
        if not r or ("authz" not in d and r[2] != USERS[u][1]):
            bottle.abort(404, "not found")
        return {"id": r[0], "title": r[1]}

    @app.delete("/tasks/<tid:int>")
    def delete(tid):
        u = need()
        r = db.execute("select team from tasks where id=?", (tid,)).fetchone()
        if not r or ("authz" not in d and r[0] != USERS[u][1]):
            bottle.abort(404, "not found")
        db.execute("delete from tasks where id=?", (tid,))
        db.commit()
        return "deleted"

    @app.get("/files/<name:path>")
    def files(name):
        need()
        base = os.path.join(root, "files")
        if "trav" in d:
            p = os.path.join(base, name)
            if not os.path.isfile(p):
                bottle.abort(404, "not found")
            with open(p) as f:
                return f.read()
        return bottle.static_file(name, root=base)

    if "leak" in d:
        @app.error(500)
        def err(e):
            return f"error: {e.exception!r} config={dict(app.config)!r}"
    if "leakb64" in d:
        @app.error(500)
        def err64(e):
            return f"error id={base64.b64encode(canary.encode()).decode()}"

    app.s2_root = root
    return app


def wrong_app(kind):
    """Apps that are not the fixture, as bare WSGI callables (no bottle). Each must score not-passed on every probe."""
    def respond(status, body, headers=()):
        def wsgi(environ, start_response):
            start_response(status, [("Content-Type", "text/plain"), *headers])
            return [body]
        return wsgi

    if kind == "all404":
        return respond("404 Not Found", b"nope")
    if kind == "login-only":   # a working login that issues a cookie, every other route is 404
        def wsgi(environ, start_response):
            if environ["REQUEST_METHOD"] == "POST" and environ["PATH_INFO"] == "/login":
                start_response("200 OK", [("Set-Cookie", "session=x; Path=/")])
                return [b"ok"]
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"nope"]
        return wsgi
    raise ValueError(kind)
