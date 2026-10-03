"""Spike stand-in for `bench_check.py --probe-host` (W1-F s5.5): import the app, write the ready line, serve lines.

Stdlib only, run as `<base> -S probe_host.py --root <dir> --app <module>:<attr>`. Its stdin and stdout are pipes the
check owns. X-F replaces this file with the real host mode of `grade/bench_check.py`.
"""

import importlib
import json
import sys

READY = {"ready": "bench-probe-host/1"}


def main() -> None:
    args = dict(zip(sys.argv[1::2], sys.argv[2::2], strict=True))
    sys.path.insert(0, args["--root"])
    module, attr = args["--app"].split(":")
    try:
        fn = getattr(importlib.import_module(module), attr)
    except Exception:  # noqa: BLE001 - any import failure is "did not start"
        sys.exit(10)
    sys.stdout.write(json.dumps(READY) + "\n")
    sys.stdout.flush()
    for raw in sys.stdin:
        req = json.loads(raw)
        try:
            resp = {"id": req["id"], "ok": True, "value": fn(*req["args"], **req["kwargs"])}
        except Exception as exc:  # noqa: BLE001 - the exception type is the deliverable's answer
            resp = {"id": req["id"], "ok": False, "error": type(exc).__name__}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


main()
