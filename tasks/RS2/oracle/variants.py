# W0 section 2 (rev 6.6): one top-level VARIANTS literal, read with ast.literal_eval, never executed.
# Check-based task, so `flips` lists the case ids whose outcome differs from the reference's (all passed) and `clauses`
# maps each flipped case id to the clause the check records. `edits` apply to the reference overlay, each `old` exactly once.
# Every variant keeps all five hidden tests green; the first run measures the table (W1-L Erratum 1, R2-5, R2-6).
VARIANTS = {
    'noretry': {'flips': ['g-5xx-burst'], 'clauses': {'g-5xx-burst': 'effect'},
    'edits': [{'file': 'src/structlog/shipper.py', 'old': 'ATTEMPTS = 3\n', 'new': 'ATTEMPTS = 1\n'}]},
    'notimeout': {'flips': ['g-hang', 'g-slow-first'], 'clauses': {'g-hang': 'time', 'g-slow-first': 'time'},
    'edits': [{'file': 'src/structlog/shipper.py', 'old': 'timeout=left / (ATTEMPTS - attempt)', 'new': 'timeout=None'}]},
    'retry5': {'flips': ['g-5xx-persistent', 'g-hang', 'g-lost-then-grow', 'g-ordering'], 'clauses': {'g-5xx-persistent': 'requests', 'g-hang': 'requests', 'g-lost-then-grow': 'requests', 'g-ordering': 'requests'},
    'edits': [{'file': 'src/structlog/shipper.py', 'old': 'ATTEMPTS = 3\n', 'new': 'ATTEMPTS = 5\n'}]},
    'batchidattempt': {'flips': ['g-lost-response', 'g-lost-then-grow', 'g-slow-first'], 'clauses': {'g-lost-response': 'effect', 'g-lost-then-grow': 'effect', 'g-slow-first': 'effect'},
    'edits': [{'file': 'src/structlog/shipper.py', 'old': '{"batch_id": batch_id, "records": records}', 'new': '{"batch_id": uuid.uuid4().hex, "records": records}'}]},
    'clearearly': {'flips': ['g-5xx-persistent', 'g-lost-then-grow', 'g-ordering'], 'clauses': {'g-5xx-persistent': 'result', 'g-lost-then-grow': 'result', 'g-ordering': 'result'},
    'edits': [{'file': 'src/structlog/shipper.py', 'old': '            sent += self._send(batch_id, records, deadline)\n', 'new': '            self._pending = None\n            sent += self._send(batch_id, records, deadline)\n'}]},
    'requeuetail': {'flips': ['g-lost-then-grow', 'g-ordering'], 'clauses': {'g-lost-then-grow': 'result', 'g-ordering': 'result'},
    'edits': [{'file': 'src/structlog/shipper.py', 'old': '            if self._pending is None:\n                if not self._buffer:\n', 'new': '            if self._pending is not None and self._buffer:\n                self._pending = (uuid.uuid4().hex, self._buffer + self._pending[1])\n                self._buffer.clear()\n            if self._pending is None:\n                if not self._buffer:\n'}]},
    'retry4xx': {'flips': ['g-4xx'], 'clauses': {'g-4xx': 'requests'},
    'edits': [{'file': 'src/structlog/shipper.py', 'old': '        return exc.code >= 500\n', 'new': '        return True\n'}]},
    'growid': {'flips': ['g-lost-then-grow'], 'clauses': {'g-lost-then-grow': 'result'},
    'edits': [{'file': 'src/structlog/shipper.py', 'old': '        self._buffer = []\n        self._pending = None\n', 'new': '        self._buffer = []\n        self._batch_id = None\n'}, {'file': 'src/structlog/shipper.py', 'old': '        sent = 0\n        for _ in range(2):                       # the pending batch first, then the records buffered since\n            if self._pending is None:\n                if not self._buffer:\n                    break\n                self._pending = (uuid.uuid4().hex, self._buffer[:])\n                self._buffer.clear()\n            batch_id, records = self._pending\n            sent += self._send(batch_id, records, deadline)\n            self._pending = None\n        return sent\n', 'new': '        if not self._buffer:\n            return 0\n        if self._batch_id is None:\n            self._batch_id = uuid.uuid4().hex\n        records = list(self._buffer)\n        accepted = self._send(self._batch_id, records, deadline)\n        del self._buffer[:len(records)]\n        self._batch_id = None\n        return accepted\n'}]}}
