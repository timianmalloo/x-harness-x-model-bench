"""Post events to the ledger service described in docs/ledger-service.md."""

import json
import time
import urllib.error
import urllib.request
import uuid

PER_ATTEMPT = 0.9
PAUSE = 0.05
ATTEMPTS = 3


class LedgerError(Exception):
    """The ledger service refused an event or could not be reached."""


def post_event(base_url, name, value):
    url = base_url.rstrip("/") + "/v1/events"
    body = json.dumps({"name": name, "value": value}).encode("utf-8")
    headers = {"Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())}
    last = None
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(PAUSE)
        try:
            request = urllib.request.Request(url, data=body, method="POST", headers=headers)
            with urllib.request.urlopen(request, timeout=PER_ATTEMPT) as response:
                return int(json.loads(response.read())["id"])
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                raise LedgerError(f"refused with {exc.code}") from exc
            last = exc
        except (TimeoutError, ConnectionResetError, ConnectionAbortedError) as exc:
            last = exc
        except urllib.error.URLError as exc:
            if not isinstance(exc.reason, (TimeoutError, ConnectionResetError, ConnectionAbortedError)):
                raise LedgerError(f"unreachable: {exc.reason}") from exc
            last = exc
        except (ValueError, KeyError, TypeError) as exc:
            raise LedgerError("ledger reply has no id") from exc
    raise LedgerError(f"no answer: {last}")
