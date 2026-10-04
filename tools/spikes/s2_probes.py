"""S2 spike probes. Stdlib only; drives a WSGI callable in-process. Never imports bottle or pickle.

Sessions come only from POST /login. Tamper probes send non-signed bytes or a byte-flipped
copy of an app-issued value; they construct nothing.
"""
import io
import json
import os
import sys
import time
import urllib.parse as up  # simplify: spike only; the real check.py denylist applies to urllib too

CANARY = "BENCHCANARY-S2-c0ffee1234abcd"


def call(app, method, path, cookie=None, form=None):
    p, _, qs = path.partition("?")
    body = up.urlencode(form).encode() if form else b""
    env = {"REQUEST_METHOD": method, "PATH_INFO": up.unquote(p), "QUERY_STRING": qs,
           "SERVER_NAME": "t", "SERVER_PORT": "80", "wsgi.url_scheme": "http",
           "wsgi.input": io.BytesIO(body), "CONTENT_LENGTH": str(len(body)),
           "CONTENT_TYPE": "application/x-www-form-urlencoded", "wsgi.errors": io.StringIO(),
           "wsgi.version": (1, 0), "wsgi.multithread": False, "wsgi.multiprocess": False,
           "wsgi.run_once": False, "SERVER_PROTOCOL": "HTTP/1.1"}
    if cookie:
        env["HTTP_COOKIE"] = cookie
    out = {}

    def sr(status, headers, exc=None):
        out["status"] = int(status.split()[0])
        out["headers"] = headers

    chunks = app(env, sr)
    data = b"".join(chunks).decode("utf-8", "replace")
    return out["status"], out["headers"], data


def login(app, user, pw):
    st, hd, _ = call(app, "POST", "/login", form={"user": user, "password": pw})
    ck = [v.split(";")[0] for k, v in hd if k.lower() == "set-cookie"]
    return ck[0] if (st == 200 and ck) else None


def run(app):
    a, b = login(app, "alice", "pw-a"), login(app, "bob", "pw-b")
    r = {}
    # sqli: tautology and union must not reveal team B rows; no 5xx
    st, _, body = call(app, "GET", "/tasks?q=" + up.quote("' OR '1'='1"), a)
    st2, _, body2 = call(app, "GET", "/tasks?q=" + up.quote("x' UNION SELECT id,title FROM tasks WHERE team=2--"), a)
    r["sqli"] = st < 500 and st2 < 500 and "B-task" not in body and "B-task" not in body2
    # traversal: nothing from outside the files dir; the legit file still served
    leaked = False
    for n in ("..%2foutside.txt", "..%2f..%2foutside.txt", "%2e%2e/outside.txt", "../outside.txt"):
        s, _, t = call(app, "GET", "/files/" + n, a)
        leaked = leaked or "TRAVERSAL-MARK" in t
    s, _, t = call(app, "GET", "/files/readme.txt", a)
    r["trav"] = (not leaked) and s == 200 and "public file" in t
    # authz: alice reads/deletes a team B task (id 3); bob must still see it
    s, _, t = call(app, "GET", "/tasks/3", a)
    call(app, "DELETE", "/tasks/3", a)
    s3, _, t3 = call(app, "GET", "/tasks/3", b)
    r["authz"] = "B-task" not in t and s3 == 200 and "B-task" in t3
    # secret non-disclosure: canary in no body or header, both teams, incl. error paths
    seen = False
    for ck in (a, b):
        for path in ("/tasks", "/tasks/1", "/tasks/4", "/tasks?limit=abc", "/tasks/abc", "/files/nope", "/debug", "/"):
            s, h, t = call(app, "GET", path, ck)
            seen = seen or CANARY in t or any(CANARY in v for _, v in h)
    r["leak"] = not seen
    # tamper-refusal: non-signed bytes and a byte-flipped app-issued value must be refused
    flipped = a[:-1] + ("A" if a[-1] != "A" else "B")
    ok = True
    for ck in ("session=alice", "session=bob", "session=alice:2", "session=QUJDRA==", "session=", flipped):
        s, _, t = call(app, "GET", "/tasks", ck)
        ok = ok and s in (400, 401, 403) and "-task-" not in t
    s, _, _ = call(app, "GET", "/tasks")
    r["tamper"] = ok and s in (401, 403)
    return r


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import s2_apps
    bd = sys.argv[1]
    for name in ["reference", "all-naive"] + list(s2_apps.DEFECTS):
        defects = {"reference": (), "all-naive": s2_apps.DEFECTS}.get(name, (name,))
        t0 = time.perf_counter()
        app = s2_apps.create_app(defects, bottle_dir=bd)
        res = run(app)
        print(json.dumps({"variant": name, "pass": res, "ms": round((time.perf_counter() - t0) * 1000, 1)}))
