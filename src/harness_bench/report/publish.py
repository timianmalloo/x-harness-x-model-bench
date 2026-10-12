"""Publishing a generated page (ADR-0027 s4, s6; ADR-0029 s1, s7): the egress scan, the write, the one open.

`publish` refuses without `BENCH_OPERATOR_EMAIL` (fail-closed). It drops every excerpt element (`class="excerpt"`)
that `scan_text` flags, counted, never redacted in place; then scans the rest of the page (the egress gate's classes
with the host's credential literals, and `scan_text`'s shapes) and writes nothing on a hit (HB-SEC-001). It writes
the page atomically and, with `open`, calls the pack's `open_in_chrome` (render-markdown.py, loaded by path; this
module is its one call site), printing and returning the status (`opened`, or `not opened: <why>`).

`scan_text` is the one excerpt filter (seam ruling S-1): pure, it names each email, UUID, `Authorization`, `Bearer `,
`eyJ...` (JWT) and token shape in a text, never the matched value. `cost_compare.render` takes it injected, and the
analyst Markdown passes it before it is committed.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

from harness_bench import egress
from harness_bench.errors import BenchError
from harness_bench.report import credentials

OPERATOR_EMAIL_ENV = "BENCH_OPERATOR_EMAIL"
DESTINATION = "report"  # the egress destination id of report publication (report/html.py PUBLICATION)
ROOT = Path(__file__).resolve().parents[3]  # the bench root: its profiles name the host's credential files
RENDER_MARKDOWN = ROOT / "docs" / "ai-forward-pack" / "scripts" / "render-markdown.py"
# Named shapes, in priority order: a span one shape matched is not counted again by a later one.
SHAPES = (
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("uuid", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)),
    ("authorization", re.compile(r"\bauthorization[\"']?\s*[:=]\s*[\"']?\S{8,}", re.IGNORECASE)),
    ("bearer", re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}")),
    *(("token", shape) for shape in egress.SHAPES),
)
# An excerpt is one element whose class list names `excerpt` (ADR-0027 s3: at most three per harness, <= 280 chars).
EXCERPT = re.compile(r'<(\w+)\b[^>]*\bclass="(?:[^"]*\s)?excerpt(?:\s[^"]*)?"[^>]*>.*?</\1>', re.DOTALL)


def scan_text(text: str) -> list[str]:
    """Every egress-scan finding in `text`, each naming its shape (never the matched value); [] when clean."""
    found: list[tuple[int, int, str]] = []
    for name, shape in SHAPES:
        for m in shape.finditer(text):
            if not any(m.start() < end and start < m.end() for start, end, _ in found):
                found.append((m.start(), m.end(), name))
    return [name for _, _, name in sorted(found)]


def _drop_flagged_excerpts(html: str) -> tuple[str, int]:
    dropped = 0

    def one(m: re.Match) -> str:
        nonlocal dropped
        if scan_text(m.group(0)):
            dropped += 1
            return ""
        return m.group(0)
    return EXCERPT.sub(one, html), dropped


def _write(out: Path, text: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp, out)


def _open(out: Path) -> str:
    """ADR-0027 s4: the pack's lookup, loaded by path; no second Chrome lookup is written here."""
    try:
        spec = importlib.util.spec_from_file_location("render_markdown", RENDER_MARKDOWN)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except (OSError, ImportError, AttributeError, SyntaxError) as exc:
        return f"not opened: render-markdown.py not loadable ({exc})"
    return module.open_in_chrome(out)


def publish(html: str, out: Path, open: bool) -> str:
    email = os.environ.get(OPERATOR_EMAIL_ENV, "").strip()
    if not email:  # ADR-0027 s6: fail-closed, never `partial: email not supplied`
        raise BenchError("HB-USR-002", f"set {OPERATOR_EMAIL_ENV} to the operator's e-mail: the published page is scanned "
                                       "for it, and nothing is written without it (ADR-0027 s6)")
    page, dropped = _drop_flagged_excerpts(html)
    verdict = egress.check(page, destination=DESTINATION, operator=egress.Operator.from_os(email),
                           secrets=sorted(credentials.host_values(ROOT)), canaries=egress.CANARIES)
    shapes = sorted(set(scan_text(page)))
    if verdict.withheld or shapes:
        raise BenchError("HB-SEC-001", f"the page holds {', '.join(sorted(set(verdict.classes) | set(shapes)))}; "
                                       f"nothing was written to {out}")
    _write(out, page)
    print(f"published {out}: {dropped} excerpt(s) dropped by shape", file=sys.stderr)
    if not open:
        return "not opened: --open not given"
    status = _open(out)
    print(status)
    return status
