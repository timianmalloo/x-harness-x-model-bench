"""The analyst section of a generated page (ADR-0029 s7; the Leader's ruling for ADR-0027's cost-compare page).

`check_and_render(md_text, generated_numbers)` is the one number check, shared by `report.pack_cost` and
`report.cost_compare`: the analyst Markdown must pass `publish.scan_text` (no email, UUID, bearer, JWT or token
shape), and every number it cites must appear among `generated_numbers` (the numbers of the page's generated tables,
from `table_numbers`); otherwise it refuses and lists each unmatched number. It returns the section's HTML under the
heading "Analysis (written by an analyst, not generated)". The check is mechanical, never a read.

The number rule (one definition, used on both sides): a number is a run of digits with optional `,` thousands groups
and an optional decimal part, read from the rendered text (so Markdown list markers and frontmatter, which do not
render as text, are not citations). It is compared by value: `1,234`, `1234` and `1234.0` are one number; a sign or a
`%` beside it is not part of it.
"""

from __future__ import annotations

import html
import importlib.util
import re
from decimal import Decimal, InvalidOperation

from harness_bench.errors import BenchError
from harness_bench.report import publish
from harness_bench.report.html_builder import Html, el, trusted

HEADING = "Analysis (written by an analyst, not generated)"
SECTION_ID = "analysis"
NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_TAG = re.compile(r"<[^>]+>")
_TABLE = re.compile(r"<table\b.*?</table>", re.DOTALL)


def canonical(token: str) -> str:
    """One number's comparison form: thousands separators dropped, trailing zeros dropped (`1,500.0` -> `1500`)."""
    try:
        value = Decimal(token.replace(",", ""))
    except InvalidOperation:  # NUMBER only matches valid decimals; kept as a guard for a direct caller
        return token
    text = format(value.normalize(), "f")
    return text


def numbers(text: str) -> set[str]:
    """Every number in plain `text`, in canonical form."""
    return {canonical(m.group(0)) for m in NUMBER.finditer(text)}


def text_of(markup: str) -> str:
    """The visible text of `markup`: tags dropped, entities decoded."""
    return html.unescape(_TAG.sub(" ", markup))


def table_numbers(page_html: str) -> set[str]:
    """The numbers of every `<table>` in a generated page: what an analyst may cite (ADR-0029 s7)."""
    return set().union(*(numbers(text_of(t)) for t in _TABLE.findall(page_html)))


def _render_markdown(md_text: str) -> str:
    """The pack's stdlib Markdown renderer (render-markdown.py, which escapes every text run), loaded by path as
    `publish` loads the same file: one renderer, no second Markdown dialect here."""
    spec = importlib.util.spec_from_file_location("render_markdown", publish.RENDER_MARKDOWN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render_markdown(md_text)


def check_and_render(md_text: str, generated_numbers: set[str]) -> Html:
    """The analyst section's HTML, or a refusal: HB-SEC-001 on a scan hit (shapes named, never values), HB-USR-002
    listing every cited number absent from `generated_numbers`."""
    shapes = sorted(set(publish.scan_text(md_text)))
    if shapes:
        raise BenchError("HB-SEC-001", f"the analysis holds {', '.join(shapes)}; it is not embedded")
    rendered = _render_markdown(md_text)
    allowed = {canonical(n) for n in generated_numbers}
    missing = sorted(numbers(text_of(rendered)) - allowed, key=lambda n: (Decimal(n), n))
    if missing:
        raise BenchError("HB-USR-002", "the analysis cites numbers that are not in the page's generated tables: "
                                       + ", ".join(missing))
    return el("section", {"id": SECTION_ID}, el("h2", None, HEADING),
              el("p", {"class": "muted"}, "Written by an analyst from the tables above; every number it cites appears "
                 "in them (checked mechanically when the page was built)."),
              el("div", {"class": "analysis"}, trusted(rendered)))
