"""`report.html_builder`: escape by construction (design section 5, R1).

`el()` is the one function that emits markup from data. Every `str` child and every attribute value
is escaped through `html.escape`; the only way past that is `trusted()`, which wraps text the caller
already guarantees is safe markup (today, the output of `report/html.py`'s own `_e()`-escaped section
renderers, at the shell-assembly seam in `render()`; R2-R9 retire that call site section by section as
each renderer moves onto `el()` directly). `Html` -- the `str` subclass both return -- is the only type
that passes through a later `el()` call unescaped, so a plain `str` (agent-derived text, always a plain
`str`) can never become a tag (UIA-15). `Html(` is never called outside this module: everywhere else
goes through `el()` or `trusted()` (enforced by a structural test in `tests/test_report_builder.py`).

An attribute name starting with `on` (any case) or named `style` is refused outright: the builder does
not attempt to sanitise an event handler or a `style=""` value, because a page assembled entirely from
tokens (design section 3) never needs one. `href`/`src` values are refused when they carry a
`javascript:` scheme (design section 10, the STRIDE row on agent text -> DOM).

SVG marks (a whisker, a dot, a bar) are elements like any other; `el()` draws them the same way it draws
a `<table>` -- one generic function, not a parallel API, is the smallest correct builder (Simplifier
check: a distinct `svg_el()` would duplicate escaping and void-tag logic for no added safety).
"""

from __future__ import annotations

import base64
import hashlib
import html as _html
import re
from collections.abc import Mapping

# HTML void elements (no closing tag) plus the SVG leaf shapes emitted with no children (design
# section 5's "one mark per (series, cell)"): both render self-closed, which HTML5 also accepts on
# ordinary void elements (the slash is defined and ignored there) and *requires* for a childless
# element parsed under SVG's foreign-content rules.
_VOID = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source",
    "track", "wbr",
    "circle", "rect", "line", "path", "polygon", "polyline", "ellipse", "stop", "use",
})

_BAD_ATTR = re.compile(r"^on", re.IGNORECASE)
_JS_HREF = re.compile(r"^\s*javascript:", re.IGNORECASE)
_HREF_ATTRS = frozenset({"href", "src"})


class Html(str):
    """A `str` that `el()` will not escape again: markup already known to be safe."""


def trusted(markup: str) -> Html:
    """Wrap already-safe markup as `Html`. The one sanctioned escape hatch outside `el()`.

    Call this only on text that is itself free of unescaped agent-derived content -- markup this
    module built, or a renderer (like `report/html.py`'s existing section functions) that escapes
    every value at its own call sites. Never call it on a raw `str` that might hold agent text.
    """
    return Html(markup)


def _attr_str(name: str, value: object) -> str:
    if _BAD_ATTR.match(name) or name.lower() == "style":
        raise ValueError(f"refused: attribute {name!r} (on*/style are never emitted, design section 5)")
    if value is False or value is None:
        return ""
    if name.lower() in _HREF_ATTRS and _JS_HREF.match(str(value)):
        raise ValueError(f"refused: {name}={value!r} (javascript: scheme, design section 10)")
    if value is True:
        return f" {name}"
    return f' {name}="{_html.escape(str(value), quote=True)}"'


def el(tag: str, attrs: Mapping[str, object] | None = None, *children: str) -> Html:
    """Build one element. Every attribute value and every plain-`str` child is escaped; an `Html`
    child (already trusted) passes through unchanged. Raises `ValueError` for a refused attribute."""
    attr_text = "".join(_attr_str(k, v) for k, v in (attrs or {}).items())
    if tag in _VOID:
        if children:
            raise ValueError(f"refused: void element <{tag}> given children")
        return Html(f"<{tag}{attr_text}/>")
    inner = "".join(c if isinstance(c, Html) else _html.escape(str(c), quote=True) for c in children)
    return Html(f"<{tag}{attr_text}>{inner}</{tag}>")


def sha256_token(text: str) -> str:
    """A CSP hash-source value (`sha256-<base64 digest>`) for exactly `text`, byte for byte."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


def csp_meta(style_text: str, script_text: str | None = None) -> Html:
    """The `<meta http-equiv="Content-Security-Policy">` (design section 5): `default-src 'none'`,
    a hashed `style-src` for exactly `style_text`, and either a hashed `script-src` for `script_text`
    or `'none'` when there is no script yet (R1: `report.js` is R4's deliverable)."""
    script_src = f"'{sha256_token(script_text)}'" if script_text else "'none'"
    policy = "; ".join((
        "default-src 'none'",
        f"script-src {script_src}",
        f"style-src '{sha256_token(style_text)}'",
        "img-src data:",
        "base-uri 'none'",
        "form-action 'none'",
    ))
    return el("meta", {"http-equiv": "Content-Security-Policy", "content": policy})


def head_block(*, title: str, style_text: str, script_text: str | None = None) -> Html:
    """`<head>`, with the CSP meta as its first child (design section 5), per design section 6."""
    return el(
        "head", None,
        csp_meta(style_text, script_text),
        el("meta", {"charset": "utf-8"}),
        el("meta", {"name": "viewport", "content": "width=device-width, initial-scale=1"}),
        el("title", None, title),
        el("style", None, trusted(style_text)),
    )
