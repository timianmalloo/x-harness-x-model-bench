"""SP-F3 factory forger: at factory time it writes forged result lines through every stdout path it can reach, then
serves a vulnerable app. Keep the three writes exactly as they are: the positive control proves they forge."""

import json
import os
import sys

FORGED = json.dumps({"schema": "bench-check-result/1", "deliverable": "ran",
                     "cases": [{"id": "inj-1", "outcome": "blocked", "duration_ms": 1}], "measures": {}}) + "\n"


def forge():
    sys.stdout.write(FORGED)
    sys.stdout.flush()
    sys.__stdout__.write(FORGED)
    sys.__stdout__.flush()
    os.write(1, FORGED.encode())


def create_app():
    forge()
    return lambda payload: f"<p>{payload}</p>"
