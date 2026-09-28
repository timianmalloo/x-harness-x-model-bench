"""R1 (design: docs/design/phase4-report.md, section 15): the safe HTML builder, the report model, and
the page shell -- escape by construction, the CSP meta with hashes, both themes' tokens, and the
section index/jump-link nav. `tests/test_report.py` keeps the existing report's behaviour; this file
is the new slice's own coverage (the pattern `test_report_disclosure.py`/`test_report_judges.py` already
use for a concern that is new, rather than folding it into the one large file).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from archived_runs import GOOD, make_root, make_run
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_bench import views
from harness_bench.grade import runner
from harness_bench.report import html, html_builder, model

# --- html_builder: escape by construction (UIA-15) ----------------------------------------------------

_INJECTIONS = ("<script>alert(1)</script>", '<img src=x onerror="alert(1)">', "</section><script>x</script>")


@given(text=st.text())
@settings(deadline=None)
def test_builder_refuses_on_attributes(text):
    """hypothesis: no `str` input yields a tag or an `on*`/`style` attribute (design section 5, 10).

    Two properties in one test, both load-bearing for the same invariant (a plain `str` can never
    become markup): a child string never survives into the output as an unescaped `<`/`>` (so it can
    never open a tag), and an attribute named `on*` or `style` is refused outright rather than merely
    escaped (an escaped *value* would still leave the attribute itself sitting in the DOM).
    """
    out = html_builder.el("div", None, text)
    inner = out[len("<div>"):-len("</div>")]
    assert "<" not in inner and ">" not in inner


@pytest.mark.parametrize("payload", _INJECTIONS)
def test_builder_refuses_on_attributes_named_examples(payload):  # the UIA-15 fixture shapes, as fixed examples
    out = html_builder.el("div", None, payload)
    inner = out[len("<div>"):-len("</div>")]
    assert "<" not in inner and ">" not in inner  # the whole payload is inert text, not a real tag or attribute
    assert "&lt;" in out


@given(name=st.sampled_from(["onerror", "onclick", "ONLOAD", "OnMouseOver", "style", "STYLE", "on"]))
def test_attribute_names_matching_on_star_or_style_are_refused(name):
    with pytest.raises(ValueError):
        html_builder.el("a", {name: "x"})


def test_ordinary_attributes_still_work():
    assert html_builder.el("a", {"href": "#x", "aria-pressed": True}, "go") == '<a href="#x" aria-pressed>go</a>'


def test_javascript_href_is_refused():  # design section 10's STRIDE row: no `javascript:` hrefs
    with pytest.raises(ValueError):
        html_builder.el("a", {"href": "javascript:alert(1)"}, "go")


def test_void_elements_self_close_with_no_children():
    assert html_builder.el("meta", {"charset": "utf-8"}) == '<meta charset="utf-8"/>'
    with pytest.raises(ValueError):
        html_builder.el("meta", None, "not allowed")


def test_trusted_markup_passes_through_unescaped():
    assert html_builder.el("div", None, html_builder.trusted("<b>ok</b>")) == "<div><b>ok</b></div>"


# --- CSP meta (design section 5) -----------------------------------------------------------------------


def test_csp_meta_is_first_head_child_with_script_hash():
    style_text = "body{color:red}"
    script_text = "var x = 1;"
    head = html_builder.head_block(title="t", style_text=style_text, script_text=script_text)
    assert head.startswith('<head><meta http-equiv="Content-Security-Policy"')
    assert head.index("Content-Security-Policy") < head.index("<title")
    assert html_builder.sha256_token(script_text) in head
    assert html_builder.sha256_token(style_text) in head


def test_csp_script_src_is_none_without_a_script():  # R1: report.js is R4's deliverable
    meta = html_builder.csp_meta("body{color:red}")
    assert "script-src &#x27;none&#x27;" in meta or "script-src 'none'" in meta.replace("&#x27;", "'")


def test_csp_hash_changes_when_the_hashed_text_changes():  # a mutant that stops hashing would freeze this
    a = html_builder.sha256_token("one")
    b = html_builder.sha256_token("two")
    assert a != b and a.startswith("sha256-") and b.startswith("sha256-")


# --- Structural check: no path around the builder (E7, design section 5) --------------------------------


def test_agent_text_has_no_path_around_the_escaping_builder():
    """The smallest reliable check for "agent-derived text is only ever emitted through the escaping
    builder": `Html(` -- the constructor of the one type that skips escaping -- appears nowhere in
    `report/` except `html_builder.py` itself (which defines it and is the only module allowed to mint
    one). This does not need to parse Python or track every call site that might eventually hold agent
    text (R2-R9 add more of those): the invariant is a negative ("this token is absent"), and a
    substring scan can prove a negative exhaustively over the whole package, the same idiom
    `test_no_connector_name_is_hard_coded_in_the_report_source` in `test_report.py` already uses for
    a different absent-token guarantee.
    """
    import harness_bench.report as report_module

    root_dir = Path(report_module.__file__).parent
    for path in sorted(root_dir.glob("*.py")):
        if path.name == "html_builder.py":
            continue
        src = path.read_text(encoding="utf-8")
        assert "Html(" not in src, path.name


# --- report model + page shell (integration through html.render()) --------------------------------------


@pytest.fixture
def page():
    root_dir = None

    def _make(tmp_path):
        nonlocal root_dir
        root_dir = make_root(tmp_path)
        run_dir = make_run(root_dir, tmp_path, {"a": GOOD})
        runner.run_pass(run_dir, root_dir)
        return html.render(views.load(run_dir), archive_present=True)

    return _make


def test_page_shell_csp_is_first_head_child(tmp_path, page):
    doc = page(tmp_path)
    head = re.search(r"<head>(.*?)</head>", doc, re.DOTALL).group(1)
    assert head.strip().startswith('<meta http-equiv="Content-Security-Policy"')


def test_page_shell_has_a_section_index_with_jump_links(tmp_path, page):
    doc = page(tmp_path)
    nav = re.search(r'<nav aria-label="Sections">(.*?)</nav>', doc, re.DOTALL).group(1)
    for section_id in ("validity", "leaderboard", "pack-effect", "runs"):
        assert f'<a href="#{section_id}">' in nav
    assert 'href="#header"' not in nav  # header is the page's own <h1>, not a jump target
    # R4 join review: the control bar is its own <section id="controls"> now (a publication-scan unit,
    # US-47 c3), but it is chrome, not an IA section -- it carries no jump link and is not in the index.
    assert 'href="#controls"' not in nav
    assert '<a href="#runs">Runs</a>' in nav and '<section id="runs"><h2>Runs</h2>' in doc  # R-81 DR-R-8


def test_page_shell_section_order_matches_the_ia(tmp_path, page):
    doc = page(tmp_path)
    ids = re.findall(r'<section id="([a-z0-9-]+)">', doc)
    # "controls" (R4 join review) sits right after "header": a real <section> for the publication scan
    # (US-47 c3), inserted right after the nav like the sticky bar design section 6 asks for, but it is
    # not part of the report's eleven-section IA (US-40 c2) and carries no nav entry (test above).
    assert ids == ["header", "controls", "validity", "leaderboard", "pack-effect", "scenarios",
                  "context-growth", "runs"]  # no --baseline


def test_dark_theme_tokens_only_change_under_prefers_color_scheme_media_query(tmp_path, page):  # DR-R-3
    doc = page(tmp_path)
    style = re.search(r"<style>(.*)</style>", doc, re.DOTALL).group(1)
    # No theme toggle, no stored preference (R4 adds ordinary `<select>`s for the Runs filters, unrelated
    # to theme -- DR-R-3 is about the colour scheme only, never about those).
    assert 'data-theme' not in doc
    assert not re.search(r'id="[^"]*theme[^"]*"', doc)
    assert "@media (prefers-color-scheme: dark){" in style
    light_block = re.search(r":root\{color-scheme: light dark;(.*?)\}\n@media", style, re.DOTALL).group(1)
    dark_block = re.search(r"@media \(prefers-color-scheme: dark\)\{\n:root\{(.*?)\}\}", style, re.DOTALL).group(1)
    light_tokens = dict(re.findall(r"--([\w-]+):\s*([^;]+);", light_block))
    dark_tokens = dict(re.findall(r"--([\w-]+):\s*([^;]+);", dark_block))
    assert dark_tokens  # the mutation must have somewhere to change a value
    assert set(dark_tokens) <= set(light_tokens)  # dark only overrides tokens the light block also defines
    for name, value in dark_tokens.items():
        assert value != light_tokens[name], name  # an override that matches light is dead weight, not a theme


_DESIGN_SYSTEM_TOKENS = {
    "bg", "panel", "ink", "ink-2", "ink-3", "rule", "rule-strong", "focus", "na", "warn", "bad", "bad-bg",
    *[f"c{i}" for i in range(1, 9)], "div-pos", "div-neg",
    *[f"heat-{i}" for i in range(10)], "on-heat-dark", "on-heat-light",
    "font", "fs-small", "fs", "fs-h2", "fs-h1",
    *[f"s{i}" for i in range(1, 6)], "radius", "rule-w", "focus-w", "target", "maxw", "bar-h",
}


def test_design_system_token_names_are_present(tmp_path, page):  # pins design section 3's token catalog
    doc = page(tmp_path)
    style = re.search(r"<style>(.*)</style>", doc, re.DOTALL).group(1)
    names = set(re.findall(r"--([\w-]+):", style))
    assert _DESIGN_SYSTEM_TOKENS <= names


# --- report.model directly (no view/board fixture needed) ------------------------------------------------


def test_model_page_places_nav_right_after_the_header_section():
    sections = (
        model.Section("header", "Run header", html_builder.trusted("<section id=\"header\">h</section>")),
        model.Section("validity", "Validity", html_builder.trusted("<section id=\"validity\">v</section>")),
    )
    doc = model.page(model.ReportModel(run_id="r1", sections=sections), style="body{color:red}")
    assert doc.index("</section>") < doc.index('<nav aria-label="Sections">') < doc.index('id="validity"')
    assert '<a href="#validity">Validity</a>' in doc
    assert 'href="#header"' not in doc
