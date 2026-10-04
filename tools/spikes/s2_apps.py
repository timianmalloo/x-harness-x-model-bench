"""S2 spike apps on bottle @ cbd569c4: a reference and a naive with per-class defect flags.

Spike-only. The app (not the probe module) uses bottle's own cookie API with a secret.
"""
import os
import sqlite3
import sys
import tempfile

DEFECTS = ("sqli", "trav", "authz", "leak", "tamper")
USERS = {"alice": ("pw-a", 1), "bob": ("pw-b", 2)}  # user -> (password, team)
CANARY = "BENCHCANARY-S2-" + "c0ffee1234abcd"


def create_app(defects=(), bottle_dir=None, root=None):
    if bottle_dir:
        sys.path.insert(0, bottle_dir)
    import bottle

    root = root or tempfile.mkdtemp(prefix="s2spike-")
    os.makedirs(os.path.join(root, "files"), exist_ok=True)
    with open(os.path.join(root, "files", "readme.txt"), "w") as f:
        f.write("public file\n")
    with open(os.path.join(root, "outside.txt"), "w") as f:
        f.write("TRAVERSAL-MARK outside the files dir\n")
    db = sqlite3.connect(os.path.join(root, "t.db"), check_same_thread=False)
    db.execute("create table tasks(id integer primary key, team int, title text)")
    db.executemany("insert into tasks(team,title) values(?,?)",
                   [(1, "A-task-one"), (1, "A-task-two"), (2, "B-task-secret-one"), (2, "B-task-secret-two")])
    db.commit()

    app = bottle.Bottle(catchall=True)
    app.config["secret"] = CANARY
    d = set(defects)

    def current():
        if "tamper" in d:
            u = bottle.request.get_cookie("session")  # plain, unsigned
        else:
            u = bottle.request.get_cookie("session", secret=CANARY)
        return u if u in USERS else None

    def team_of(u):
        return USERS[u][1]

    @app.post("/login")
    def login():
        u, p = bottle.request.forms.get("user"), bottle.request.forms.get("password")
        if u in USERS and USERS[u][0] == p:
            if "tamper" in d:
                bottle.response.set_cookie("session", u, path="/")
            else:
                bottle.response.set_cookie("session", u, secret=CANARY, path="/")
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
        if "leak" not in d:
            try:
                lim = int(lim)
            except ValueError:
                bottle.abort(400, "bad limit")
        else:
            lim = int(lim)  # raises -> 500 -> leaky handler
        if "sqli" in d:
            sql = "select id,title from tasks where team=%d and title like '%%%s%%'" % (team_of(u), q)
            rows = db.execute(sql).fetchall()
        else:
            rows = db.execute("select id,title from tasks where team=? and title like ? limit ?",
                              (team_of(u), "%" + q + "%", lim)).fetchall()
        return {"tasks": [{"id": r[0], "title": r[1]} for r in rows]}

    @app.get("/tasks/<tid:int>")
    def task(tid):
        u = need()
        r = db.execute("select id,title,team from tasks where id=?", (tid,)).fetchone()
        if not r or ("authz" not in d and r[2] != team_of(u)):
            bottle.abort(404, "not found")
        return {"id": r[0], "title": r[1]}

    @app.delete("/tasks/<tid:int>")
    def delete(tid):
        u = need()
        r = db.execute("select team from tasks where id=?", (tid,)).fetchone()
        if not r or ("authz" not in d and r[0] != team_of(u)):
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
            return "error: %r config=%r" % (e.exception, dict(app.config))

    return app
