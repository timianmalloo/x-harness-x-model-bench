# Ledger service

The ledger service records named numeric events.

## `POST /v1/events`

Request body, JSON: `{"name": <string>, "value": <number>}`.

Reply on success: status `201` and the JSON body `{"id": <int>}`, the id of the event the service created.

Header `Idempotency-Key` (optional). The first request that carries a key creates an event. A later request with the
same key creates no event: the service replies with status `200` and the `id` of the event the first request created.

Failures: a status in the `5xx` range may be temporary. A status in the `4xx` range is final: the service refused the
request and the same request will be refused again.
