"""The egress gate (US-47, ADR-0005): every payload the bench sends to a judge passes `check` first.

In-process and offline: it reads a string and returns a `Verdict`. It opens no connection and starts
no process. The gateway (row 17, `harness_bench.gateway`) calls it and hands the payload on only
through `Verdict.release`, which never calls the backend for a withheld payload.

Canonicalization contract (Codex F1). The scan reads every *view* of the payload, not only the text as sent:
the payload itself; each layer of NFKC normalization, HTML entities, JSON string escapes and URL
percent-encoding, applied until the text stops changing; the text with control and format characters (Cc, Cf:
NUL, BOM, zero-width space, soft hyphen) removed; and the base64 / base64url runs in any view that decode to
mostly-printable text (errors replaced, NULs and non-printables stripped), followed the same way. Exact values
(credentials, canaries) also match across whitespace and line splits. A payload whose views are still changing
after MAX_LAYERS layers, or that yields more than MAX_VIEWS views, is withheld as `unscannable` (fail closed).
Not decoded, and so a residual: ROT-n, compression, encryption, and a value spread over separately-encoded pieces.

For slice 2 (US-47 c3): the capture test must plant the canary in the payload as the gateway assembles it
(rubric, delimited artifact, oracle), not in a string handed to `check` directly, or it proves only this module.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import re
import unicodedata
import urllib.parse
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from harness_bench.report import html as report_html
from harness_bench.report.credentials import encodings

WITHHELD = "withheld: sensitive content"
DESTINATION = re.compile(r"[a-z][a-z0-9._-]{0,31}(?::[a-z0-9._-]{1,31})?")
CLASSES = ("credential", "token_shape", "token_prefix", "email", "username", "home_path", "canary", "unscannable")
# Shapes the report's scan (report/html.py SECRET_SHAPES) does not yet name (D&P Major 2).
EXTRA_SHAPES = (
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),  # GitHub fine-grained tokens
    re.compile(r"\bxai-[A-Za-z0-9]{20,}"),  # xAI keys
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}"),  # Google API keys
)
# The report's shapes and the extra ones, in any case (an upper-cased token is still a token, Codex F1).
SHAPES = tuple(re.compile(p.pattern, re.IGNORECASE) for p in (*report_html.SECRET_SHAPES, *EXTRA_SHAPES))
TOKEN_BODY = r"[A-Za-z0-9_\-]{16,}"  # after an operator prefix: a token body, not prose about the prefix
# simplify: fixed bounds; raise them if a real judge payload is ever withheld as unscannable.
MAX_LAYERS = 4
MAX_VIEWS = 64
PRINTABLE_SHARE = 0.8  # simplify: a decoded run at least this printable is text; tune on a real false view

T = TypeVar("T")

_B64_RUN = re.compile(r"[A-Za-z0-9+/_-]{8,}={0,2}")
_JSON_ESCAPE = re.compile(r"\\(u[0-9a-fA-F]{4}|[\\/\"bfnrt])")
_JSON_CHARS = {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


@dataclass(frozen=True)
class Verdict:
    """The result of one scan. A hit names only its classes, never the matched value."""

    destination: str
    payload_sha256: str
    classes: tuple[str, ...]
    payload: str | None = field(repr=False)
    scanned: tuple[str, ...] = ()

    def record(self) -> dict:
        """The ledger shape: the destination id, the digest and the class names; never the payload."""
        return {"destination": self.destination, "payload_sha256": self.payload_sha256, "classes": self.classes,
                "scanned": self.scanned}

    @property
    def withheld(self) -> bool:
        return bool(self.classes)

    @property
    def reason(self) -> str | None:
        return WITHHELD if self.withheld else None

    def release(self, backend: Callable[[str], T]) -> T | None:
        """Hand the payload to `backend` when it is clean; a withheld payload never reaches it."""
        if self.withheld or self.payload is None:
            return None
        return backend(self.payload)


@dataclass(frozen=True)
class Operator:
    """The operator's identifiers, supplied at run time and never committed (the origin repo is public, R-42)."""

    email: str = field(repr=False)
    username: str = field(repr=False)
    home: str = field(repr=False)

    def __post_init__(self) -> None:
        # An empty identifier would be "not scanned" while the verdict reads "clean" (D&P, R-60 c4).
        if not all(v.strip() for v in (self.email, self.username, self.home)):
            raise ValueError("Operator: email, username and home are all required and non-empty")


def _json_unescape(text: str) -> str:
    def one(m: re.Match) -> str:
        e = m.group(1)
        return chr(int(e[1:], 16)) if e[0] == "u" else _JSON_CHARS.get(e, e)
    return _JSON_ESCAPE.sub(one, text)


def _decode_layer(text: str) -> str:
    """One layer of each supported text decoding, in a fixed order."""
    return urllib.parse.unquote(_json_unescape(html.unescape(unicodedata.normalize("NFKC", text))))


def _printable(raw: bytes) -> str:
    """`raw` as text with its non-printable characters removed, when it is mostly text; "" when it is noise.

    Decoded with errors="replace" and NULs set aside (UTF-16 text read as UTF-8), so one bad byte or UTF-16 no
    longer drops the whole run (Fable Major 3). Noise (the decoding of an ordinary word) is mostly non-printable.
    """
    decoded = raw.decode("utf-8", errors="replace").replace("\0", "")
    kept = "".join(c for c in decoded if (c.isprintable() or c.isspace()) and c != "\ufffd")
    return kept if kept and len(kept) >= PRINTABLE_SHARE * len(decoded) else ""


def _base64_text(text: str) -> str:
    """The base64 / base64url runs in `text` that decode to mostly-printable text, one per line."""
    out = []
    for run in _B64_RUN.findall(text):
        body = run.rstrip("=").replace("-", "+").replace("_", "/")
        if len(body) % 4 == 1:
            continue
        try:
            raw = base64.b64decode(body + "=" * (-len(body) % 4), validate=True)
        except binascii.Error:
            continue
        out.append(_printable(raw))
    return "\n".join(o for o in out if o)


def _controls_removed(text: str) -> str:
    """The text without control and format characters (Cc, Cf: NUL, BOM, zero-width space, soft hyphen), keeping
    whitespace, so a value interleaved with them still matches (Fable Major 3)."""
    return "".join(c for c in text if c.isspace() or unicodedata.category(c) not in ("Cc", "Cf"))


def _views(payload: str) -> tuple[list[str], bool]:
    """Every view of the payload (the contract above), and False when a bound was hit (unscannable)."""
    views: list[str] = []
    queue, seen = [(payload, 0)], set()
    while queue:
        text, depth = queue.pop()
        if text in seen:
            continue
        if depth > MAX_LAYERS or len(views) >= MAX_VIEWS:
            return views, False
        seen.add(text)
        views.append(text)
        for derived in (_decode_layer(text), _base64_text(text), _controls_removed(text)):
            if derived and derived != text:
                queue.append((derived, depth + 1))
    return views, True


def _ws(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _exact(views: list[str], values: Sequence[str]) -> bool:
    """Any value, or its base64 or URL-encoded form (report.credentials.encodings), in any view, also across
    whitespace and line splits."""
    forms = encodings({v for v in values if v.strip()})
    return any(f in v or _ws(f) in _ws(v) for v in views for f in forms)


def _encoded(views: list[str], value: str) -> bool:
    """The base64 or URL-encoded form of an identifier (D&P: identifiers pass through encodings() too)."""
    return any(f in v for v in views for f in encodings({value}) - {value})


def _anycase(views: list[str], value: str) -> bool:
    """The value in any view ignoring case (an email's domain is case-insensitive), or an encoded form."""
    return any(value.casefold() in v.casefold() for v in views) or _encoded(views, value)


def _word(views: list[str], value: str) -> bool:
    """The value as a whole word (no letter or digit on either side) in any view ignoring case, or encoded."""
    word = re.compile(rf"(?<![^\W_]){re.escape(value)}(?![^\W_])", re.IGNORECASE)
    return any(word.search(v) for v in views) or _encoded(views, value)


def _path_form(text: str) -> str:
    """Casefolded, with every run of slashes or backslashes as one "/" (so JSON-escaped paths match too)."""
    return re.sub(r"[\\/]+", "/", text.casefold())


def _path(views: list[str], value: str) -> bool:
    """The path in any view, in any separator form or case, as a POSIX drive path (`/c/...`, which
    `/mnt/c/...` contains), or encoded."""
    forms = {_path_form(value)}
    drive = re.fullmatch(r"([a-z]):(/.*)", _path_form(value))
    if drive:
        forms.add(f"/{drive.group(1)}{drive.group(2)}")
    return any(f in _path_form(v) or _ws(f) in _ws(_path_form(v)) for v in views for f in forms) or \
        _encoded(views, value)


def check(payload: str, *, destination: str, operator: Operator, secrets: Sequence[str] = (),
          canaries: Sequence[str] = (), token_prefixes: Sequence[str] = ()) -> Verdict:
    """Scan every view of `payload` bound for `destination`.

    Every value is supplied by the caller at run time and is never stored or returned: `secrets` are the
    credential values the host holds; `operator` identifies the operator; `canaries` are the planted
    US-13/US-48 markers; `token_prefixes` are the operator's own token prefixes. A hit returns a withheld
    verdict: no payload, only its sha256, the destination and the class names. `scanned` names each class
    that ran, so "clean" never reads the same as "not scanned".
    """
    def hits(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        views, complete = _views(text)
        scans = {
            "credential": (lambda: _exact(views, secrets)) if secrets else None,
            "token_shape": lambda: any(p.search(v) for v in views for p in SHAPES),
            "token_prefix": (lambda: any(re.search(re.escape(p) + TOKEN_BODY, v, re.IGNORECASE)
                                         for v in views for p in token_prefixes if p.strip()))
            if token_prefixes else None,
            "email": lambda: _anycase(views, operator.email),
            "username": lambda: _word(views, operator.username),
            "home_path": lambda: _path(views, operator.home),
            "canary": (lambda: _exact(views, canaries)) if canaries else None,
        }
        scanned = tuple(name for name in CLASSES if scans.get(name))
        found = tuple(name for name in scanned if scans[name]())
        return found + (() if complete else ("unscannable",)), scanned

    # The destination is a fixed backend id (Codex F3): it must not be able to carry content into a record.
    if not DESTINATION.fullmatch(destination) or hits(destination)[0]:
        raise ValueError("destination is not a safe backend id (lower-case name[:qualifier], at most 64 characters)")
    classes, scanned = hits(payload)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return Verdict(destination=destination, payload_sha256=digest, classes=classes,
                   payload=None if classes else payload, scanned=scanned)
