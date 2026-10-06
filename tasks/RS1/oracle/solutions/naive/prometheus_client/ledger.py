"""Post events to the ledger service described in docs/ledger-service.md."""

import json
import urllib.request


class LedgerError(Exception):
    """The ledger service refused an event or could not be reached."""


def post_event(base_url, name, value):
    body = json.dumps({"name": name, "value": value}).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/events", data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request) as response:
            return int(json.loads(response.read())["id"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise LedgerError(str(exc)) from exc
