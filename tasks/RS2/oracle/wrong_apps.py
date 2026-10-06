# One literal: each wrong app is the reference with one stated behaviour broken; `reds` is the exact set of hidden test
# ids it turns red, by assertion. `edits` apply to the reference overlay, each `old` exactly once.
WRONG_APPS = {
    "wa-nocopy": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "self._buffer.append(dict(event_dict))", "new": "self._buffer.append(event_dict)"}],
        "reds": ["test_processor_returns_event_dict_unchanged_and_buffers_a_copy"]},
    "wa-keep": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "            self._pending = None\n        return sent\n",
                   "new": "            self._pending = None\n            self._buffer[:] = records\n            break\n        return sent\n"}],
        "reds": ["test_flush_returns_the_accepted_count_and_empties_the_buffer"]},
    "wa-ok4xx": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": '                    raise ShipError(f"collector request failed: {exc}") from exc\n',
                   "new": "                    return 0\n"}],
        "reds": ["test_a_refused_batch_raises_ship_error"]},
    "wa-sendempty": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "                if not self._buffer:\n                    break\n",
                   "new": "                if not self._buffer and sent:\n                    break\n"}],
        "reds": ["test_an_empty_buffer_sends_nothing"]},
    "wa-reverse": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "self._pending = (uuid.uuid4().hex, self._buffer[:])\n", "new": "self._pending = (uuid.uuid4().hex, self._buffer[::-1])\n"}],
        "reds": ["test_records_are_sent_in_the_order_they_were_buffered"]},
}
