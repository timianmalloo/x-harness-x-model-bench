# W0 section 2 (rev 6.6): one top-level VARIANTS literal, read with ast.literal_eval, never executed.
# Check-based task, so `flips` lists the case ids whose outcome differs from the reference's (all passed) and `clauses`
# maps each flipped case id to the clause the check records. `edits` apply to the reference overlay, each `old` exactly once.
# Every variant keeps all six hidden tests green; the first run measures the table (W1-L Erratum 1, R2-5).
VARIANTS = {
    "noretry": {
        "flips": ["f-5xx-burst"],
        "clauses": {"f-5xx-burst": "effect"},
        "edits": [{"file": "prometheus_client/ledger.py", "old": "ATTEMPTS = 3\n", "new": "ATTEMPTS = 1\n"}]},
    "notimeout": {
        "flips": ["f-hang", "f-recover", "f-slow-first"],
        "clauses": {"f-hang": "time", "f-recover": "time", "f-slow-first": "time"},
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": "timeout=left / (ATTEMPTS - attempt)", "new": "timeout=None"}]},
    "attempt3s": {
        "flips": ["f-hang", "f-recover"],
        "clauses": {"f-hang": "time", "f-recover": "time"},
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": "timeout=left / (ATTEMPTS - attempt)", "new": "timeout=3.0"},
                  {"file": "prometheus_client/ledger.py", "old": "DEADLINE = 2.9\n", "new": "DEADLINE = 3600.0\n"}]},
    "retry5": {
        "flips": ["f-5xx-persistent", "f-hang", "f-recover"],
        "clauses": {"f-5xx-persistent": "requests", "f-hang": "requests", "f-recover": "requests"},
        "edits": [{"file": "prometheus_client/ledger.py", "old": "ATTEMPTS = 3\n", "new": "ATTEMPTS = 5\n"}]},
    "nokey": {
        "flips": ["f-lost-response", "f-slow-first"],
        "clauses": {"f-lost-response": "effect", "f-slow-first": "effect"},
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": ', "Idempotency-Key": key', "new": ""}]},
    "retry4xx": {
        "flips": ["f-4xx"],
        "clauses": {"f-4xx": "requests"},
        "edits": [{"file": "prometheus_client/ledger.py",
                   "old": "        return exc.code >= 500\n", "new": "        return True\n"}]},
    "cacheerror": {
        "flips": ["f-recover"],
        "clauses": {"f-recover": "result"},
        "edits": [{"file": "prometheus_client/ledger.py", "old": "ATTEMPTS = 3\n", "new": "ATTEMPTS = 3\n_failed = None\n"},
                  {"file": "prometheus_client/ledger.py", "old": "    error = None\n",
                   "new": "    global _failed\n    if _failed is not None:\n        raise _failed\n    error = None\n"},
                  {"file": "prometheus_client/ledger.py",
                   "old": '    raise LedgerError(f"ledger did not answer in time: {error}")\n',
                   "new": '    _failed = LedgerError(f"ledger did not answer in time: {error}")\n    raise _failed\n'}]},
}
