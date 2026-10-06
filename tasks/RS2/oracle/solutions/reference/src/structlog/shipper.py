"""Ship structlog events to the log collector described in docs/collector.md."""

import json
import time
import urllib.error
import urllib.request
import uuid

ATTEMPTS = 3
DEADLINE = 2.9


class ShipError(Exception):
    """The collector refused a batch or could not be reached."""


def _transient(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, (TimeoutError, ConnectionResetError, ConnectionAbortedError))


class HttpShipper:
    def __init__(self, base_url):
        self._url = base_url.rstrip("/") + "/v1/logs"
        self._buffer = []
        self._batch_id = None

    def processor(self, logger, name, event_dict):
        self._buffer.append(dict(event_dict))
        return event_dict

    def flush(self):
        if not self._buffer:
            return 0
        records = list(self._buffer)
        if self._batch_id is None:
            self._batch_id = uuid.uuid4().hex
        deadline = time.monotonic() + DEADLINE
        error = None
        for attempt in range(ATTEMPTS):
            left = deadline - time.monotonic()
            if left <= 0:
                break
            data = json.dumps({"batch_id": self._batch_id, "records": records}, default=str).encode("utf-8")
            request = urllib.request.Request(
                self._url, data=data, method="POST", headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=left / (ATTEMPTS - attempt)) as response:
                    payload = response.read()
            except OSError as exc:
                if isinstance(exc, urllib.error.HTTPError):
                    exc.close()
                if not _transient(exc):
                    raise ShipError(f"collector request failed: {exc}") from exc
                error = exc
                continue
            try:
                accepted = int(json.loads(payload)["accepted"])
            except (ValueError, KeyError, TypeError) as exc:
                raise ShipError("collector reply has no count") from exc
            del self._buffer[:len(records)]
            self._batch_id = None
            return accepted
        raise ShipError(f"collector did not answer in time: {error}")
