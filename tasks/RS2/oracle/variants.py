# W0 section 2 (rev 6.6): one top-level VARIANTS literal, read with ast.literal_eval, never executed.
# Check-based task, so `flips` lists the case ids whose outcome differs from the reference's (all passed) and `clauses`
# maps each flipped case id to the clause the check records. `edits` apply to the reference overlay, each `old` exactly once.
# Every variant keeps all five hidden tests green; the first run measures the table (W1-L Erratum 1, R2-5, R2-6).
VARIANTS = {
    "noretry": {
        "flips": ["g-5xx-burst"],
        "clauses": {"g-5xx-burst": "effect"},
        "edits": [{"file": "src/structlog/shipper.py", "old": "ATTEMPTS = 3\n", "new": "ATTEMPTS = 1\n"}]},
    "notimeout": {
        "flips": ["g-hang", "g-slow-first"],
        "clauses": {"g-hang": "time", "g-slow-first": "time"},
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "timeout=left / (ATTEMPTS - attempt)", "new": "timeout=None"}]},
    "retry5": {
        "flips": ["g-5xx-persistent", "g-hang", "g-ordering"],
        "clauses": {"g-5xx-persistent": "requests", "g-hang": "requests", "g-ordering": "requests"},
        "edits": [{"file": "src/structlog/shipper.py", "old": "ATTEMPTS = 3\n", "new": "ATTEMPTS = 5\n"}]},
    "batchidattempt": {
        "flips": ["g-lost-response", "g-slow-first"],
        "clauses": {"g-lost-response": "effect", "g-slow-first": "effect"},
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": '{"batch_id": self._batch_id, "records": records}',
                   "new": '{"batch_id": uuid.uuid4().hex, "records": records}'}]},
    "clearearly": {
        "flips": ["g-5xx-persistent", "g-ordering"],
        "clauses": {"g-5xx-persistent": "result", "g-ordering": "result"},
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "        records = list(self._buffer)\n", "new": "        records = list(self._buffer)\n        self._buffer.clear()\n"}]},
    "requeuetail": {
        "flips": ["g-ordering"],
        "clauses": {"g-ordering": "result"},
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "        self._buffer = []\n        self._batch_id = None\n",
                   "new": "        self._buffer = []\n        self._held = []\n        self._batch_id = None\n"},
                  {"file": "src/structlog/shipper.py",
                   "old": "        if not self._buffer:\n            return 0\n        records = list(self._buffer)\n",
                   "new": "        if not (self._buffer or self._held):\n            return 0\n        records = self._buffer + self._held\n        self._buffer, self._held = [], []\n"},
                  {"file": "src/structlog/shipper.py",
                   "old": "            del self._buffer[:len(records)]\n", "new": ""},
                  {"file": "src/structlog/shipper.py",
                   "old": '        raise ShipError(f"collector did not answer in time: {error}")\n',
                   "new": '        self._held = records\n        raise ShipError(f"collector did not answer in time: {error}")\n'}]},
    "retry4xx": {
        "flips": ["g-4xx"],
        "clauses": {"g-4xx": "requests"},
        "edits": [{"file": "src/structlog/shipper.py",
                   "old": "        return exc.code >= 500\n", "new": "        return True\n"}]},
}
