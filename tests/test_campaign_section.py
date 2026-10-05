"""Report section 3 (X-H2; docs/design/eval-power-verdicts.md section 11.4, brief docs/coordination/eval-wave2-e1/x-h2.md).

Campaigns are real ledgers built with C1's helpers (tests/test_cli_campaign.py); verdicts are the real
`verdicts.verdict`; the reader is the real `readiness.hidden_test_disagreements` in the join test. The only
fixtures are the C2/C3 inputs (tests/fixtures/campaign/w0_shapes.py), each with its swap point.
"""

from __future__ import annotations

import importlib.util
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_cli_campaign import CID, append, make_repo, put, walk_to
from test_gates import _cell

from harness_bench import campaign, power, readiness, verdicts, views
from harness_bench.errors import BenchError
from harness_bench.report import campaign_section, html

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "harness_bench"
_spec = importlib.util.spec_from_file_location("w0_shapes", ROOT / "tests" / "fixtures" / "campaign" / "w0_shapes.py")
w0 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w0)

RUN_ID = "R2"
LOG = "harness_bench.report.campaign_section"
D = Decimal


# ---------------------------------------------------------------- a minimal DOM

VOID = {"meta", "link", "br", "hr", "img", "input", "rect", "line", "path", "circle", "polygon", "polyline"}


class Node:
    def __init__(self, tag, attrs):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self) -> str:
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def walk(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node("#root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, {k: (v if v is not None else "") for k, v in attrs}))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def dom(doc: str) -> Node:
    parser = _Parser()
    parser.feed(doc)
    return parser.root


class Found(list):
    """Matches; indexing an empty result fails on an assertion, never an IndexError."""

    def __getitem__(self, i):
        assert self, "no element matched"
        return super().__getitem__(i)


def q(node: Node, tag: str | None = None, **attrs) -> list[Node]:
    """Descendants matching the tag and the attributes (`data_kind` means `data-kind`; None means present)."""
    want = {k.rstrip("_").replace("_", "-"): v for k, v in attrs.items()}
    return Found(n for n in node.walk() if (tag is None or n.tag == tag)
                 and all(k in n.attrs and (v is None or n.attrs[k] == v) for k, v in want.items()))


def section_of(root: Node, section_id: str) -> Node:
    found = q(root, "section", id=section_id)
    assert found, f"no <section id={section_id!r}> in the page"
    return found[0]


# ---------------------------------------------------------------- the world

@dataclass
class World:
    root: Path
    state: campaign.CampaignState
    prereg: dict
    inputs: dict
    view: views.RunView
    obj: campaign_section.CampaignInput
    calls: list


def grid_cells(extra=(), reps=(1, 2, 3), tasks=("S1", "S2"), off=0, on=1, on_tokens=100):
    cells = [_cell(t, r, arm, primary=(off if arm == "off" else on), cid=f"{t}-{arm}-{r}",
                   tokens=(on_tokens if arm == "on" else 100))
             for t in tasks for r in reps for arm in ("off", "on")]
    return cells + list(extra)


def mixed_cells():
    """Per task the pairs (off, on) = (0, 1), (1, 0), (0, 0): a mean difference of 0 with a wide interval."""
    values = {1: (0, 1), 2: (1, 0), 3: (0, 0)}
    return [_cell(t, r, arm, primary=values[r][0 if arm == "off" else 1], cid=f"{t}-{arm}-{r}")
            for t in ("S1", "S2") for r in (1, 2, 3) for arm in ("off", "on")]


def grid_plan():
    return {"arms": {"off": {"pack": None}, "on": {"pack": {"revision": 7, "commit": "ab" * 20}}},
            "tasks": {"S1": {}, "S2": {}}, "campaign": {"campaign_id": CID}}


def ring_plan():
    return {"arms": {"incumbent": {"pack": {"revision": 6, "commit": "cd" * 20}},
                     "candidate": {"pack": {"revision": 7, "commit": "ab" * 20}}},
            "tasks": {"S1": {}, "S2": {}}, "ring": {"tag": "r1", "hash": "ab" * 32}, "campaign": {"campaign_id": CID}}


def make_world(tmp_path, *, cells=None, kind="grid", reader: Callable | None = None, method="none", m=1, min_pairs=3,
               admitted=("S1", "S2"), attach=True, final_power=True, fixes=0, eligible=True, plan_body=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = make_repo(tmp_path)
    walk_to(root, "baselined")
    for n in range(fixes):  # a fix demotes `piloted` and `registered`, so fixes come before the pilot
        before, after = "abcdef"[n] * 64, "abcdef"[n + 1] * 64
        append(root, "defect_fix.admitted", defect_class=f"MOD-{n}", commit=f"{n}" * 40,
               changes={"src/harness_bench/engine.py": [before, after]})
    append(root, "pilot.passed")
    for task in ("S1", "S2"):
        append(root, "admission.decided", task=task, admitted=int(task in admitted), reason="kept")
    prereg = w0.prereg(method=method, m=m, min_pairs=min_pairs)
    inputs = w0.power_inputs(method=method, m=m)
    if final_power:
        append(root, "power.recorded", role="final", input_hash=put(root, inputs, "power"))
    if kind == "grid":
        append(root, "registered", prereg_hash=put(root, prereg, "prereg"))
    if attach:
        if kind == "grid":
            append(root, "grid.attached", run_id=RUN_ID, plan_hash="q" * 64)
        else:
            append(root, "ring_run.attached", run_id=RUN_ID, ring_hash="ab" * 32, plan_hash="q" * 64)
    state = campaign.read(root, CID)
    body = plan_body or (grid_plan() if kind == "grid" else ring_plan())
    view = views.RunView(run_id=RUN_ID, plan=body, completed=True, grading_id="g", catalog_version=None,
                         cells=cells if cells is not None else grid_cells())
    calls: list = []

    def default_reader():
        calls.append(1)
        return []

    obj = campaign_section.CampaignInput(
        state=state, prereg=prereg, power_inputs=inputs, power_result=power.analyse(w0.analysable(inputs)),
        eligibility=campaign.Eligibility(eligible, () if eligible else ("run is not attached to the campaign",)),
        expected_na=w0.EXPECTED_NA, read_disagreements=reader or default_reader)
    return World(root, state, prereg, inputs, view, obj, calls)


def render(world: World, obj=None, **kw) -> str:
    return html.render(world.view, archive_present=False, campaign_obj=obj or world.obj, **kw)


def verdict_cells(root: Node) -> list[Node]:
    return q(root, "td", class_="verdict-cell")


def with_reader(world: World, reader) -> campaign_section.CampaignInput:
    return campaign_section.CampaignInput(**{**vars(world.obj), "read_disagreements": reader})


def raiser(code="HB-USR-002", message="the reason text"):
    def read():
        raise BenchError(code, message)
    return read


# ---------------------------------------------------------------- R-93, three states

def test_r93_warning_line_renders_with_count_and_ids(tmp_path):
    world = make_world(tmp_path)
    page = dom(render(world, with_reader(world, lambda: ["C-014", "C-031"])))
    sec = section_of(page, "property-verdicts")
    lines = q(sec, "p", data_kind="hidden-test-disagreement")
    assert len(lines) == 1
    assert lines[0].attrs["data-count"] == "2" and lines[0].attrs["class"] == "warn"
    assert "C-014" in lines[0].text() and "C-031" in lines[0].text()
    order = [n for n in sec.walk() if n.attrs.get("data-kind") == "excluded-total" or n is lines[0] or n.tag == "table"]
    assert [n.attrs.get("data-kind", n.tag) for n in order] == ["excluded-total", "hidden-test-disagreement", "table"]


def test_r93_line_absent_when_zero(tmp_path):
    world = make_world(tmp_path)
    sec = section_of(dom(render(world)), "property-verdicts")
    assert not q(sec, None, data_kind="hidden-test-disagreement") and not q(sec, None, data_kind="hidden-test-agreement-not-recorded")
    assert "excluded 0 cells in total" in sec.text()


def test_r93_not_recorded_when_reader_failed(tmp_path):
    world = make_world(tmp_path)
    page = dom(render(world, with_reader(world, raiser())))
    lines = q(page, "p", data_kind="hidden-test-agreement-not-recorded")
    assert len(lines) == 1
    assert "data-count" not in lines[0].attrs
    assert not re.search(r"C-\d+", lines[0].text())
    assert not q(page, None, data_kind="hidden-test-disagreement")


def test_reader_raise_renders_not_recorded_with_the_reason(tmp_path):
    world = make_world(tmp_path)
    page = dom(render(world, with_reader(world, raiser(message="grading pass zz9 is absent or not completed"))))
    line = q(page, "p", data_kind="hidden-test-agreement-not-recorded")[0]
    assert line.text() == "Hidden-test agreement not recorded: grading pass zz9 is absent or not completed."


def test_another_exception_from_the_reader_propagates(tmp_path):
    world = make_world(tmp_path)
    with pytest.raises(BenchError) as err:
        render(world, with_reader(world, raiser(code="HB-USR-001", message="other")))
    assert err.value.code == "HB-USR-001"
    with pytest.raises(RuntimeError):
        render(world, with_reader(world, lambda: (_ for _ in ()).throw(RuntimeError("boom"))))


def test_the_reader_is_called_once(tmp_path):
    world = make_world(tmp_path)
    render(world)
    assert world.calls == [1]


@pytest.mark.parametrize("reader", [lambda: ["C-014"], raiser()], ids=["list", "raise"])
def test_r93_line_not_in_the_header(tmp_path, reader):
    world = make_world(tmp_path)
    page = dom(render(world, with_reader(world, reader)))
    header = section_of(page, "header")
    assert q(header, None, data_block="campaign"), "the EV-20 campaign block is part of the header"
    assert not [n for n in header.walk() if n.attrs.get("data-kind", "").startswith("hidden-test")]


def test_r93_kinds_differ_and_only_the_list_carries_a_count(tmp_path):
    world = make_world(tmp_path)
    seen = {}
    for name, reader in (("list", lambda: ["C-014", "C-031"]), ("empty", list), ("raise", raiser())):
        page = dom(render(world, with_reader(world, reader)))
        kinds = [n.attrs["data-kind"] for n in q(page, "p") if n.attrs.get("data-kind", "").startswith("hidden-test")]
        seen[name] = kinds
        assert len(kinds) == len(set(kinds))
        assert all("data-count" not in n.attrs for n in q(page, "p", data_kind="hidden-test-agreement-not-recorded"))
    assert seen == {"list": ["hidden-test-disagreement"], "empty": [], "raise": ["hidden-test-agreement-not-recorded"]}


def test_r93_line_changes_no_verdict(tmp_path):
    world = make_world(tmp_path)
    tables = []
    for reader in (list, lambda: ["C-014", "C-031"], raiser()):
        sec = section_of(dom(render(world, with_reader(world, reader))), "property-verdicts")
        tables.append(q(sec, "table")[0].text())
    assert tables[0] == tables[1] == tables[2] and tables[0]


def test_no_campaign_means_no_section_and_the_page_is_unchanged(tmp_path):
    world = make_world(tmp_path)
    plain = html.render(world.view, archive_present=False)
    assert html.render(world.view, archive_present=False, campaign_obj=None) == plain
    page = dom(plain)
    assert not q(page, "section", id="property-verdicts") and not q(page, None, data_block="campaign")
    assert not [n for n in page.walk() if n.attrs.get("data-kind", "").startswith("hidden-test")]


# ---------------------------------------------------------------- the join test (X-E has joined)

def test_section_reads_the_real_readiness_function(tmp_path):
    """Leg (a): a run folder with no completed grading pass; the real reader raises and the reason reaches the page."""
    world = make_world(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with pytest.raises(BenchError) as err:
        readiness.hidden_test_disagreements(run_dir, "grade-none")
    page = dom(render(world, with_reader(world, lambda: readiness.hidden_test_disagreements(run_dir, "grade-none"))))
    line = q(page, "p", data_kind="hidden-test-agreement-not-recorded")[0]
    assert "is absent or not completed" in line.text()
    assert line.text() == f"Hidden-test agreement not recorded: {err.value.message}."


# ---------------------------------------------------------------- legend (R-96)

@pytest.mark.parametrize(("method", "m", "level", "rule"), [
    ("holm", 45, "0.9989", "alpha/m (Bonferroni; Holm's first step)"),
    ("bonferroni", 45, "0.9989", "alpha/m (Bonferroni)"),
    ("none", 1, "0.9500", "alpha (no correction)"),
])
def test_legend_prints_level_rule(tmp_path, method, m, level, rule):
    world = make_world(tmp_path, method=method, m=m, cells=grid_cells(reps=(1, 2)), min_pairs=2)
    legend = q(section_of(dom(render(world)), "property-verdicts"), None, data_block="legend")[0]
    assert f"Interval level: {level} ({rule})" in legend.text()
    assert legend.attrs["data-method"] == method and legend.attrs["data-level-rule"] == rule
    assert legend.attrs["data-alpha-per-test"] == str(D("0.05") / m if method != "none" else D("0.05"))
    for cell in verdict_cells(dom(render(world))):
        assert level in cell.attrs["title"] and rule in cell.attrs["title"]


# ---------------------------------------------------------------- NA counts and exclusions

def tampered_world(tmp_path):
    bad = _cell("S1", 4, "on", primary=None, reason="invalid (check tampered)", cid="S1-on-4")
    return make_world(tmp_path, cells=grid_cells(extra=[bad, _cell("S1", 4, "off", primary=0, cid="S1-off-4")]))


def test_na_counts_by_reason_beside_every_verdict(tmp_path):
    world = tampered_world(tmp_path)
    sec = section_of(dom(render(world)), "property-verdicts")
    cell = verdict_cells(sec)[0]
    assert "not recorded by reason: invalid (check tampered) 1" in q(cell, None, data_part="excluded")[0].text()
    block = q(sec, "p", data_kind="na-counts")[0]
    assert block.text() == "not recorded by reason: invalid (check tampered) 1"


def test_check_tampered_is_listed_counted_and_a_pilot_item(tmp_path):
    from harness_bench import gates
    world = tampered_world(tmp_path)
    sec = section_of(dom(render(world)), "property-verdicts")
    items = q(sec, "li", data_cell_id="S1-on-4")
    assert items and "invalid (check tampered)" in items[0].text()
    assert "excluded 2 cells in total" in sec.text()  # the tampered cell and its partner
    pilot = gates.pilot(world.view, [], [], expected_na=w0.EXPECTED_NA)
    assert ("check-tampered", "S1-on-4") in [(i.kind, i.ident) for i in pilot]


def blocked_world(tmp_path):
    blocked = _cell("S2", 4, "on", outcome="failed", cause="auth", cid="S2-on-4")
    return make_world(tmp_path, cells=grid_cells(extra=[blocked]))


def test_excluded_one_cell_in_three_places(tmp_path):
    page = dom(render(blocked_world(tmp_path)))
    cell = verdict_cells(page)[0]
    places = {
        "cell": q(cell, None, data_part="excluded")[0],
        "block": q(page, None, data_block="exclusions")[0],
        "banner": section_of(page, "validity"),
    }
    assert "excluded 1" in places["cell"].text()
    for name, node in places.items():
        assert "S2-on-4" in node.text() and "failed (auth)" in node.text(), name
    assert "excluded 1 cells in total" in places["block"].text()


# ---------------------------------------------------------------- the verdict cell

def test_verdict_cell_has_eight_parts_in_order(tmp_path):
    world = make_world(tmp_path)
    cell = verdict_cells(section_of(dom(render(world)), "property-verdicts"))[0]
    parts = [n for n in cell.walk() if "data-part" in n.attrs]
    assert [p.attrs["data-part"] for p in parts] == ["verdict", "effect", "interval", "mde", "per-task", "token-ratio", "pairs", "excluded"]
    assert all(p.attrs.get("aria-label") for p in parts)
    required = next(r["n"] for r in world.obj.power_result["security"].required_pairs)
    by = {p.attrs["data-part"]: p.text() for p in parts}
    assert by["verdict"].startswith("better") and by["effect"] == "effect +1.00"
    assert by["mde"] == "MDE 0.30" and by["pairs"] == f"n 6 of {required}"
    assert "task S1: +1.00 [1.00, 1.00]" in by["per-task"] and by["excluded"].startswith("excluded 0")


def test_row_and_column_headers_name_property_harness_comparison(tmp_path):
    table = q(section_of(dom(render(make_world(tmp_path))), "property-verdicts"), "table")[0]
    row = q(table, "tr", data_property="security")[0]
    scopes = [(th.attrs["scope"], th.text()) for th in q(row, "th")]
    assert scopes == [("row", "security"), ("row", "cc"), ("row", "off vs on")]
    assert all(th.attrs["scope"] == "col" for th in q(q(table, "thead")[0], "th"))


@pytest.mark.parametrize(("state", "cells", "min_pairs", "word", "tail"), [
    ("better", None, 3, "better", ""),
    ("worse", grid_cells(off=1, on=0), 3, "worse", ""),
    ("no-difference", grid_cells(off=0, on=0), 3, "no difference ≥ MDE", ""),
    ("underpowered", mixed_cells(), 3, "inconclusive (underpowered)", ""),
    ("not-recorded", grid_cells(reps=(1, 2)), 6, "inconclusive (not recorded)", " — 4 of 6 pairs recorded"),
])
def test_evu_3_state_pairs_verdict_cell(tmp_path, state, cells, min_pairs, word, tail):
    world = make_world(tmp_path, cells=cells, min_pairs=min_pairs)
    cell = verdict_cells(section_of(dom(render(world)), "property-verdicts"))[0]
    assert cell.attrs["data-state"] == state
    assert q(cell, None, data_part="verdict")[0].text().strip().endswith(word + tail)


def test_evu_3_zero_recorded_pairs(tmp_path):
    world = make_world(tmp_path, cells=[])
    cell = verdict_cells(section_of(dom(render(world)), "property-verdicts"))[0]
    assert cell.attrs["data-state"] == "zero-pairs"
    assert q(cell, None, data_part="verdict")[0].text().strip().endswith("inconclusive (not recorded) — 0 pairs recorded; excluded 0")


def test_evu_3_no_admitted_task_empty_state(tmp_path):
    sec = section_of(dom(render(make_world(tmp_path, admitted=()))), "property-verdicts")
    assert "No property task was admitted. See the campaign record." in sec.text()
    assert not verdict_cells(sec)


def test_evu_3_a_comparison_absent_from_the_arms(tmp_path):
    only_off = [c for c in grid_cells() if c.pack == "off"]
    world = make_world(tmp_path, cells=only_off, plan_body={**grid_plan(), "arms": {"off": {"pack": None}}})
    row = q(section_of(dom(render(world)), "property-verdicts"), "tr", data_property="security")[0]
    assert "This grid has no on." in row.text()


def test_evu_3_more_than_ten_excluded_cells_scroll(tmp_path):
    extra = [_cell("S1", r, "on", outcome="failed", cause="auth", cid=f"S1-x-{r}") for r in range(10, 22)]
    page = dom(render(make_world(tmp_path, cells=grid_cells(extra=extra))))
    box = q(q(page, None, data_block="exclusions")[0], None, class_="scroll")
    assert box and len(q(box[0], "li")) == 12


def test_evu_3_ineligible_run_prints_the_reasons_and_no_verdict(tmp_path):
    world = make_world(tmp_path, attach=False)
    run = campaign.RunFacts(run_id=RUN_ID, plan_present=True, plan_hash="q" * 64, plan_campaign_id=CID,
                            plan_prereg_hash=None, plan_run_identity_hash=None, plan_ring_hash=None, grade_identity_hash="g")
    verdict = campaign.eligibility(world.state, campaign.effective_identity(world.root, world.state), run, None)
    assert not verdict.eligible and verdict.reasons
    obj = campaign_section.CampaignInput(**{**vars(world.obj), "eligibility": verdict})
    sec = section_of(dom(render(world, obj)), "property-verdicts")
    banner = q(sec, "p", data_kind="ineligible")[0]
    assert banner.text().startswith("No verdicts: ")
    assert all(reason in banner.text() for reason in verdict.reasons)
    assert not verdict_cells(sec) and not q(sec, "table")
    assert world.calls == []


# ---------------------------------------------------------------- EVU-1, 2, 4, 6, 7, 8 and the campaign block

def test_evu_1_4_8(tmp_path):
    world = make_world(tmp_path)
    page = dom(render(world))
    cell = verdict_cells(page)[0]
    assert "better" in q(cell, None, data_part="verdict")[0].text()
    assert all(g.attrs.get("aria-hidden") == "true" for g in q(cell, None, class_="glyph"))
    ids = [s.attrs["id"] for s in q(page, "section")]
    assert ids.index("validity") + 1 == ids.index("property-verdicts") and ids.index("property-verdicts") < ids.index("leaderboard")
    assert html.render(world.view, archive_present=False, campaign_obj=None) == html.render(world.view, archive_present=False)


def test_evu_2_interval_marks(tmp_path):
    cell = verdict_cells(section_of(dom(render(make_world(tmp_path))), "property-verdicts"))[0]
    marks = q(cell, None, class_="bar")
    assert marks and all("data-interval-lo" in m.attrs and "data-interval-hi" in m.attrs for m in marks)
    effect = q(cell, None, class_="bar", data_mark="effect")[0]
    assert effect.attrs["data-mde"] == "0.30" and effect.attrs["aria-hidden"] == "true"
    text = q(cell, None, data_part="interval")[0].text()
    assert f"{effect.attrs['data-interval-lo']} to {effect.attrs['data-interval-hi']}" in text


def test_evu_7_exploratory_labels(tmp_path):
    from archived_runs import GOOD, make_root, make_run

    from harness_bench.grade import runner
    root_dir = make_root(tmp_path)
    run_dir = make_run(root_dir, tmp_path, {"a": GOOD, "b": GOOD}, harness="codex", combos={"a": "copilot-sol", "b": "copilot-sol"})
    runner.run_pass(run_dir, root_dir)
    view = views.load(run_dir)
    for c in view.cells:
        if c.cell_id == "a":
            c.pack = "on"
    world = make_world(tmp_path / "w", eligible=False)  # the page is a campaign report; the flipped cell label names no pair
    header = "Exploratory — see §3 Property verdicts for the pre-registered result"
    badge = "exploratory — not pre-registered"
    page = dom(html.render(view, archive_present=True, run_dir=run_dir, root=root_dir, campaign_obj=world.obj))
    pack = section_of(page, "pack-improvement")
    cells = [td for td in q(pack, "td", data_verdict="intention")]
    assert cells and header in pack.text()
    assert all(q(td, None, class_="badge") and badge in td.text() for td in cells)
    assert len([n for n in pack.walk() if n.text() == badge]) == len(cells)
    plain = section_of(dom(html.render(view, archive_present=True, run_dir=run_dir, root=root_dir)), "pack-improvement")
    assert header not in plain.text() and badge not in plain.text()


def test_campaign_block_facts_come_from_the_ledger(tmp_path):
    world = make_world(tmp_path, fixes=2)
    block = q(section_of(dom(render(world)), "header"), None, data_block="campaign")[0]
    field = {n.attrs["data-field"]: n.text() for n in q(block, "dd")}
    row = campaign.latest
    assert field["question"] == "does the pack help"
    assert field["prereg-hash"].startswith(row(world.state, "registered")["prereg_hash"][:12])
    assert field["baseline"].startswith(row(world.state, "baseline.recorded")["identity_hash"][:12])
    assert "MOD-0" in field["defect-fixes"] and "MOD-1" in field["defect-fixes"]
    assert field["mde"] == "security 0.30"
    assert field["power-analysis"].startswith(row(world.state, "power.recorded", role="final")["input_hash"][:12])
    assert "(final)" in field["power-analysis"]
    assert field["arms"] == "off (no pack), on (revision 7)"


def test_campaign_block_absent_rows_print_not_recorded(tmp_path):
    world = make_world(tmp_path, final_power=False, attach=False)
    block = q(section_of(dom(render(world)), "header"), None, data_block="campaign")[0]
    field = {n.attrs["data-field"]: n.text() for n in q(block, "dd")}
    assert field["power-analysis"] == "not recorded" and field["defect-fixes"] == "not recorded"
    assert all(v.strip() for v in field.values())


def test_section_kind_follows_the_attach_row(tmp_path):
    grid = make_world(tmp_path / "g")
    ring = make_world(tmp_path / "r", kind="ring", cells=[_cell(t, r, a, primary=1, cid=f"{t}-{a}-{r}") for t in ("S1", "S2") for r in (1, 2) for a in ("incumbent", "candidate")])
    assert campaign_section.build(grid.view, grid.obj).section.id == "property-verdicts"
    assert campaign_section.build(ring.view, ring.obj).section.id == "regression-check"


# ---------------------------------------------------------------- the ring section

def ring_cells(incumbent=1, candidate=1, arms=("incumbent", "candidate"), extra=()):
    return [_cell(t, r, a, primary=(incumbent if a == "incumbent" else candidate), cid=f"{t}-{a}-{r}")
            for t in ("S1", "S2") for r in (1, 2, 3) for a in arms] + list(extra)


@pytest.mark.parametrize(("name", "kw", "state", "text"), [
    ("signal", {"incumbent": 1, "candidate": 0}, "signal", "regression signal"),
    ("no-signal", {"incumbent": 1, "candidate": 1}, "no-signal", "no regression detected at 0.30 — this ring cannot see smaller effects."),
    ("missing-arm", {"arms": ("incumbent",)}, "withheld", "Result withheld: ring is missing candidate."),
    ("gate-failed", {"extra": [_cell("S1", 9, "candidate", outcome="failed", cid="S1-lost")]}, "withheld",
     "Result withheld: ring gate failed (cell-lost S1-lost)."),
])
def test_evu_3_regression_table_states(tmp_path, name, kw, state, text):
    world = make_world(tmp_path, kind="ring", cells=ring_cells(**kw))
    sec = section_of(dom(render(world)), "regression-check")
    cell = q(sec, "td", data_state=state)[0]
    assert cell.text() == text
    assert "No earlier ring result for this pack." in sec.text()


def test_evu_3_ring_without_property_tasks(tmp_path):
    world = make_world(tmp_path, kind="ring", cells=ring_cells(), admitted=())
    obj = campaign_section.CampaignInput(**{**vars(world.obj), "power_inputs": {**world.inputs, "properties": {}}, "power_result": {}})
    assert "This ring has no property tasks." in section_of(dom(render(world, obj)), "regression-check").text()


def test_evu_6_ring_section_has_no_verdict_words(tmp_path):
    for n, kw in enumerate(({"incumbent": 1, "candidate": 0}, {"incumbent": 1, "candidate": 1}, {"arms": ("incumbent",)})):
        world = make_world(tmp_path / f"w{n}", kind="ring", cells=ring_cells(**kw))
        sec = section_of(dom(render(world)), "regression-check")
        assert not re.search(r"better|worse|dominates", sec.text(), re.IGNORECASE)


# ---------------------------------------------------------------- telemetry (design 12)

def event_of(caplog, name):
    found = [r for r in caplog.records if r.name == LOG and r.getMessage() == name]
    assert len(found) == 1, f"{len(found)} {name} events, expected 1"
    return found[0]


def test_verdicts_computed_event_fields(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=LOG)
    world = tampered_world(tmp_path)
    render(world)
    event = event_of(caplog, "verdicts.computed")
    assert event.verdicts == 1 and event.resamples_total == verdicts.resamples_for(D("0.05"))
    assert event.excluded_total == 2 and event.na_total == 1 and event.labels == {"better": 1}
    assert isinstance(event.ms, (int, float)) and event.ms >= 0


def test_verdicts_computed_event_reads_not_recorded_when_ineligible(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=LOG)
    world = make_world(tmp_path, eligible=False)
    render(world)
    event = event_of(caplog, "verdicts.computed")
    assert {event.verdicts, event.resamples_total, event.excluded_total, event.na_total, event.ms} == {"not recorded"}
    assert event.labels == "not recorded"


def test_gate_evaluated_event_fields(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=LOG)
    world = make_world(tmp_path, kind="ring", cells=ring_cells(extra=[_cell("S1", 9, "candidate", outcome="failed", cid="S1-lost")]))
    render(world)
    event = event_of(caplog, "gate.evaluated")
    assert event.tag == "r1" and event.items == {"cell-lost": 1}
    assert isinstance(event.ms, (int, float)) and event.ms >= 0


@pytest.mark.parametrize(("reader", "expect"), [(lambda: ["a", "b", "c"], 3), (list, 0), (raiser(), "not recorded")])
def test_section_built_event_fields(tmp_path, caplog, reader, expect):
    caplog.set_level(logging.INFO, logger=LOG)
    world = make_world(tmp_path)
    render(world, with_reader(world, reader))
    event = event_of(caplog, "section.built")
    assert event.hidden_disagreements == expect and type(event.hidden_disagreements) is type(expect)


# ---------------------------------------------------------------- sweep S-2

DOMINATES_ALLOWED = {("verdicts.py", "dominates"), ("report/campaign_section.py", "No arm dominates another.")}


def sweep_dominates(root: Path, allowed) -> list[str]:
    """Problems: an occurrence of the word outside its allowlisted needle, and an allowlist pair that matches nothing."""
    problems, matched = [], set()
    for path in sorted(p for pattern in ("*.py", "*.js", "*.html") for p in root.rglob(pattern)):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for needle in (n for f, n in allowed if f == rel):
            if needle.lower() in text.lower():
                matched.add((rel, needle))
            text = re.sub(re.escape(needle), "", text, flags=re.IGNORECASE)
        if "dominates" in text.lower():
            problems.append(f"{rel}: the word outside the allowlist")
    problems += [f"stale allowlist pair {pair}" for pair in sorted(allowed - matched)]
    return problems


def test_dominates_appears_only_in_the_allowlisted_places():
    assert sweep_dominates(SRC, DOMINATES_ALLOWED) == []


def test_dominates_sweep_red_fixture(tmp_path):
    (tmp_path / "report").mkdir()
    (tmp_path / "mod.py").write_text("X = 'a dominates b'\n", encoding="utf-8")
    (tmp_path / "report" / "assets.js").write_text("const s = 'Dominates';\n", encoding="utf-8")
    problems = sweep_dominates(tmp_path, {("verdicts.py", "dominates")})
    assert any("mod.py" in p for p in problems) and any("assets.js" in p for p in problems)
    assert any("stale allowlist pair" in p for p in problems)


def test_dominance_line_is_the_verdict_statement_with_context(tmp_path):
    world = make_world(tmp_path, cells=grid_cells(on_tokens=50))
    block = q(section_of(dom(render(world)), "property-verdicts"), None, data_block="dominance")[0]
    assert [li.text() for li in q(block, "li")] == ["on dominates off on security (cc)"]
    assert "No arm dominates another." not in block.text()


def test_dominance_empty_state_and_a_costly_gain_is_not_a_dominance_line(tmp_path):
    world = make_world(tmp_path, cells=grid_cells(on_tokens=400))
    block = q(section_of(dom(render(world)), "property-verdicts"), None, data_block="dominance")[0]
    assert block.text() == "No arm dominates another."
    cell = verdict_cells(section_of(dom(render(world)), "property-verdicts"))[0]
    assert "better at ×4.00 tokens" in cell.text()
