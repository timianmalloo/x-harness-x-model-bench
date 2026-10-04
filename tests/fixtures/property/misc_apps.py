"""Small deliverables for the probe-host tests: a hang, and a grandchild with default stdio (RF-11)."""

import subprocess
import sys
import time

TOKEN = "grandchild-token-7f3a"


def hang(payload):
    time.sleep(600)


def spawn_grandchild(payload):
    subprocess.run([sys.executable, "-c", f"import sys; sys.stdout.write({TOKEN!r}); sys.stdout.flush()"], check=False)
    return "safe"
