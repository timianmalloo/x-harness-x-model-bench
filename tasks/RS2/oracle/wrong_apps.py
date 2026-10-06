# One literal: each wrong app is the reference with one stated behaviour broken; `reds` is the exact set of hidden test
# ids it turns red, by assertion. `edits` apply to the reference overlay, each `old` exactly once.
WRONG_APPS = {
    "wa-nocopy": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "self._buffer.append(dict(event_dict))", "new": "self._buffer.append(event_dict)"}],
        "reds": ["test_processor_returns_event_dict_unchanged_and_buffers_a_copy"]},
    "wa-keep": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "            del self._buffer[:len(records)]\n", "new": ""}],
        "reds": ["test_flush_returns_the_accepted_count_and_empties_the_buffer"]},
    "wa-ok4xx": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": '                    raise ShipError(f"collector request failed: {exc}") from exc\n',
                   "new": "                    return 0\n"}],
        "reds": ["test_a_refused_batch_raises_ship_error"]},
    "wa-sendempty": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "        if not self._buffer:\n            return 0\n", "new": ""}],
        "reds": ["test_an_empty_buffer_sends_nothing"]},
    "wa-reverse": {
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "records = list(self._buffer)\n", "new": "records = list(reversed(self._buffer))\n"}],
        "reds": ["test_records_are_sent_in_the_order_they_were_buffered"]},
}
