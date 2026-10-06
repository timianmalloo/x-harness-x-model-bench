# Log collector

The log collector stores batches of log records.

## `POST /v1/logs`

Request body, JSON: `{"batch_id": <string>, "records": [<object>, ...]}`.

Reply on success: status `200` and the JSON body `{"accepted": <int>}`, the number of records the collector stored.

A batch whose `batch_id` the collector has already seen is accepted without being stored again: the collector replies with
status `200` and the `accepted` count of the first batch that carried that `batch_id`.

Failures: a status in the `5xx` range may be temporary. A status in the `4xx` range is final: the collector refused the
batch and the same batch will be refused again.
