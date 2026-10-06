"""RS2 hidden check (W1-L 9.1, 9.3): eight fault cases against a check-owned log collector. Stdlib and bench_check only.

The check never imports the deliverable. Each case starts one probe host and one collector fake on the socket
`bench_check.listen()` yields. The host runs `rs2_shim.handle` (this folder), which builds the deliverable's `HttpShipper`,
feeds it the events `r1`, `r2` through `processor`, and calls `flush()`. The check measures each call's wall time and decides
every outcome itself from the raw response and the collector's counters. A case passes iff every clause holds; the clause that
decides is the first to fail, in this order: time, requests, effect, result. Evidence is counts and batch-id values, never bodies.

Scope, stated so nobody reads more than there is: the collector answers per a fixed schedule (which request number is slowed,
dropped, hung or answered 503), so a client is judged on these schedules only. No jitter, and the seed is unused. A response
lost in one flush followed by a new record before the next flush is not scheduled (the reference sends that record under the
kept batch id, and the collector would drop it as a repeat); only `g-ordering` adds a record after a failure, and its failure
is a 503, which applies nothing.
"""

import json
import os
import time

import bench_check as bc

MAX_BODY = 65536                                # a request body is read to this size at most
SLOW_S = 6.0                                    # the delay of a `slow` reply: past every bound of the case
SEED = ["r1", "r2"]                             # the events buffered before the first flush of every case
LATE = {"g-ordering": ["r3"], "g-lost-then-grow": ["r3"]}                   # events buffered between a failed flush and its `then` flush


class Fake:
    """The collector: stored batches by id, the records applied, and the requests of one case. One call is armed at a time."""

    def __init__(self):
        self.batches, self.applied, self.effects, self.requests, self.schedule, self.rest = {}, [], 0, [], [], "ok"
        self.seen = 0
        self.dup_deliveries = 0                 # deliveries that applied a record already applied (idempotency_violations)

    def arm(self, schedule, rest):
        self.schedule, self.rest, self.seen = list(schedule), rest, 0

    def malformed(self):
        self.requests.append({"n": len(self.requests) + 1, "batch_id": None, "action": "malformed"})
        return {"status": 400, "json": {"error": "malformed"}}

    def action(self):
        n = self.seen - 1                       # `handle` counts the request before it asks, so the first request is index 0
        if n < len(self.schedule):
            return self.schedule[n]
        return self.schedule[-1] if self.rest == "last" and self.schedule else "ok"

    def handle(self, method, path, headers, body):
        self.seen += 1
        action = self.action()
        try:
            batch = json.loads(body)
        except ValueError:
            batch = {}
        batch_id, records = batch.get("batch_id"), batch.get("records") or []
        self.requests.append({"n": len(self.requests) + 1, "batch_id": batch_id, "action": action})
        if method != "POST" or path != "/v1/logs":
            return {"status": 404, "json": {"error": "not found"}}
        if action == "s503":
            return {"status": 503, "json": {"error": "unavailable"}}
        if action == "s400":
            return {"status": 400, "json": {"error": "refused"}}
        if action == "hang":
            return {"hang": True}
        if batch_id is not None and batch_id in self.batches:
            accepted = self.batches[batch_id]
        else:
            accepted = len(records)
            if any(r in self.applied for r in records):
                self.dup_deliveries += 1        # one delivery counts once, however many of its records repeat
            self.applied.extend(records)
            self.effects += 1
            if batch_id is not None:
                self.batches[batch_id] = accepted
        if action == "lost":
            return {"drop": True}
        return {"status": 200, "json": {"accepted": accepted}, **({"delay": SLOW_S} if action == "slow" else {})}

    def names(self):
        return [r.get("event") for r in self.applied]


class Call:
    """One logical call: the host's answer, its wall time and what the collector saw while it ran."""

    def __init__(self, host, fake, frame):
        r0, e0, t0 = len(fake.requests), fake.effects, time.monotonic()
        resp = host.request(frame)
        self.ms = round((time.monotonic() - t0) * 1000)
        self.timed_out = host.timed_out
        self.ok = isinstance(resp, dict) and resp.get("ok") is True
        self.broken = resp is None and not host.timed_out
        self.value = resp.get("value") if self.ok else None
        self.requests, self.effects = len(fake.requests) - r0, fake.effects - e0


def serve(fake, sock):
    """Accept on the bound socket and answer per the fake. Returns the close function. Stdlib only; the fake decides every reply."""
    import http.server
    import threading

    stop = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        timeout = 10                             # every socket read of a request is bounded in time

        def do_POST(self):
            length = self.headers.get("Content-Length") or "0"
            if not length.isdigit() or int(length) > MAX_BODY:
                reply = fake.malformed()         # counted as a request, no effect, never read past the cap
            else:
                body = self.rfile.read(int(length))
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
        thread.join(5)                           # the serve thread ends inside the case, before the next case starts

    return close


def clause_of(case, calls, fake, contract):
    """The first failing clause of the case, or None. `calls` is the first flush, then the `then` flush when there was one."""
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
        good = first.ok and first.effects == 1 and first.value == len(SEED) and fake.names() == SEED
    else:
        good = not first.ok and first.effects <= case.get("effects_max", 0)   # a lost reply may follow an applied batch
    if not good:
        return "effect"
    if case.get("then"):
        want = SEED + LATE.get(case["id"], [])
        if not (calls[1].ok and calls[1].value == len(want) and fake.names() == want):
            return "result"
    return None


def run_probe(ctx, case, evidence, violations):
    fake = Fake()
    host, calls = None, []
    shim_dir = os.path.dirname(os.path.abspath(__file__))                  # where rs2_shim lives
    ctx.app["paths"] = [p for p in ctx.app.get("paths", []) if p != shim_dir] + [shim_dir]
    with bc.listen() as sock:
        close = serve(fake, sock)
        try:
            host = bc.probe_host(case, sock)
            setup = [host.request({"args": ["start", "{fake_url}"], "kwargs": {}}),   # `{fake_url}` is substituted by the host
                     host.request({"args": ["add", SEED], "kwargs": {}})]
            if not all(isinstance(r, dict) and r.get("ok") is True for r in setup):
                clause = "broken-exchange"
            else:
                fake.arm(case["schedule"], case["rest"])
                calls.append(Call(host, fake, ctx.doc["call"]))
                if case.get("then") and not (calls[0].broken or calls[0].timed_out):
                    host.request({"args": ["add", LATE.get(case["id"], [])], "kwargs": {}})
                    fake.arm(case["then"]["schedule"], case["then"]["rest"])   # the fault clears
                    calls.append(Call(host, fake, ctx.doc["call"]))
                clause = clause_of(case, calls, fake, ctx.doc["fault_contract"])
        finally:
            if host is not None:
                host.close()
            close()
    violations.append(fake.dup_deliveries)      # deliveries that re-applied a record (CR47-8); a replayed batch id applies nothing
    evidence[case["id"]] = {"clause": clause, "batch_ids": [r["batch_id"] for r in fake.requests],
                            "calls": [{"ms": c.ms, "requests": c.requests, "effects": c.effects, "ok": c.ok} for c in calls]}
    return "passed" if clause is None else "failed"


def check(ctx):
    evidence, violations = {}, []
    results = [bc.run_case(case, lambda case=case: run_probe(ctx, case, evidence, violations)) for case in ctx.cases]
    with open(os.path.join(ctx.evidence, "rs2-calls.json"), "w", encoding="utf-8") as f:
        json.dump(evidence, f, sort_keys=True)
    with open(os.path.join(ctx.evidence, "clauses.json"), "w", encoding="utf-8") as f:   # same dict as above: one source
        json.dump({case: e["clause"] for case, e in evidence.items() if e["clause"] is not None}, f, sort_keys=True)
    bc.write_result(results, {"idempotency_violations": sum(violations)})


bc.main(check)
