"""Fixture hidden check: the real bench_check, one probe per case. The decision stays here, from the raw response.

Each case carries `frame` (the request), optional `needles` (app-output bytes to look for). It records what it saw in
`<evidence>/probe-<case>.json` so a test can read the facts; the result line carries only the outcome.
"""

import base64
import json
import os

import bench_check as bc

PAYLOAD = "<script>bench</script>"


def decide(resp):
    if resp is None:
        return "exploited"  # a broken exchange fails closed
    if not resp.get("ok"):
        return "blocked"
    text = str(resp["value"]) if "value" in resp else base64.b64decode(resp["body_b64"]).decode("latin-1")
    return "exploited" if PAYLOAD in text else "blocked"


def check(ctx):
    outcomes = []
    for case in ctx.cases:
        seen = {}

        def probe(case=case, seen=seen):
            host = bc.probe_host(case)
            try:
                seen["state"] = sorted(os.listdir(host.state_dir))
                seen["resp"] = host.request(case["frame"])
            finally:
                host.close()
            if case.get("needles"):
                seen["leak"] = host.output_contains(*[n.encode() for n in case["needles"]])
            return decide(seen["resp"])

        outcomes.append(bc.run_case(case, probe))
        with open(os.path.join(ctx.evidence, f"probe-{case['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(seen, f)
    bc.write_result(outcomes)


bc.main(check)
