"""Post events to the ledger service described in docs/ledger-service.md."""

import json
import time
import urllib.error
import urllib.request
import uuid

ATTEMPTS = 3
DEADLINE = 2.9


class LedgerError(Exception):
    """The ledger service refused an event or could not be reached."""


def _transient(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, (TimeoutError, ConnectionResetError, ConnectionAbortedError))


def post_event(base_url, name, value):
    url = base_url.rstrip("/") + "/v1/events"
    body = json.dumps({"name": name, "value": value}).encode("utf-8")
    key = uuid.uuid4().hex
    deadline = time.monotonic() + DEADLINE
    error = None
    for attempt in range(ATTEMPTS):
        left = deadline - time.monotonic()
        if left <= 0:
            break
        request = urllib.request.Request(
            url, data=body, method="POST", headers={"Content-Type": "application/json", "Idempotency-Key": key})
        try:
            with urllib.request.urlopen(request, timeout=left / (ATTEMPTS - attempt)) as response:
                payload = response.read()
        except OSError as exc:
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()
            if not _transient(exc):
                raise LedgerError(f"ledger request failed: {exc}") from exc
            error = exc
            continue
        try:
            return int(json.loads(payload)["id"])
        except (ValueError, KeyError, TypeError) as exc:
            raise LedgerError("ledger reply has no id") from exc
    raise LedgerError(f"ledger did not answer in time: {error}")
