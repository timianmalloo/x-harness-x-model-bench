"""Small deliverables for the probe-host tests: a hang, and a grandchild with default stdio (RF-11)."""

import subprocess
import sys
import time

TOKEN = "grandchild-token-7f3a"


def hang(payload):
    time.sleep(600)


def slow(payload):
    time.sleep(0.9)
    return "safe"


def spawn_grandchild(payload):
    # RF-11: no creationflags on purpose (allowlisted in tests/test_console_windows.py). CREATE_NO_WINDOW gives the
    # grandchild its own console whatever its host is, so an attached host's stdout would never reach it and RF-11
    # survives. SW_HIDE hides the new console a detached host's grandchild gets; it does not stop an attached one.
    hidden = (subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0)
              if sys.platform == "win32" else None)
    subprocess.run([sys.executable, "-c", f"import sys; sys.stdout.write({TOKEN!r}); sys.stdout.flush()"], check=False,
                   startupinfo=hidden)
    return "safe"
