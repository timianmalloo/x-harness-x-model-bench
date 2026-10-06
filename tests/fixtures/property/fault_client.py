"""Fixture client deliverable for a shape (b) loopback task: calls a URL the check gives it as `{fake_url}`."""

import time
import urllib.error
import urllib.request

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch(url, pause=0.3):
    """GET with up to three attempts; a 5xx is retried after `pause`, a 4xx is not."""
    for attempt in range(3):
        try:
            with _OPENER.open(url, timeout=2) as resp:
                return resp.read().decode()
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == 2:
                raise
            time.sleep(pause)
    return None


def twice(url):
    """Two logical calls: two effects at a fake that applies one per 200."""
    fetch(url)
    return fetch(url)


def hang(url):
    time.sleep(30)
