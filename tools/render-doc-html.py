"""Render a markdown doc to a browsable HTML page, using the pack's doc-viewer template.

The markdown is the source. The HTML is a generated copy: each `## ` section becomes a page in the
viewer's navigation, and Mermaid fences render as diagrams. tests/test_docs_html_in_sync.py fails
when a copy drifts from its source.

Usage: python tools/render-doc-html.py [docs/specs/<name>.md ...]   (default: every entry in DOCS)
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "ai-forward-pack" / "templates" / "doc-viewer.template.html"
PROJECT = "harness-bench"
DOCS = ("docs/specs/harness-bench.md",)
# The pack template keeps a fixed 300px sidebar at every width, which clips the page on a phone.
# simplify: a narrow-screen override injected here; ceiling: one media query; upgrade trigger:
# the pack's doc-viewer template becomes responsive upstream (then delete this block).
NARROW = ("<style>@media (max-width:760px){.layout{grid-template-columns:minmax(0,1fr)}"
          "nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}"
          "main{padding:24px 16px;max-width:100%;min-width:0}.content :not(pre)>code{overflow-wrap:anywhere}"
          ".content pre,.content table,.mermaid{display:block;max-width:100%;overflow-x:auto}}</style>\n")


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "page"


def pages(markdown: str) -> list[dict]:
    """Split on level-2 headings; the text before the first one is the overview page."""
    body = re.sub(r"\A---\n.*?\n---\n", "", markdown, count=1, flags=re.S)
    title = re.search(r"^# (.+)$", body, re.M)
    doc_title = title.group(1).strip() if title else PROJECT
    parts = re.split(r"^(?=## )", body, flags=re.M)
    result = [{"id": "overview", "title": "Overview", "group": doc_title, "markdown": parts[0].strip() + "\n"}]
    for part in parts[1:]:
        heading = part.splitlines()[0][3:].strip()
        result.append({"id": _slug(heading), "title": heading, "group": doc_title,
                       "markdown": "# " + heading + "\n" + part.split("\n", 1)[1]})
    return result


def render(source: Path) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    docs = json.dumps(pages(source.read_text(encoding="utf-8")), ensure_ascii=False, indent=1)
    docs = docs.replace("</", "<\\/")  # a literal </script> in the markdown must not close the tag
    meta = json.dumps({"project": PROJECT, "generated": "from " + source.relative_to(ROOT).as_posix(),
                       "documented_sha": ""})
    html = re.sub(r"window\.DOCS = \[.*?\n\];", lambda _: "window.DOCS = " + docs + ";", template, count=1, flags=re.S)
    html = re.sub(r"window\.DOC_META = \{.*?\};", lambda _: "window.DOC_META = " + meta + ";", html, count=1)
    html = html.replace("</head>", NARROW + "</head>", 1)
    return html.replace("__PROJECT__", PROJECT)


def target(source: Path) -> Path:
    return source.with_suffix(".html")


def main(argv: list[str]) -> int:
    for name in argv or DOCS:
        source = ROOT / name
        target(source).write_text(render(source), encoding="utf-8", newline="\n")
        print(f"rendered {name} -> {target(source).relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
