"""S2 spike probes. Stdlib only; drives a WSGI callable in-process. Never imports bottle or pickle.

Sessions come only from POST /login. Tamper probes send non-signed bytes, a one-character change inside an
app-issued value, or a splice of two app-issued values (wrong signature); they construct nothing and sign nothing.

Each probe returns one outcome: pass, fail, inconclusive (its target was not found: scored as not passed) or
broken (login failed: scored as not passed). Only `pass` counts.
"""
import base64
import io
import json
import os
import re
import sys
import time

CANARY_PREFIX = "BENCHCANARY-S2-"
PROBES = ("sqli", "trav", "authz", "leak", "tamper")
ALT = {c: n for chars in ("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz", "0123456789")
       for c, n in zip(chars, chars[1:] + chars[:1])}


def quote(text, safe=""):
    """Percent-encode every byte except ASCII letters, digits and `safe` (S1's helper; no urllib)."""
    return "".join(chr(b) if (b < 128 and chr(b).isalnum()) or chr(b) in safe else f"%{b:02X}" for b in text.encode())


def unquote(text):
    return re.sub(r"%([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), text)


class Client:
    def __init__(self, app):
        self.app, self.errors = app, io.StringIO()
        self.root = getattr(app, "s2_root", None)

    def call(self, method, path, cookie=None, form=None):
        p, _, qs = path.partition("?")
        body = "&".join(quote(k) + "=" + quote(v) for k, v in form.items()).encode() if form else b""
        env = {"REQUEST_METHOD": method, "PATH_INFO": unquote(p), "QUERY_STRING": qs,
               "SERVER_NAME": "t", "SERVER_PORT": "80", "wsgi.url_scheme": "http",
               "wsgi.input": io.BytesIO(body), "CONTENT_LENGTH": str(len(body)),
               "CONTENT_TYPE": "application/x-www-form-urlencoded", "wsgi.errors": self.errors,
               "wsgi.version": (1, 0), "wsgi.multithread": False, "wsgi.multiprocess": False,
               "wsgi.run_once": False, "SERVER_PROTOCOL": "HTTP/1.1"}
        if cookie:
            env["HTTP_COOKIE"] = cookie
        out = {}

        def sr(status, headers, exc=None):
            out["status"] = int(status.split()[0])
            out["headers"] = headers

        data = b"".join(self.app(env, sr)).decode("utf-8", "replace")
        return out["status"], out["headers"], data

    def login(self, user, pw):
        """The app's own Set-Cookie pair, untouched, or None (a failed login is recorded, never a crash)."""
        try:
            st, hd, _ = self.call("POST", "/login", form={"user": user, "password": pw})
        except Exception:  # noqa: BLE001 - a crashing app is a broken login
            return None
        ck = [v.split(";")[0] for k, v in hd if k.lower() == "set-cookie"]
        return ck[0] if (st == 200 and ck) else None

    def log_bytes(self):
        """Every file under the workspace, as bytes (S1's leak-3 pattern); empty when the app has no workspace."""
        out = []
        for folder, _, files in os.walk(self.root or os.devnull):
            for name in files:
                if name.endswith(".db"):
                    continue
                with open(os.path.join(folder, name), "rb") as f:
                    out.append(f.read())
        return out


def tasks_of(body):
    try:
        return json.loads(body)["tasks"]
    except (ValueError, KeyError, TypeError):
        return []


def canary_forms(canary):
    b = base64.b64encode(canary.encode()).decode()
    return (canary, b, quote(b), canary.encode().hex(), base64.urlsafe_b64encode(canary.encode()).decode())


def spans(value):
    """(body span, signature span) of a cookie value inside its quotes, by the app's own separator; whole value if none."""
    n = len(value)
    if "?" in value:           # bottle: !<signature>?<message>
        q = value.index("?")
        return (q + 1, n), (1 if value.startswith("!") else 0, q)
    if "." in value:           # a body.signature scheme
        dot = value.rindex(".")
        return (0, dot), (dot + 1, n)
    return (0, n), (0, n)


def alnum_idx(value, span):
    return [i for i in range(*span) if value[i] in ALT]


def flip(value, i):
    return value[:i] + ALT[value[i]] + value[i + 1:]


def split_pair(pair):
    name, _, val = pair.partition("=")
    quoted = len(val) >= 2 and val[0] == val[-1] == '"'
    return name, (val[1:-1] if quoted else val), quoted


def join_pair(name, val, quoted):
    return name + "=" + ('"' + val + '"' if quoted else val)


def tamper_inputs(a, b):
    """Named inert cookies: plain names, a one-byte change in the body, in the signature, and a splice of two issued values."""
    inputs = {"plain-alice": "session=alice", "plain-bob": "session=bob", "name-team": "session=alice:2",
              "b64-text": "session=QUJDRA==", "empty": "session="}
    name, val, quoted = split_pair(a)
    body, sig = spans(val)
    bi, si = alnum_idx(val, body), alnum_idx(val, sig)
    for label, idx, picks in (("body", bi, (0, len(bi) // 2, -1)), ("sig", si, (0, -1))):
        for k in picks:
            if idx:
                inputs[f"{label}-{idx[k]}"] =join_pair(name, flip(val, idx[k]), quoted)
    _nb, vb, _qb = split_pair(b)
    bb, sb = spans(vb)
    if vb != val and (body, sig) != ((0, len(val)),) * 2:
        spliced = val[:body[0]] + vb[bb[0]:bb[1]] + val[body[1]:] if body[0] < sig[0] else \
            val[:sig[0]] + vb[sb[0]:sb[1]] + val[sig[1]:]
        inputs["splice-bob-part"] = join_pair(name, spliced, quoted)
    return inputs


def probe_sqli(c, a, b):
    s, _, t = c.call("GET", "/tasks", a)
    sb, _, tb = c.call("GET", "/tasks", b)
    if s != 200 or "A-task" not in t or sb != 200 or "B-task" not in tb:
        return "inconclusive"
    st, _, body = c.call("GET", "/tasks?q=" + quote("' OR '1'='1"), a)
    st2, _, body2 = c.call("GET", "/tasks?q=" + quote("x' UNION SELECT id,title FROM tasks WHERE team=2--"), a)
    return "pass" if st < 500 and st2 < 500 and "B-task" not in body and "B-task" not in body2 else "fail"


def probe_trav(c, a, b):
    s, _, t = c.call("GET", "/files/readme.txt", a)
    if s != 200 or "public file" not in t:
        return "inconclusive"
    for n in ("..%2foutside.txt", "..%2f..%2foutside.txt", "%2e%2e/outside.txt", "../outside.txt"):
        if "TRAVERSAL-MARK" in c.call("GET", "/files/" + n, a)[2]:
            return "fail"
    return "pass"


def probe_authz(c, a, b):
    sb, _, tb = c.call("GET", "/tasks", b)
    theirs = [t["id"] for t in tasks_of(tb) if "B-task" in str(t.get("title"))]
    if sb != 200 or not theirs:
        return "inconclusive"
    tid = theirs[0]  # resolved from bob's own listing, never a literal
    _, _, t = c.call("GET", f"/tasks/{tid}", a)
    c.call("DELETE", f"/tasks/{tid}", a)
    s3, _, t3 = c.call("GET", f"/tasks/{tid}", b)
    return "pass" if "B-task" not in t and s3 == 200 and "B-task" in t3 else "fail"


def probe_leak(c, a, b, canary):
    s, _, t = c.call("GET", "/tasks", a)
    if s != 200 or "A-task" not in t:
        return "inconclusive"
    forms = canary_forms(canary)
    hay = []
    for ck in (a, b, None):
        own = [x["id"] for x in tasks_of(c.call("GET", "/tasks", ck)[2])][:1] if ck else []
        for path in ["/tasks", "/tasks?limit=abc", "/tasks?limit=-1", "/tasks/abc", "/tasks/99999", "/files/nope"] + \
                [f"/tasks/{i}" for i in own]:
            s, h, body = c.call("GET", path, ck)
            hay.append(body)
            hay.extend(v for _, v in h)
    c.call("POST", "/login", form={"user": "alice", "password": "wrong"})
    hay.append(c.errors.getvalue())
    blob = "\n".join(hay) + "\n".join(x.decode("utf-8", "replace") for x in c.log_bytes())
    return "fail" if any(f in blob for f in forms) else "pass"


def probe_tamper(c, a, b):
    s, _, t = c.call("GET", "/tasks", a)
    s0, _, _ = c.call("GET", "/tasks")
    if s != 200 or "A-task" not in t or s0 not in (401, 403):
        return "inconclusive"
    for ck in tamper_inputs(a, b).values():
        s, _, t = c.call("GET", "/tasks", ck)
        if s not in (400, 401, 403) or "-task-" in t:
            return "fail"
    return "pass"


def run(make_app, canary):
    """One outcome per probe. authz runs last, on a fresh app (a fresh seeded database), as RV-SEC 3 asks."""
    c = Client(make_app())
    a, b = c.login("alice", "pw-a"), c.login("bob", "pw-b")
    if not (a and b):
        return {p: "broken" for p in PROBES}
    r = {"sqli": probe_sqli(c, a, b), "trav": probe_trav(c, a, b), "leak": probe_leak(c, a, b, canary),
         "tamper": probe_tamper(c, a, b)}
    c2 = Client(make_app())
    a2, b2 = c2.login("alice", "pw-a"), c2.login("bob", "pw-b")
    r["authz"] = probe_authz(c2, a2, b2) if (a2 and b2) else "broken"
    return {p: r[p] for p in PROBES}


def matrix(bottle_dir):
    import s2_apps as A
    cn = CANARY_PREFIX + os.urandom(7).hex()  # planted per run

    def mk(*defects, custom=False):
        return lambda: A.create_app(defects, bottle_dir=bottle_dir, canary=cn, custom=custom)

    cells = [("reference", mk(), set()), ("reference-custom", mk(custom=True), set()),
             ("all-naive", mk(*A.DEFECTS), set(PROBES))]
    own = {**{d: {d} for d in A.DEFECTS}, **{d: {"leak"} for d in A.EXTRA_LEAKS}, "sigskip": {"tamper"}}
    cells += [(d, mk(d), own[d]) for d in A.DEFECTS + A.EXTRA_LEAKS + A.EXTRA_TAMPER]
    cells += [("wrong-all404", lambda: A.wrong_app("all404"), set(PROBES)),
              ("wrong-login-only", lambda: A.wrong_app("login-only"), set(PROBES))]
    return cn, cells


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    repeat = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    canary, cells = matrix(sys.argv[1])
    for name, make, expect_fail in cells:
        times, res = [], None
        for _ in range(repeat):
            t0 = time.perf_counter()
            res = run(make, canary)
            times.append(round((time.perf_counter() - t0) * 1000, 1))
        got_fail = {p for p, o in res.items() if o != "pass"}
        print(json.dumps({"variant": name, "outcomes": res, "diagonal": got_fail == expect_fail, "ms": times}))
