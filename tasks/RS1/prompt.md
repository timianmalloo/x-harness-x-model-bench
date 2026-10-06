Add a module `prometheus_client/ledger.py` with a function `post_event(base_url, name, value)`.

It sends the event to `<base_url>/v1/events`, as described in `docs/ledger-service.md`, and returns the new event's `id` as an `int`. It raises `LedgerError` (a class defined in the same module) when the service refuses the event or cannot be reached. A call must return or raise within 3 seconds, and must send at most 3 requests to the service.

Add tests for it to `tests/test_ledger.py`.
