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


@pytest.mark.parametrize("make", [
    lambda: "sk-ant-" + token_hex(16),
    lambda: "sk-proj-" + token_hex(20),
    lambda: "ghp_" + token_hex(18),
    lambda: "eyJ" + ".".join(token_hex(8) for _ in range(3)),
], ids=["anthropic", "openai", "github", "jwt"])
def test_a_token_shaped_string_is_withheld(make):
    # Each value is random hex in a known token's shape: it matches the pattern and authenticates nothing.
    text = _plant(make())
    verdict = egress.check(text, destination=DEST)
    assert verdict.classes == ("token_shape",)
    assert (verdict.reason, verdict.payload_sha256) == ("withheld: sensitive content", _sha(text))


@pytest.mark.parametrize("form", [str, str.upper], ids=["as-given", "other-case"])
def test_the_operators_email_is_withheld_in_any_case(form):
    email = f"operator-{token_hex(6)}@example.invalid"  # RFC 2606 .invalid: never a real mailbox
    text = _plant(f"Contact: {form(email)}")
    verdict = egress.check(text, destination=DEST, email=email)
    assert verdict.classes == ("email",)
    assert (verdict.reason, verdict.payload_sha256) == ("withheld: sensitive content", _sha(text))


@pytest.mark.parametrize("context", ["by {u}.", "owner={U}", "/srv/{u}/work"], ids=["prose", "other-case", "path"])
def test_the_operators_username_is_withheld_as_a_whole_word(context):
    username = f"op{token_hex(4)}"
    text = _plant(context.format(u=username, U=username.upper()))
    verdict = egress.check(text, destination=DEST, username=username)
    assert verdict.classes == ("username",)
    assert (verdict.reason, verdict.payload_sha256) == ("withheld: sensitive content", _sha(text))
    # Inside a longer word it is not the username (a short name would otherwise withhold ordinary prose).
    assert egress.check(_plant(f"{username}9z"), destination=DEST, username=username).classes == ()


@pytest.mark.parametrize("form", [
    lambda h: h + "\\projects\\repo\\main.py",
    lambda h: h.replace("\\", "/") + "/projects",
    lambda h: h.replace("\\", "\\\\"),
    str.lower,
], ids=["backslash", "forward-slash", "json-escaped", "other-case"])
def test_the_operators_home_path_is_withheld_in_any_separator_form(form):
    home = f"C:\\Users\\egress-{token_hex(4)}"  # a synthetic folder name; no real home is read
    text = _plant(f"cwd: {form(home)}")
    verdict = egress.check(text, destination=DEST, home=home)
    assert verdict.classes == ("home_path",)
    assert (verdict.reason, verdict.payload_sha256) == ("withheld: sensitive content", _sha(text))


@pytest.mark.parametrize("encode", [
    lambda v: v,
    lambda v: base64.b64encode(v.encode("utf-8")).decode("ascii"),
], ids=["plain", "base64"])
def test_a_planted_canary_is_withheld(encode):
    canary = f"CANARY-{token_hex(8)}"
    text = _plant(encode(canary))
    verdict = egress.check(text, destination=DEST, canaries=[canary])
    assert verdict.classes == ("canary",)
    assert (verdict.reason, verdict.payload_sha256) == ("withheld: sensitive content", _sha(text))


def test_a_withheld_payload_never_reaches_the_backend():
    value = _credential()
    backend = FakeBackend()
    verdict = egress.check(_plant(value), destination=DEST, secrets=[value])
    assert verdict.release(backend) is None
    assert backend.received == []
    assert verdict.payload is None
    assert value not in repr(verdict)
