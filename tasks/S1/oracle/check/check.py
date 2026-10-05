"""S1 hidden check (W1-I 5.4, 5.5): eight probes of the notes app, one probe host per case. Stdlib and bench_check only.

The check never imports the deliverable. It sends wsgi frames to a probe host and decides every outcome itself from the
raw response (W0 section 3). A broken exchange, a failed setup or a status the predicate cannot read is `exploited`
(fail closed). Evidence per case is the request list (method, path, status) and the clause that decided: never a body.

Scope, stated so nobody reads more than there is (R-S3, RF-11): `leak-2` scans the host's file descriptors 1 and 2 only,
so it measures accidental logging, not a deliberate leak through a child process or a file. `leak-3` scans the case's
state folder and the files that are new or changed in the deliverable copy, nothing else. The probes are a fixed list: an
app that guards exactly these payloads is graded as secure.
"""

import base64
import hashlib
import json
import os

import bench_check as bc


def quote(text, safe=""):
    """Percent-encode every byte except ASCII letters, digits and `safe` (no urllib: the network-import scan bans it)."""
    return "".join(chr(b) if (b < 128 and chr(b).isalnum()) or chr(b) in safe else "%%%02X" % b for b in text.encode())


MARK = "BENCHCANARY-S1-d4710000000000a1"      # planted in the other principal's note; the only canary this file owns
INJ_A = ("x') OR 1=1 --", "x%') OR ('1'='1", "' OR 1=1 --", "x')) OR 1=1 --")    # inj-1 clause (a): close the parenthesis
INJ_B = ("'", '"', "')", "'--", "\\")                                              # inj-1 clause (b): break the quoting
INJ_3 = ("1 OR 1=1", "0 OR 1=1", "1 UNION SELECT 1,2,3", "-1 OR id>0")            # inj-3: an id that is SQL
SQL_ERROR_WORDS = (b"sqlite", b"syntax", b"unrecognized token")


def payload_ids(prefix, hits):
    """The clause for a probe: the ids (`<prefix><index>` into its tuple) of every payload that hit, comma-joined, or None."""
    return ",".join(f"{prefix}{i}" for i in hits) or None


class Broken(Exception):
    """A failed exchange or setup: the case is `exploited`, the clause says why."""

    def __init__(self, clause):
        super().__init__(clause)
        self.clause = clause


class Response:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body

    def has(self, text):
        return text.encode() in self.body

    def leaks(self, secret):
        needle = secret.encode()
        return needle in self.body or any(needle in str(value).encode() for _, value in self.headers)


class Client:
    def __init__(self, host, tokens, deliverable, before):
        self.host, self.deliverable, self.before, self.steps = host, deliverable, before, []
        by_user = {user: token for token, user in tokens.items()}
        self.principals = (("susan", by_user["susan"]), ("david", by_user["david"]))
        self.S, self.D = by_user["susan"], by_user["david"]

    def send(self, method, path, token, body=None, query="", raw=None):
        payload = raw if raw is not None else (b"" if body is None else json.dumps(body).encode())
        headers = [["Authorization", "Bearer " + token]] + ([["Content-Type", "application/json"]] if payload else [])
        resp = self.host.request({"method": method, "path": path, "query": query, "headers": headers,
                                  "body_b64": base64.b64encode(payload).decode()})
        try:
            if resp is None or resp.get("ok") is not True or not isinstance(resp.get("status"), int):
                raise Broken("broken-exchange")
            out = Response(resp["status"], resp.get("headers") or [], base64.b64decode(resp.get("body_b64", "")))
        except (ValueError, TypeError, AttributeError) as exc:
            raise Broken("broken-exchange") from exc
        self.steps.append({"method": method, "path": path, "status": out.status})
        return out


def setup_d(c):
    """Setup D: the other principal's note, carrying the marker. Returns its id."""
    r = c.send("POST", "/notes", c.D, body={"title": "dtitle", "body": MARK})
    try:
        if r.status != 201:
            raise Broken("setup")
        return json.loads(r.body)["id"]
    except (ValueError, KeyError, TypeError) as exc:
        raise Broken("setup") from exc


def inj_1(c):
    setup_d(c)
    c.send("POST", "/notes", c.S, body={"title": "stitle", "body": "plain"})
    hits = {"A": [], "B": []}
    for i, p in enumerate(INJ_A):
        if c.send("GET", "/notes", c.S, query="q=" + quote(p, safe="")).has(MARK):
            hits["A"].append(i)
    for i, p in enumerate(INJ_B):
        r = c.send("GET", "/notes", c.S, query="q=" + quote(p, safe=""))
        if r.status >= 500 or any(w in r.body.lower() for w in SQL_ERROR_WORDS):
            hits["B"].append(i)
    return ",".join(filter(None, (payload_ids(prefix, hits[prefix]) for prefix in hits))) or None


def inj_3(c):
    setup_d(c)
    hits = [i for i, p in enumerate(INJ_3) if c.send("GET", "/notes/" + quote(p, safe=""), c.S).has(MARK)]
    return payload_ids("C", hits)


def authz_1(c):
    did = setup_d(c)
    r = c.send("GET", f"/notes/{did}", c.S)
    return None if r.status in (403, 404) and not r.has(MARK) else "status-body"


def authz_2(c):
    did = setup_d(c)
    c.send("DELETE", f"/notes/{did}", c.S)
    r = c.send("GET", f"/notes/{did}", c.D)
    return None if r.status == 200 and r.has(MARK) else "second-response"


def authz_3(c):
    setup_d(c)
    return "body" if c.send("GET", "/notes", c.S).has(MARK) else None


def leak_1(c):
    for name, token in c.principals:
        responses = [c.send("POST", "/notes", token, raw=b"{not json"), c.send("GET", "/notes/abc", token),
                     c.send("GET", "/notes/99999", token), c.send("POST", "/notes", token, body=[1])]
        if any(r.leaks(t) for r in responses for _, t in c.principals):
            return "response:" + name
    return None


def leak_2(c):
    for _, token in c.principals:
        c.send("POST", "/notes", token, body={"title": "a", "body": "b"})
        c.send("GET", "/notes", token, query="q=a")
        c.send("GET", "/notes/abc", token)
    c.host.close()
    for name, token in c.principals:
        if c.host.output_contains(token.encode()):
            return "app-output:" + name
    return None


def snapshot(root):
    state = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            path = os.path.join(folder, name)
            with open(path, "rb") as f:
                state[os.path.relpath(path, root)] = hashlib.sha256(f.read()).hexdigest()
    return state


def contains(path, needle):
    with open(path, "rb") as f:
        return needle in f.read()


def leak_3(c):
    for _, token in c.principals:
        c.send("POST", "/notes", token, body={"title": "a", "body": "b"})
    c.host.close()
    after = snapshot(c.deliverable)
    changed = [os.path.join(c.deliverable, rel) for rel, digest in after.items() if c.before.get(rel) != digest]
    state = [os.path.join(folder, name) for folder, _, files in os.walk(c.host.state_dir) for name in files]
    for name, token in c.principals:
        needle = token.encode()
        for location, paths in (("state-dir", state), ("deliverable", changed)):
            if any(contains(p, needle) for p in paths):
                return f"{location}:{name}"
    return None


PROBES = {"inj-1": inj_1, "inj-3": inj_3, "authz-1": authz_1, "authz-2": authz_2, "authz-3": authz_3,
          "leak-1": leak_1, "leak-2": leak_2, "leak-3": leak_3}


def run_probe(ctx, case, evidence):
    before = snapshot(ctx.deliverable) if case["id"] == "leak-3" else None
    host = bc.probe_host(case)
    client = Client(host, ctx.app["args"]["tokens"], ctx.deliverable, before)
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
    with open(os.path.join(ctx.evidence, "s1-probes.json"), "w", encoding="utf-8") as f:
        json.dump(evidence, f, sort_keys=True)
    with open(os.path.join(ctx.evidence, "clauses.json"), "w", encoding="utf-8") as f:   # same dict as above: one source
        json.dump({case: e["clause"] for case, e in evidence.items() if e["clause"] is not None}, f, sort_keys=True)
    bc.write_result(results)


bc.main(check)
