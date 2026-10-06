"""Check-supplied frame handler for RS2 (HttpShipper is a class, and a probe-host app must be one callable).

Loaded by the probe host as the app `rs2_shim:handle`; the check puts the deliverable's `src` and this folder on the host's
`paths`. The host keeps one process per case, so the shipper lives in this module's state between the check's calls:
`start(base_url)` builds it, `add(names)` runs the deliverable's `processor` once per name, `flush()` returns its result.
A raised exception is reported by the host as `{ok: false, error: <type name>}`. Stdlib and the deliverable only.
"""

_shipper = None


def handle(op, arg=None):
    global _shipper
    if op == "start":
        from structlog.shipper import HttpShipper
        _shipper = HttpShipper(arg)
        return None
    if op == "add":
        for name in arg:
            _shipper.processor(None, "info", {"event": name})
        return None
    if op == "flush":
        return _shipper.flush()
    raise ValueError(op)
