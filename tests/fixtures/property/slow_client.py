"""A client that is slow to start: its import takes one second, which the fault case's duration must not include."""

import time

time.sleep(1.0)

from fault_client import fetch  # noqa: E402,F401
