"""The egress gate (US-47, ADR-0005, ruling R-60): one test per sensitive class, plus the withhold path.

Offline only. Every sensitive value is an inert synthetic string generated here at run time; none is committed
(the origin repo is public, R-42). The backend is a plain object that records what it is handed.
"""

import base64
import hashlib
import urllib.parse
from pathlib import Path
from secrets import token_hex

import pytest

from harness_bench import egress

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAYLOAD = (FIXTURES / "egress" / "judge-payload.txt").read_text(encoding="utf-8")
DEST = "judge:fake"


class FakeBackend:
    """Stands in for a judge backend: records each payload it is handed and returns a canned verdict."""

    def __init__(self):
        self.received: list[str] = []

    def __call__(self, payload: str) -> str:
        self.received.append(payload)
        return "verdict"


def _plant(value: str) -> str:
    return PAYLOAD.replace("<<PLANT>>", value)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_clean_text_passes_unchanged_and_reaches_the_backend():
    backend = FakeBackend()
    verdict = egress.check(PAYLOAD, destination=DEST, secrets=[f"synthetic-{token_hex(16)}"])
    assert (verdict.withheld, verdict.reason, verdict.classes) == (False, None, ())
    assert verdict.payload == PAYLOAD
    assert verdict.release(backend) == "verdict"
    assert backend.received == [PAYLOAD]


def _credential() -> str:
    # Carries "/" and "+" so its URL-encoded form differs from the plain one.
    return f"synthetic/{token_hex(12)}+{token_hex(12)}"


@pytest.mark.parametrize("encode", [
    lambda v: v,
    lambda v: base64.b64encode(v.encode("utf-8")).decode("ascii"),
    lambda v: urllib.parse.quote(v, safe=""),
], ids=["plain", "base64", "url"])
def test_a_credential_value_is_withheld_in_each_encoding(encode):
    value = _credential()
    text = _plant(encode(value))
    verdict = egress.check(text, destination=DEST, secrets=[value])
    assert verdict.classes == ("credential",)
    assert verdict.reason == "withheld: sensitive content"
    assert (verdict.payload_sha256, verdict.destination) == (_sha(text), DEST)


def test_a_withheld_payload_never_reaches_the_backend():
    value = _credential()
    backend = FakeBackend()
    verdict = egress.check(_plant(value), destination=DEST, secrets=[value])
    assert verdict.release(backend) is None
    assert backend.received == []
    assert verdict.payload is None
    assert value not in repr(verdict)
