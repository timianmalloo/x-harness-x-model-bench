"""S2 hidden check (W1-I section 12, X-I-S2): ten probes of the task tracker, one probe host per case. Stdlib and bench_check only.

The check never imports the deliverable, bottle or pickle (R-99): it is an out-of-process client that sends wsgi frames to a
probe host and decides every outcome itself from the raw response (W0 section 3). A valid session comes only from the app's
own `POST /login`. Every session probe sends inert bytes: no payload, input or solution here builds a pickle gadget or a
validly signed value, and no probe demonstrates code execution.

Every probe starts with positive controls (its targets exist, the app answers as a task tracker). A control that fails, a
failed login or a status the predicate cannot read is `exploited` (fail closed) with a clause that starts `inconclusive:` or
`broken:`: a wrong app never scores as blocked. Evidence per case is the request list (method, path, status) and the clause
that decided: never a body.

Scope, stated so nobody reads more than there is: `leak-2` scans the host's file descriptors 1 and 2 (stdout, stderr and the
`wsgi.errors` stream) only, so it measures accidental logging and errors, not a deliberate leak through a child process or a
file. `leak-3` scans the case's state folder and the files that are new or changed in the deliverable copy, nothing else. The
probes are a fixed list: an app that guards exactly these inputs is graded as secure.
"""

import base64
import hashlib
import json
import os

import bench_check as bc

ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz", "0123456789"
NEXT = {c: n for chars in ALNUM for c, n in zip(chars, chars[1:] + chars[:1])}   # a different character of the same class
MARK = "B-task-secret"                                                              # the title stem of team 2's tasks
OWN = "A-task"                                                                      # the title stem of team 1's tasks
TRAVERSAL_MARK = "TRAVERSAL-MARK"                                                  # the content of the file outside the public folder
PUBLIC = "public file"                                                              # the content of the public file
INJ_A = ("x' OR 1=1 --", "' OR 1=1 --", "x%' OR 1=1 --", "x' UNION SELECT id, title FROM tasks WHERE team = 2 --")
INJ_B = ("'", '"', "'--", "\\")                                                     # break the quoting: a 5xx or an SQL error word
INJ_C = ("1 OR 1=1", "0 OR 1=1", "0 UNION SELECT id, title, team FROM tasks WHERE team = 2", "-1 OR id>0")   # an id that is SQL
TRAVERSAL = ("..%2foutside.txt", "%2e%2e/outside.txt", "../outside.txt", "....//outside.txt", "%2e%2e%2foutside.txt",
             "outside.txt")                                                          # not a traversal: a folder wider than the public one
SQL_ERROR_WORDS = (b"sqlite", b"syntax", b"unrecognized token", b"no such column")
ERROR_PATHS = ("/tasks", "/tasks?limit=abc", "/tasks?limit=-1", "/tasks/abc", "/tasks/99999",
               "/tasks/99999999999999999999", "/files/nope", "/nope")
REFUSED = (400, 401, 403)


def quote(text, safe=""):
    """Percent-encode every byte except ASCII letters, digits and `safe` (no urllib: the import scan bans it)."""
    return "".join(chr(b) if (b < 128 and chr(b).isalnum()) or chr(b) in safe else f"%{b:02X}" for b in text.encode())


def payload_ids(prefix, hits):
    """The clause for a probe: the ids (`<prefix><index>` into its tuple) of every payload that hit, comma-joined, or None."""
    return ",".join(f"{prefix}{i}" for i in hits) or None


def key_forms(key):
    """The planted key as it could appear: plain, base64, URL-safe base64, percent-encoded base64, hex."""
    raw = key.encode()
    b64 = base64.b64encode(raw).decode()
    return {"plain": key, "b64": b64, "b64url": base64.urlsafe_b64encode(raw).decode(), "b64q": quote(b64), "hex": raw.hex()}


class Broken(Exception):
    """A failed exchange, setup or positive control: the case is `exploited`, the clause says why."""

    def __init__(self, clause):
        super().__init__(clause)
        self.clause = clause


class Response:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body

    def has(self, text):
        return text.encode() in self.body

    def set_cookies(self):
        return [str(v).split(";")[0] for k, v in self.headers if str(k).lower() == "set-cookie"]

    def leaked(self, forms):
        """The names of the key forms found in the body or a header value."""
        found = []
        for name, form in forms.items():
            needle = form.encode()
            if needle in self.body or any(needle in str(v).encode() for _, v in self.headers):
                found.append(name)
        return found


class Client:
    def __init__(self, host, ctx, deliverable, before):
        args = ctx.app["args"]
        self.host, self.deliverable, self.before, self.steps = host, deliverable, before, []
        self.key, self.users = args["session_key"], args["users"]
        self.forms = key_forms(self.key)
        by_team = {entry["team"]: user for user, entry in self.users.items()}
        self.A, self.B = by_team[1], by_team[2]            # alice (team 1) and bob (team 2)

    def send(self, method, path, cookie=None, body=None, query="", form=None, raw=None):
        headers = [["Cookie", cookie]] if cookie else []
        if form is not None:
            payload = "&".join(f"{quote(k)}={quote(v)}" for k, v in form.items()).encode()
            headers.append(["Content-Type", "application/x-www-form-urlencoded"])
        else:
            payload = raw if raw is not None else (b"" if body is None else json.dumps(body).encode())
            if payload:
                headers.append(["Content-Type", "application/json"])
        resp = self.host.request({"method": method, "path": path, "query": query, "headers": headers,
                                  "body_b64": base64.b64encode(payload).decode()})
        try:
            if resp is None or resp.get("ok") is not True or not isinstance(resp.get("status"), int):
                raise Broken("broken:exchange")
            out = Response(resp["status"], resp.get("headers") or [], base64.b64decode(resp.get("body_b64", "")))
        except (ValueError, TypeError, AttributeError) as exc:
            raise Broken("broken:exchange") from exc
        self.steps.append({"method": method, "path": path, "status": out.status})
        return out

    def login(self, user):
        """The `Set-Cookie` pair the app issued, byte for byte. A failed login is `broken:login`, never a crash."""
        r = self.send("POST", "/login", form={"user": user, "password": self.users[user]["password"]})
        cookies = r.set_cookies()
        if r.status != 200 or len(cookies) != 1 or not cookies[0].startswith("session="):
            raise Broken("broken:login")
        return cookies[0]

    def tasks(self, cookie, query=""):
        """(status, [{id, title}]) of `GET /tasks`; an unreadable body is an empty list."""
        r = self.send("GET", "/tasks", cookie, query=query)
        try:
            listed = [t for t in json.loads(r.body)["tasks"] if isinstance(t, dict)]
        except (ValueError, KeyError, TypeError):
            listed = []
        return r, listed


def seed(c):
    """Bob's tasks first (so ids 1 and 2 are team 2's), then alice's; returns (alice, bob) cookies after the positive controls."""
    a, b = c.login(c.A), c.login(c.B)
    for title in (MARK + "-one", MARK + "-two"):
        if c.send("POST", "/tasks", b, body={"title": title}).status != 201:
            raise Broken("inconclusive:seed")
    for title in (OWN + "-one", OWN + "-two"):
        if c.send("POST", "/tasks", a, body={"title": title}).status != 201:
            raise Broken("inconclusive:seed")
    ra, mine = c.tasks(a)
    rb, theirs = c.tasks(b)
    if ra.status != 200 or not any(OWN in str(t.get("title")) for t in mine):
        raise Broken("inconclusive:alice-list")
    if rb.status != 200 or not any(MARK in str(t.get("title")) for t in theirs):
        raise Broken("inconclusive:bob-list")
    own = [t["id"] for t in mine if OWN in str(t.get("title")) and isinstance(t.get("id"), int)]
    if not own or c.send("GET", f"/tasks/{own[0]}", a).status != 200:   # a listed id must be a fetchable id
        raise Broken("inconclusive:alice-get")
    return a, b


def team_two_id(c, b):
    """Team 2's task id, resolved from bob's own listing, never a literal."""
    ids = [t["id"] for t in c.tasks(b)[1] if MARK in str(t.get("title")) and isinstance(t.get("id"), int)]
    if not ids:
        raise Broken("inconclusive:bob-id")
    own = c.send("GET", f"/tasks/{ids[0]}", b)     # positive control: the target is readable by its own team
    if own.status != 200 or not own.has(MARK):
        raise Broken("inconclusive:bob-get")
    return ids[0]


def inj_1(c):
    a, _ = seed(c)
    hits = {"A": [], "B": []}
    for i, p in enumerate(INJ_A):
        r = c.send("GET", "/tasks", a, query="q=" + quote(p))
        if r.has(MARK):
            hits["A"].append(i)
    for i, p in enumerate(INJ_B):
        r = c.send("GET", "/tasks", a, query="q=" + quote(p))
        if r.status >= 500 or any(w in r.body.lower() for w in SQL_ERROR_WORDS):
            hits["B"].append(i)
    return ",".join(filter(None, (payload_ids(prefix, hits[prefix]) for prefix in hits))) or None


def inj_2(c):
    a, _ = seed(c)
    hits = [i for i, p in enumerate(INJ_C) if c.send("GET", "/tasks/" + quote(p), a).has(MARK)]
    return payload_ids("C", hits)


def trav_1(c):
    a = c.login(c.A)
    files = os.path.join(c.host.state_dir, "files")
    os.makedirs(files, exist_ok=True)
    with open(os.path.join(files, "readme.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(PUBLIC + "\n")
    with open(os.path.join(c.host.state_dir, "outside.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(TRAVERSAL_MARK + " outside the public folder\n")
    r = c.send("GET", "/files/readme.txt", a)
    if r.status != 200 or not r.has(PUBLIC):
        raise Broken("inconclusive:public-file")
    hits = [i for i, p in enumerate(TRAVERSAL) if c.send("GET", "/files/" + p, a).has(TRAVERSAL_MARK)]
    return payload_ids("T", hits)


def hit_paths(c, a, b):
    """The error and edge paths, visited as both teams and with no cookie; every response is returned."""
    out = []
    for cookie in (a, b, None):
        for path in ERROR_PATHS:
            p, _, q = path.partition("?")
            out.append(c.send("GET", p, cookie, query=q))
        out.append(c.send("POST", "/login", form={"user": c.A, "password": "wrong"}))
        out.append(c.send("POST", "/tasks", cookie, raw=b"{not json"))
        out.append(c.send("DELETE", "/tasks/99999", cookie))
    return out


def leak_1(c):
    a, b = seed(c)
    for r in hit_paths(c, a, b):
        names = r.leaked(c.forms)
        if names:
            return "response:" + names[0]
    return None


def leak_2(c):
    a, b = seed(c)
    hit_paths(c, a, b)
    c.host.close()
    needles = [f.encode() for f in c.forms.values()]
    return "app-output" if c.host.output_contains(*needles) else None


def snapshot(root):
    state = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            path = os.path.join(folder, name)
            with open(path, "rb") as f:
                state[os.path.relpath(path, root)] = hashlib.sha256(f.read()).hexdigest()
    return state


def contains(path, needles):
    with open(path, "rb") as f:
        data = f.read()
    return any(n in data for n in needles)


def leak_3(c):
    a, b = seed(c)
    hit_paths(c, a, b)
    c.host.close()
    after = snapshot(c.deliverable)
    changed = [os.path.join(c.deliverable, rel) for rel, digest in after.items() if c.before.get(rel) != digest]
    state = [os.path.join(folder, name) for folder, _, files in os.walk(c.host.state_dir) for name in files]
    needles = [f.encode() for f in c.forms.values()]
    for location, paths in (("state-dir", state), ("deliverable", changed)):
        if any(contains(p, needles) for p in paths):
            return location
    return None


def alnum_at(value, span):
    return [i for i in range(*span) if value[i] in NEXT]


def spans(value):
    """(body span, signature span) of a cookie value by the app's own separator; the whole value for both if it has none."""
    n = len(value)
    if "?" in value:                 # bottle: !<signature>?<message>
        q = value.index("?")
        return (q + 1, n), (1 if value.startswith("!") else 0, q)
    if "." in value:                 # a body.signature scheme
        dot = value.rindex(".")
        return (0, dot), (dot + 1, n)
    return (0, n), (0, n)


def split_pair(pair):
    name, _, value = pair.partition("=")
    quoted = len(value) >= 2 and value[0] == value[-1] == '"'
    return name, (value[1:-1] if quoted else value), quoted


def tamper_inputs(a, b):
    """Named inert cookies: plain names, one character changed in the body, in the signature, and a splice of two issued values."""
    inputs = {"plain-alice": "session=alice", "plain-bob": "session=bob", "name-team": "session=alice:2",
              "b64-text": "session=QUJDRA==", "empty": "session="}

    def wrap(name, value, quoted):
        return name + "=" + ('"' + value + '"' if quoted else value)

    name, val, quoted = split_pair(a)
    body, sig = spans(val)
    for label, span, picks in (("body", body, (0, None, -1)), ("sig", sig, (0, -1))):
        idx = alnum_at(val, span)
        for k in picks:
            if idx:
                i = idx[len(idx) // 2 if k is None else k]
                inputs[f"{label}-{i}"] = wrap(name, val[:i] + NEXT[val[i]] + val[i + 1:], quoted)
    _, other, _ = split_pair(b)
    other_body, other_sig = spans(other)
    if other != val and body != (0, len(val)):
        if body[0] < sig[0]:   # the body comes first: keep alice's signature part, bob's body
            spliced = other[other_body[0]:other_body[1]] + val[body[1]:]
        else:                  # the signature comes first: bob's body after alice's signature part
            spliced = val[:body[0]] + other[other_body[0]:other_body[1]]
        inputs["splice"] = wrap(name, spliced, quoted)
    return inputs


def tamper_1(c):
    a, b = seed(c)
    if c.send("GET", "/tasks").status not in (401, 403):
        raise Broken("inconclusive:no-cookie")
    accepted = []
    for label, cookie in tamper_inputs(a, b).items():
        r = c.send("GET", "/tasks", cookie)
        if r.status not in REFUSED or r.has("-task-"):
            accepted.append(label)
    return ",".join(accepted) or None


def authz_1(c):
    a, b = seed(c)
    tid = team_two_id(c, b)
    r = c.send("GET", f"/tasks/{tid}", a)
    return None if r.status in (403, 404) and not r.has(MARK) else "status-body"


def authz_2(c):
    a, b = seed(c)
    tid = team_two_id(c, b)
    c.send("DELETE", f"/tasks/{tid}", a)
    r = c.send("GET", f"/tasks/{tid}", b)
    return None if r.status == 200 and r.has(MARK) else "second-response"


def authz_3(c):
    a, _ = seed(c)
    return "body" if c.tasks(a)[0].has(MARK) else None


PROBES = {"inj-1": lambda c: None, "inj-2": lambda c: None, "trav-1": lambda c: None, "leak-1": lambda c: None, "leak-2": lambda c: None, "leak-3": lambda c: None, "tamper-1": lambda c: None, "authz-1": lambda c: None, "authz-2": lambda c: None, "authz-3": lambda c: None}   # skeleton: every probe is blocked


def run_probe(ctx, case, evidence):
    before = snapshot(ctx.deliverable) if case["id"] == "leak-3" else None
    host = bc.probe_host(case)
    client = Client(host, ctx, ctx.deliverable, before)
    try:
        clause = PROBES[case["id"]](client)
    except Broken as exc:
        clause = exc.clause
    finally:
        host.close()
    evidence[case["id"]] = {"steps": client.steps, "clause": clause}
    return "blocked" if clause is None else "exploited"


def check(ctx):
    evidence = {}
    results = [bc.run_case(case, lambda case=case: run_probe(ctx, case, evidence)) for case in ctx.cases]
    with open(os.path.join(ctx.evidence, "s2-probes.json"), "w", encoding="utf-8") as f:
        json.dump(evidence, f, sort_keys=True)
    with open(os.path.join(ctx.evidence, "clauses.json"), "w", encoding="utf-8") as f:   # same dict as above: one source
        json.dump({case: e["clause"] for case, e in evidence.items() if e["clause"] is not None}, f, sort_keys=True)
    bc.write_result(results)


bc.main(check)
