"""Ship structlog events to the log collector described in docs/collector.md."""

import json
import time
import urllib.error
import urllib.request
import uuid

ATTEMPTS = 3
PER_ATTEMPT = 0.9
PAUSE = 0.05


class ShipError(Exception):
    """The collector refused a batch or could not be reached."""


class HttpShipper:
    def __init__(self, base_url):
        self._url = base_url.rstrip("/") + "/v1/logs"
        self._buffer = []
        self._pending = None

    def processor(self, logger, name, event_dict):
        self._buffer.append(dict(event_dict))
        return event_dict

    def flush(self):
        sent = 0
        for _ in range(2):                       # the pending batch first, then the records buffered since
            if self._pending is None:
                if not self._buffer:
                    break
                self._pending = (uuid.uuid4().hex, self._buffer[:])
                self._buffer.clear()
            sent += self._ship(*self._pending)
            self._pending = None
        return sent

    def _ship(self, batch_id, records):
        data = json.dumps({"batch_id": batch_id, "records": records}, default=str).encode("utf-8")
        last = None
        for attempt in range(ATTEMPTS):
            if attempt:
                time.sleep(PAUSE)
            try:
                request = urllib.request.Request(
                    self._url, data=data, method="POST", headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=PER_ATTEMPT) as response:
                    return int(json.loads(response.read())["accepted"])
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    raise ShipError(f"refused with {exc.code}") from exc
                last = exc
                continue
            except (TimeoutError, ConnectionResetError, ConnectionAbortedError) as exc:
                last = exc
                continue
            except urllib.error.URLError as exc:
                if not isinstance(exc.reason, (TimeoutError, ConnectionResetError, ConnectionAbortedError)):
                    raise ShipError(f"unreachable: {exc.reason}") from exc
                last = exc
                continue
            except (ValueError, KeyError, TypeError) as exc:
                raise ShipError("collector reply has no count") from exc
        raise ShipError(f"no answer: {last}")
