import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("render_doc_html", ROOT / "tools" / "render-doc-html.py")
render_doc_html = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render_doc_html)


def test_rendered_html_matches_markdown_source():
    for name in render_doc_html.DOCS:
        source = ROOT / name
        html = render_doc_html.target(source)
        assert html.is_file(), f"{html.name} missing: run python tools/render-doc-html.py"
        assert html.read_text(encoding="utf-8") == render_doc_html.render(source), \
            f"{html.name} drifted from {source.name}: run python tools/render-doc-html.py"


def test_every_level_two_section_is_a_page():
    source = ROOT / render_doc_html.DOCS[0]
    titles = [p["title"] for p in render_doc_html.pages(source.read_text(encoding="utf-8"))]
    assert titles[0] == "Overview"
    assert "Part A — Functional specification" in titles
    assert "Part B — UX specification" in titles
    assert "Part C — UI specification" in titles
