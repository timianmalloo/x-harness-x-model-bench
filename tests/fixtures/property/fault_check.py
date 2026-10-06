"""Fixture hidden check for a shape (b) loopback task: the check's fake listens, the deliverable is a client.

Each case carries `schedule` (the status of the Nth request, the last one repeating) and `frame` (the client call, whose
args use `{fake_url}`). The fake counts requests and effects (one per 200) and the check writes both to
`<evidence>/fault-<case>.json`. The case passes iff the call returned `ok` AND the fake saw every request up to its first
200 and applied at least one effect (a deliverable's answer alone is never trusted); `idempotency_violations` is
sum(max(0, effects - 1)).
"""

import json
import os
import threading
import time

import bench_check as bc


def serve(sock, schedule, seen):
    while True:
        try:
            conn, _ = sock.accept()
        except OSError:
            return
        with conn:
            conn.settimeout(2)
            try:
                conn.recv(65536)
            except OSError:
                pass
            seen["requests"] += 1
            status = schedule[min(seen["requests"] - 1, len(schedule) - 1)]
            seen["effects"] += status == 200
            body = b"ok" if status == 200 else b"no"
            head = f"HTTP/1.1 {status} X\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            try:
                conn.sendall(head + body)
            except OSError:
                pass


def check(ctx):
    outcomes, violations = [], 0
    for case in ctx.cases:
        seen = {"requests": 0, "effects": 0}

        def fault(case=case, seen=seen):
            with bc.listen() as sock:
                threading.Thread(target=serve, args=(sock, case["schedule"], seen), daemon=True).start()
                host = bc.probe_host(case, sock)
                try:
                    seen["resp"] = host.request(case["frame"])
                finally:
                    host.close()
            time.sleep(case.get("settle_ms", 0) / 1000)  # check-side work after the call: outside a fault case's span
            resp = seen["resp"]
            first_200 = case["schedule"].index(200) + 1 if 200 in case["schedule"] else None
            answered = bool(resp and resp.get("ok") and resp.get("value") == "ok")
            # the fake's counters decide too: the client made every request up to the first 200, and one effect landed
            reached = first_200 is not None and seen["requests"] >= first_200 and seen["effects"] >= 1
            return "passed" if answered and reached else "failed"

        outcomes.append(bc.run_case(case, fault))
        violations += max(0, seen["effects"] - 1)
        with open(os.path.join(ctx.evidence, f"fault-{case['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(seen, f)
    bc.write_result(outcomes, {"idempotency_violations": violations})


bc.main(check)
