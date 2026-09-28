"""`report.model`: the presentation model (design section 5, Two Step View, R1).

`ReportModel` is the frozen tree Step 2 (the renderers) reads and Step 1 (each slice's `build()`)
writes; R1 carries only the shell fields -- `run_id` and the ordered, already-rendered `sections` --
since R0/R2-R9 own the board, comparison and summary data those sections are built from. Each later
slice extends this tree with its own formatted fields (per-section, so this module stays the one place
that later grows) rather than re-introducing ad-hoc formatting in a renderer (the duplication `html.py`
today has across `_leaderboard`, `_pack_effect` and `_comparison`, design section 5).

A `Section.body` is `Html` -- markup already escaped-by-construction or `trusted()`-marked safe at its
own call site (`report/html_builder.py`) -- never a plain `str` a shell function might re-emit unescaped.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness_bench.report import html_builder
from harness_bench.report.html_builder import Html


@dataclass(frozen=True)
class Section:
    """One `<section id="...">` of the report. `title` drives the sticky-bar jump link (design
    section 6); `header` carries none (it is the page's own `<h1>`, not a jump target)."""

    id: str
    title: str
    body: Html


@dataclass(frozen=True)
class ReportModel:
    """R1's shell model: enough to assemble the page (`html_builder.head_block` plus the section
    order, index and jump links). `run_id` names the page in `<title>`."""

    run_id: str
    sections: tuple[Section, ...]


def page(model: ReportModel, style: str, script: str | None = None) -> str:
    """The full page (design section 6): the shell, the sticky index/jump-link nav right after the
    header, then the rest of `model.sections` in order. `script` is `None` until R4 wires `report.js`
    in; the CSP's `script-src` is `'none'` until then (`html_builder.csp_meta`)."""
    nav = html_builder.el(
        "nav", {"aria-label": "Sections"},
        *(html_builder.el("a", {"href": f"#{s.id}"}, s.title) for s in model.sections if s.id != "header"),
    )
    head = html_builder.head_block(title=f"harness-bench run {model.run_id}", style_text=style, script_text=script)
    body_children: list[Html] = []
    for section in model.sections:
        body_children.append(section.body)
        if section.id == "header":
            body_children.append(nav)
    body = html_builder.el("body", None, html_builder.el("main", None, *body_children))
    doc = html_builder.el("html", {"lang": "en"}, head, body)
    return f"<!doctype html>\n{doc}\n"
