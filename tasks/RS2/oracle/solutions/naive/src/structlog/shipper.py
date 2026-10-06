"""Ship structlog events to the log collector described in docs/collector.md."""

import json
import urllib.request
import uuid


class ShipError(Exception):
    """The collector refused a batch or could not be reached."""


class HttpShipper:
    def __init__(self, base_url):
        self._url = base_url.rstrip("/") + "/v1/logs"
        self._buffer = []

    def processor(self, logger, name, event_dict):
        self._buffer.append(dict(event_dict))
        return event_dict

    def flush(self):
        if not self._buffer:
            return 0
        records = list(self._buffer)
        data = json.dumps({"batch_id": uuid.uuid4().hex, "records": records}, default=str).encode("utf-8")
        request = urllib.request.Request(self._url, data=data, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                accepted = int(json.loads(response.read())["accepted"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ShipError(str(exc)) from exc
        del self._buffer[:len(records)]
        return accepted
