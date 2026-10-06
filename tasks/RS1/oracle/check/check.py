"""RS1 hidden check (W1-L 9.1, 9.2): seven fault cases against a check-owned ledger fake. Stdlib and bench_check only.

The check never imports the deliverable. Each case starts one probe host and one fake on the socket `bench_check.listen()` yields, calls
`post_event` through the host (which fills in the fake's URL), and decides every outcome itself from the raw response and the fake's
counters. A case passes iff every clause holds; the clause that decides is the first to fail, in this order:
time, requests, effect, result. Evidence is counts and key values, never a body.

Scope, stated so nobody reads more than there is: the fake answers per a fixed schedule (which request number is slowed,
dropped, hung or answered 503), so a client is judged on these schedules only. No jitter, and the seed is unused.
"""

import json
import os
import time

import bench_check as bc

SLOW_S = 6.0                                    # the delay of a `slow` reply: past every bound of the case


class Fake:
    """The ledger service: events, the key table and the requests of one case. One logical call is armed at a time."""

    def __init__(self):
        self.events, self.by_key, self.requests, self.schedule, self.rest = [], {}, [], [], "ok"
        self.seen = 0

    def arm(self, schedule, rest):
        self.schedule, self.rest, self.seen = list(schedule), rest, 0

    def action(self):
        n = self.seen - 1                       # `handle` counts the request before it asks, so the first request is index 0
        if n < len(self.schedule):
            return self.schedule[n]
        return self.schedule[-1] if self.rest == "last" and self.schedule else "ok"

    def handle(self, method, path, headers, body):
        self.seen += 1
        action = self.action()
        key = headers.get("idempotency-key")
        self.requests.append({"n": len(self.requests) + 1, "key": key, "action": action})
        if method != "POST" or path != "/v1/events":
            return {"status": 404, "json": {"error": "not found"}}
        if action == "s503":
            return {"status": 503, "json": {"error": "unavailable"}}
        if action == "s400":
            return {"status": 400, "json": {"error": "refused"}}
        if action == "hang":
            return {"hang": True}
        if key and key in self.by_key:
            status, event = 200, self.by_key[key]
        else:
            status, event = 201, len(self.events) + 1
            self.events.append(event)
            if key:
                self.by_key[key] = event
        if action == "lost":
            return {"drop": True}
        return {"status": status, "json": {"id": event}, **({"delay": SLOW_S} if action == "slow" else {})}


class Call:
    """One logical call: the host's answer, its wall time and what the fake saw while it ran."""

    def __init__(self, host, fake, frame):
        r0, e0, t0 = len(fake.requests), len(fake.events), time.monotonic()
        resp = host.request(frame)
        self.ms = round((time.monotonic() - t0) * 1000)
        self.timed_out = host.timed_out
        self.ok = isinstance(resp, dict) and resp.get("ok") is True
        self.broken = resp is None and not host.timed_out
        self.value = resp.get("value") if self.ok else None
        self.requests, self.effects = len(fake.requests) - r0, len(fake.events) - e0


def serve(fake, sock):
    """Accept on the bound socket and answer per the fake. Returns (stop, thread). Stdlib only; the fake decides every reply."""
    import http.server
    import threading

    stop = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            reply = fake.handle("POST", self.path, {k.lower(): v for k, v in self.headers.items()}, body)
            if reply.get("drop"):
                self.close_connection = True
                return
            if reply.get("hang"):
                stop.wait(60)
                return
            if reply.get("delay"):
                stop.wait(reply["delay"])
            data = json.dumps(reply["json"]).encode()
            self.send_response(reply["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except OSError:
                pass

        def log_message(self, *args):
            pass

    class Server(http.server.ThreadingHTTPServer):
        daemon_threads = True

    server = Server(sock.getsockname(), Handler, bind_and_activate=False)
    server.socket.close()
    server.socket = sock                         # the listener's socket, already bound and listening
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def close():
        stop.set()
        server.shutdown()                        # the socket itself is closed by `listen`'s context manager

    return close


def clause_of(case, calls, fake, contract):
    """The first failing clause of the case, or None. `calls` is the first call, then the `then` call when there was one."""
    if any(c.broken for c in calls):
        return "broken-exchange"
    limit = contract["timeout_ms"] + contract["tolerance_ms"]
    if any(c.timed_out or c.ms > limit for c in calls):
        return "time"
    if any(c.requests > contract["max_retries"] + 1 for c in calls) or (case.get("final") and calls[0].requests != 1):
        return "requests"
    first = calls[0]
    if case["expect"] == "either":
        good = first.effects <= 1
    elif case["expect"] == "succeed":
        good = first.ok and first.effects == 1 and first.value == fake.events[-1]
    else:
        good = not first.ok and first.effects == 0
    if not good:
        return "effect"
    if case.get("then") and not (calls[1].ok and len(fake.events) == 1 and calls[1].value == fake.events[0]):
        return "result"
    return None


def run_probe(ctx, case, evidence, violations):
    fake = Fake()
    host, calls = None, []
    with bc.listen() as sock:
        close = serve(fake, sock)
        try:
            host = bc.probe_host(case, sock)
            frame = ctx.doc["call"]                  # `{fake_url}` is substituted by the host
            fake.arm(case["schedule"], case["rest"])
            calls.append(Call(host, fake, frame))
            if case.get("then") and not (calls[0].broken or calls[0].timed_out):
                fake.arm(case["then"]["schedule"], case["then"]["rest"])   # the fault clears
                calls.append(Call(host, fake, frame))
            clause = clause_of(case, calls, fake, ctx.doc["fault_contract"])
        finally:
            if host is not None:
                host.close()
            close()
    violations.append(sum(max(0, c.effects - 1) for c in calls))
    evidence[case["id"]] = {"clause": clause, "keys": [r["key"] for r in fake.requests],
                            "calls": [{"ms": c.ms, "requests": c.requests, "effects": c.effects, "ok": c.ok} for c in calls]}
    return "passed" if clause is None else "failed"


def check(ctx):
    evidence, violations = {}, []
    results = [bc.run_case(case, lambda case=case: run_probe(ctx, case, evidence, violations)) for case in ctx.cases]
    with open(os.path.join(ctx.evidence, "rs1-calls.json"), "w", encoding="utf-8") as f:
        json.dump(evidence, f, sort_keys=True)
    with open(os.path.join(ctx.evidence, "clauses.json"), "w", encoding="utf-8") as f:   # same dict as above: one source
        json.dump({case: e["clause"] for case, e in evidence.items() if e["clause"] is not None}, f, sort_keys=True)
    bc.write_result(results, {"idempotency_violations": sum(violations)})


bc.main(check)
