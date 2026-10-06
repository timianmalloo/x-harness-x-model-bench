Add a module `src/structlog/shipper.py` with a class `HttpShipper(base_url)` and an exception class `ShipError`, both defined in that module.

`HttpShipper.processor(logger, name, event_dict)` is a structlog processor. It appends a copy of the event to an in-memory buffer and returns `event_dict` unchanged.

`HttpShipper.flush()` sends the buffered records in one batch to `<base_url>/v1/logs`, as described in `docs/collector.md`. On success it empties the buffer and returns the number of records the collector accepted. On failure it raises `ShipError` and keeps the records for the next flush. A flush must return or raise within 3 seconds, and must send at most 3 requests to the collector.

Add tests for it to `tests/test_shipper.py`.
