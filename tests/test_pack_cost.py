"""R-PACKCOST: `report.pack_cost` (ADR-0029), from hand-built views with injected fakes, and on a real fixture run.

The arithmetic tests fake the derivations through their signatures: `context_growth.request_series(view, cell_id)`,
`tool_phases.carry_until_compaction(entered, compacted_before)` and `pack_cost.cell_facts`. The real-path test (J2-FIX
item 3) fakes nothing: a graded Copilot pack-off/pack-on pair, read by the real reader, `request_series`, the carry
rule and `cell_facts` through the view alone, with git working copies and a git pack source. The plan and profiles
of the golden's run come from R-GOLD's frozen fixture root (`archived_runs.FROZEN_ROOT`), never the repository's
`bench/`.
"""

from __future__ import annotations

import argparse
import dataclasses
import html
import os
import re
from pathlib import Path

import pytest
from archived_runs import FROZEN_ROOT

from harness_bench import gitsafe, lean
from harness_bench import plan as plan_mod
from harness_bench.errors import BenchError
from harness_bench.report import context_growth, pack_cost, publish, tool_phases
from harness_bench.report.context_growth import RequestSeries
from harness_bench.report.pack_cost import TERMS, CellFacts, PackSource
from harness_bench.telemetry import HarnessEvent, PromptPart, ToolInput
from harness_bench.views import CellView, Measure, RunView

GOLDEN = Path(__file__).parent / "goldens" / "pack-cost.html"
AXE = Path(__file__).parent / "vendor" / "axe-core" / "axe.min.js"
PACK = {"source": "C:/Projects/ai-forward", "commit": "4a22f12" + "0" * 33}
TASK_FILES = frozenset({"README.md", "slug.py"})
PACK_FILES = {
    ".github/instructions/a.instructions.md": '---\napplyTo: "**"\n---\n# A\n',
    ".github/instructions/b.instructions.md": '---\napplyTo: "src/**"\n---\n# B\n',
    "AGENTS.md": "# Agents\n",
    ".claude/skills/x/SKILL.md": "---\nname: x\n---\n",
    ".claude/agents/p.md": "# persona\n",
    "docs/knowledge/k.md": "# knowledge\n",
    ".claude/hooks/h.py": "print()\n",
    "tools/z.txt": "z\n",
}
GROK_REASON = "not recorded: per-turn totals only"
HOOK_MS, ON_WALL_MS = 3000, 15000  # hook share of wall exactly HOOK_WALL_SHARE (0.2)


# --- fixture views ------------------------------------------------------------------------------------------------
def _tokens(inp: int, out: int) -> dict:
    return {"m": {"uncached_input": inp, "cache_read": 0, "cache_write": 0, "output": out}}


def _cell(cid: str, harness: str, arm: str, tokens: dict | None, wall: int = 10000) -> CellView:
    combo = {"claude-code": "cc-opus", "copilot": "copilot-sol", "grok": "grok"}[harness]
    return CellView(cell_id=cid, task="X1", rep=1, label=f"X1.{combo}.pack-{arm}.r1", combo=combo, arm=arm,
                    harness=harness, model="m", outcome="completed", cause=None, code=None, validity="valid",
                    validity_code=None, wall_ms=Measure(wall), model_ms=Measure(None, "n"), tool_ms=Measure(None, "n"),
                    idle_ms=Measure(None, "n"), tokens=tokens, tokens_reason=None,
                    scores={"property_check_pass": Measure(1 if arm == "on" else 0)}, extraction_id="e1")


# Known parts, claude-code pair (tokens per character 0.5 from the first request: 4,500 / 9,000 prefix characters):
# fixed prefix 7,000 chars x 3 requests x 0.5 = 10,500; extra requests 1 x median(1,000, 1,100) = 1,050; a pack read of
# 400 bytes entering at request 1 and carried to request 2 = 400; a skill load of 200 bytes at request 2 = 100;
# output 500 - 300 = 200; planted residual 777. Delta = 13,027 = 15,427 - 2,400.
RESIDUAL = 777
CC_DELTA = 10500 + 1050 + 400 + 100 + 200 + RESIDUAL


def _views() -> list[RunView]:
    cells = [
        _cell("cc-off", "claude-code", "off", _tokens(2100, 300)),
        _cell("cc-on", "claude-code", "on", _tokens(2400 + CC_DELTA - 500, 500), wall=ON_WALL_MS),
        _cell("cp-off", "copilot", "off", _tokens(2100, 300)),
        _cell("cp-on", "copilot", "on", _tokens(2400 + CC_DELTA - 500, 500), wall=ON_WALL_MS + 1),
        _cell("gk-off", "grok", "off", _tokens(4900, 100)),
        _cell("gk-on", "grok", "on", _tokens(7700, 300), wall=ON_WALL_MS + 1),
    ]
    profiles = {h: plan_mod.profile_record(FROZEN_ROOT, h) for h in ("claude-code", "copilot")}
    plan = {"run_id": "b1", "plan_hash": "h1", "ring": {"tag": "lean"}, "comparisons": [["off", "on"]],
            "arms": {"off": {"pack": None}, "on": {"pack": PACK}}, "profiles": profiles,
            "builds": {"copilot": {"adapter_version": "0.1.0"}},
            "cells": [{"cell_id": c.cell_id, "task": "X1", "combo": c.combo, "harness": c.harness, "model": "m",
                       "arm": c.arm, "rep": 1} for c in cells]}
    return [RunView("b1", plan, True, "g1", "0.7", cells)]


def _parts(on: bool) -> tuple[PromptPart, ...]:
    parts = [PromptPart(0, "system", None, 2000, "inlined", "fixture")]
    if on:
        parts += [PromptPart(1, "instruction_file", ".github/instructions/a.instructions.md", 4000, "inlined", "fixture"),
                  PromptPart(2, "agents_md", "AGENTS.md", 2000, "inlined", "fixture"),
                  PromptPart(3, "skills", None, 1000, "listed", "fixture")]
    return tuple(parts)


def _facts(view: RunView, cell: CellView) -> CellFacts:
    on = cell.arm == "on"
    calls = (ToolInput(3, "Read", ("C:\\cells\\ws\\docs\\knowledge\\k.md",), None, False, 400),
             ToolInput(4, "Read", ("README.md",), None, False, 900),
             ToolInput(7, "Skill", (), None, False, 200)) if on else ()
    hooks = tuple(HarnessEvent(i, "hook", "pre", f"2026-10-12T00:00:0{2 * i}Z", f"2026-10-12T00:00:0{2 * i + 1}Z",
                               True, None) for i in range(3)) if on else ()
    base = TASK_FILES | (frozenset(PACK_FILES) if on else frozenset())
    return CellFacts(model_ordinals=(1, 5, 9) if on else (1, 5), prompt_parts=_parts(on), tool_inputs=calls,
                     harness_events=hooks, base_tree=base)


def _series(view: RunView, cell_id: str) -> RequestSeries:
    if cell_id.startswith("gk"):
        return RequestSeries(cell_id, reason=GROK_REASON)
    return RequestSeries(cell_id, inputs=(4500, 4700, 5300) if cell_id.endswith("-on") else (1000, 1100))


def _carry(entered, compacted_before):
    """A reference carry: everything entered so far, until a compaction drops it."""
    out, held = [], 0
    for i, amount in enumerate(entered):
        if i in compacted_before:
            held = 0
        held += amount
        out.append(held)
    return tuple(out)


def _source(plan: dict) -> PackSource:
    return PackSource(f"{PACK['source']}@{PACK['commit']}", None, PACK_FILES.get)


@pytest.fixture
def fakes(monkeypatch):
    monkeypatch.setattr(pack_cost, "cell_facts", _facts)
    monkeypatch.setattr(pack_cost, "pack_source", _source)
    monkeypatch.setattr(context_growth, "request_series", _series)
    monkeypatch.setattr(tool_phases, "carry_until_compaction", _carry)


def _harness(pc, name):
    return next(h for h in pc.harnesses if h.harness == name)


def _term(h, name):
    return next(t for t in h.terms if t.name == name)


# --- the decomposition ---------------------------------------------------------------------------------------------
def test_the_terms_sum_to_the_delta_with_the_planted_residual_shown_never_spread(fakes):
    cc = _harness(pack_cost.build(_views()), "claude-code")
    assert [t.name for t in cc.terms] == list(TERMS)
    values = {t.name: t.median.value for t in cc.terms}
    assert values == {"fixed_prefix": 10500, "extra_requests": 1050, "pack_reads": 400, "skill_loads": 100,
                      "hooks": None, "reasoning_output": 200, "residual": RESIDUAL}
    assert cc.delta_total.value == CC_DELTA == sum(v for v in values.values() if v is not None)
    assert _term(cc, "hooks").median.reason.startswith("not recorded")


def test_the_modelled_steps_are_labelled_inferred(fakes):
    cc = _harness(pack_cost.build(_views()), "claude-code")
    assert "Inferred (tokens per character)" in _term(cc, "fixed_prefix").label
    assert "Inferred" in _term(cc, "extra_requests").label and "Verified" in _term(cc, "extra_requests").label
    assert "Inferred" in _term(cc, "pack_reads").label
    assert _term(cc, "reasoning_output").label.startswith("Verified")


def test_grok_on_demand_terms_read_not_recorded_per_turn_totals_only(fakes):
    gk = _harness(pack_cost.build(_views()), "grok")
    for name in ("pack_reads", "skill_loads", "fixed_prefix", "extra_requests"):
        assert _term(gk, name).median == Measure(None, GROK_REASON)
        assert _term(gk, name).label == GROK_REASON
    assert _term(gk, "residual").median.value == 3000 - 200


def test_every_harness_row_carries_its_transport(fakes):
    pc = pack_cost.build(_views())
    assert {h.harness: h.transport for h in pc.harnesses} == {
        "claude-code": "acp", "copilot": "copilot -p (local adapter)", "grok": "acp"}
    page = pack_cost.render(pc)
    for row in re.findall(r'<tr data-harness="[^"]+">.*?</tr>', page, re.DOTALL):
        assert "transport: " in row, row[:120]
    assert page.count("transport: copilot -p (local adapter)") >= 3


def test_a_harness_with_unrecorded_terms_shows_not_recorded_components_never_0(fakes):
    pc = pack_cost.build(_views())
    comps = re.search(r'<section id="components">.*?</section>', pack_cost.render(pc), re.DOTALL).group(0)
    grok = re.search(r'<tr data-harness="grok">.*?</tr>', comps, re.DOTALL).group(0)
    assert ">0<" not in grok and GROK_REASON in grok
    skills = next(f for f in pc.top_files if f.path == "(skills part)" and f.harness == "claude-code")
    assert skills.component == "skill"


def test_unrecorded_base_trees_or_prompt_parts_read_not_recorded_never_0(fakes, monkeypatch):
    def no_tree(view, cell):
        return dataclasses.replace(_facts(view, cell), base_tree="not recorded: no archived working copy")
    monkeypatch.setattr(pack_cost, "cell_facts", no_tree)
    cc = _harness(pack_cost.build(_views()), "claude-code")
    assert _term(cc, "pack_reads").median == Measure(None, "not recorded: no archived working copy")
    assert _term(cc, "skill_loads").median.value == 100  # a skill load needs no pack membership

    def no_parts(view, cell):
        return dataclasses.replace(_facts(view, cell), prompt_parts="not recorded: no prompt_parts rows")
    monkeypatch.setattr(pack_cost, "cell_facts", no_parts)
    cc = _harness(pack_cost.build(_views()), "claude-code")
    assert _term(cc, "fixed_prefix").median == Measure(None, "not recorded: no prompt_parts rows")


def test_the_real_reader_without_a_run_directory_reads_not_recorded():
    view = _views()[0]
    facts = pack_cost.cell_facts(view, view.cells[0])
    assert set(dataclasses.astuple(facts)) == {pack_cost.NO_RUN_DIR}


# --- the real path: no fakes (J2-FIX items 2 and 3) ----------------------------------------------------------------
COPILOT = Path(__file__).parent / "fixtures" / "copilot"
# The pack files the pack-on record names (its AGENTS.md prompt part and its `view` calls), with frontmatter.
REAL_PACK = {
    "AGENTS.md": "# Agents\n",
    ".github/instructions/testing-strategy.instructions.md": '---\napplyTo: "**"\n---\n# Testing\n',
    ".github/instructions/observability-and-instrumentation.instructions.md": '---\napplyTo: "src/**"\n---\n# O\n',
    ".agents/skills/implement/reference/co-s0.md": "# co-s0\n",
}


def _write(folder: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text, encoding="utf-8", newline="\n")


def _real_run(tmp_path: Path, pack: dict) -> Path:
    """A graded pack-off/pack-on Copilot pair: R-COPILOT-P's real `-p` records (`rerun-off`, `rerun-on`) and their
    debug logs in each cell home, renamed to the cell's session; each working copy a git tree built as the workspace
    builder commits it (the task base, then the pack revision on pack-on)."""
    import json

    from archived_runs import GOOD, make_root, make_run

    from harness_bench.grade import runner

    root = make_root(tmp_path / "r")
    run_dir = make_run(root, tmp_path / "t", {"off": GOOD, "on": GOOD}, harness="copilot", model="gpt-6.1-sol")
    plan = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    for cell in plan["cells"]:
        cell["arm"] = cell["pack"] = cell["cell_id"]
        cell["label"] = f"X1.c.pack-{cell['arm']}.r1"
    plan |= {"arms": {"off": {"pack": None}, "on": {"pack": pack}}, "comparisons": [["off", "on"]],
             "builds": {"copilot": {"adapter_version": "0.1.0"}}}
    plan["plan_hash"] = plan_mod.plan_hash(plan)
    (run_dir / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    for cell in plan["cells"]:
        cid = cell["cell_id"]
        attempt = run_dir / "archive" / cid / "attempt-1"
        src = COPILOT / f"rerun-{cid}" / "home"
        record = next((src / "session-state").glob("*/events.jsonl"))
        native = record.parent.name
        dest = attempt / "home" / "session-state" / f"sess-{cid}" / "events.jsonl"
        dest.write_text(record.read_text(encoding="utf-8").replace(native, f"sess-{cid}"), encoding="utf-8")
        (attempt / "home" / "logs").mkdir()
        for log in (src / "logs").glob("process-*.log"):
            (attempt / "home" / "logs" / log.name).write_text(
                log.read_text(encoding="utf-8").replace(native, f"sess-{cid}"), encoding="utf-8")
        ws = attempt / "ws"
        _git(ws.parent, "init", "-q", str(ws))
        _git(ws, "add", "-A")
        _git(ws, "commit", "-q", "-m", f"X1 base ({cell['task_version'][:12]})")
        if cid == "on":
            _write(ws, REAL_PACK)
            _git(ws, "add", "-A")
            _git(ws, "commit", "-q", "-m", "ai-forward pack revision 1")
    runner.run_pass(run_dir, root)
    return run_dir


def test_the_real_path_decomposes_a_graded_copilot_pair_with_no_fakes(tmp_path):
    from harness_bench import views as views_mod
    from harness_bench.telemetry import copilot

    repo = tmp_path / "pack"
    _write(repo, REAL_PACK)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pack")
    view = views_mod.load(_real_run(tmp_path, {"source": str(repo), "commit": _git(repo, "rev-parse", "HEAD")}))
    # The frozen X1 has no property grader, so the lean pairing's admission score is set on the view; every
    # derivation under test (the reader rows, request_series, the carry, cell_facts, the pack source) is real.
    view.cells = [dataclasses.replace(c, scores=c.scores | {"property_check_pass": Measure(1)}) for c in view.cells]
    # one accessor: the view alone reaches its run's rows and archive (no `load_views` registration)
    on = next(c for c in view.cells if c.cell_id == "on")
    facts = pack_cost.cell_facts(view, on)
    record = next((COPILOT / "rerun-on" / "home" / "session-state").glob("*/events.jsonl"))
    assert facts.model_ordinals == tuple(c.native_ordinal for c in copilot.read(record).model_calls)
    assert facts.base_tree == frozenset({"slug.py", *REAL_PACK})
    assert isinstance(facts.prompt_parts, tuple) and isinstance(facts.tool_inputs, tuple)
    pc = pack_cost.build([view])
    (h,) = pc.harnesses
    assert (h.harness, h.transport, h.pairs) == ("copilot", "copilot -p (local adapter)", 1)
    terms = {t.name: t.median for t in h.terms}
    # hand count from the records: 12 pack-on requests, 5 pack-off, the pack-off median request input 6,619
    assert terms["extra_requests"] == Measure((12 - 5) * 6619)
    # Copilot's listed instruction rows carry no character count (the reader counts their text in the system part),
    # so the prefix, and the tokens per character every attributed term needs, is not recorded: never a guess.
    unpriced = Measure(None, "not recorded: prompt part instruction_file has no character count")
    assert terms["fixed_prefix"] == terms["pack_reads"] == terms["skill_loads"] == unpriced
    assert isinstance(terms["reasoning_output"].value, int)
    assert h.delta_total.value == sum(m.value for m in terms.values() if m.value is not None)
    assert {f.path: f.component for f in pc.components} == {
        "AGENTS.md": "agents_md", ".agents/skills/implement/reference/co-s0.md": "skill",
        ".github/instructions/testing-strategy.instructions.md": "always_applied_instruction",
        ".github/instructions/observability-and-instrumentation.instructions.md": "scoped_instruction"}
    assert pc.top_files == () and pack_cost.render(pc).count(unpriced.reason) >= 3


def test_per_file_tokens_are_labelled_and_the_task_readme_is_not_a_pack_file(fakes):
    pc = pack_cost.build(_views())
    files = {(f.path, f.harness): f for f in pc.top_files}
    a = files[(".github/instructions/a.instructions.md", "claude-code")]
    assert (a.component, a.tokens_per_cell.value, a.requests_carried.value, a.delivery) == (
        "always_applied_instruction", 6000, 3, "inlined")
    k = files[("docs/knowledge/k.md", "claude-code")]
    assert (k.component, k.tokens_per_cell.value, k.requests_carried.value, k.delivery) == (
        "knowledge_doc", 400, 2, "on-demand")
    assert not any(f.path == "README.md" for f in pc.top_files)
    assert "Tokens per cell, Inferred (tokens per character)" in pack_cost.render(pc)


# --- the component map ---------------------------------------------------------------------------------------------
def _git(repo: Path, *args: str) -> str:
    return gitsafe.git(list(args), cwd=repo, timeout=60, identity=True).stdout.strip()


@pytest.fixture
def pack_repo(tmp_path):
    repo = tmp_path / "pack"
    for rel, text in PACK_FILES.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8", newline="\n")
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "pack")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_the_component_map_reads_the_pack_source_through_gitsafe(pack_repo, monkeypatch):
    repo, commit = pack_repo
    seen = []
    real = gitsafe.git
    monkeypatch.setattr(gitsafe, "git", lambda args, **kw: (seen.append(args), real(args, **kw))[1])
    src = pack_cost.pack_source({"arms": {"off": {"pack": None}, "on": {"pack": {"source": str(repo), "commit": commit}}}})
    assert src.reason is None and src.label == f"{repo}@{commit}"
    classes = {p: pack_cost.classify(p, src.read(p)) for p in PACK_FILES}
    assert classes == {
        ".github/instructions/a.instructions.md": "always_applied_instruction",
        ".github/instructions/b.instructions.md": "scoped_instruction",
        "AGENTS.md": "agents_md", ".claude/skills/x/SKILL.md": "skill", ".claude/agents/p.md": "persona",
        "docs/knowledge/k.md": "knowledge_doc", ".claude/hooks/h.py": "hook", "tools/z.txt": "other"}
    assert any(a[:1] == ["show"] and a[1].startswith(commit) for a in seen)


def test_an_unreadable_pack_source_gives_unclassified_with_its_reason(fakes, tmp_path, monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(pack_cost, "cell_facts", _facts)
    monkeypatch.setattr(context_growth, "request_series", _series)
    monkeypatch.setattr(tool_phases, "carry_until_compaction", _carry)
    views = _views()
    views[0].plan["arms"]["on"]["pack"] = {"source": str(tmp_path / "absent"), "commit": PACK["commit"]}
    pc = pack_cost.build(views)
    assert pc.pack_source_reason == "not recorded: pack source not readable"
    assert pc.components and {f.component for f in pc.components} == {"unclassified"}
    assert _term(_harness(pc, "claude-code"), "residual").median.value == RESIDUAL  # the decomposition still renders
    assert "not recorded: pack source not readable" in pack_cost.render(pc)


# --- tuning candidates ---------------------------------------------------------------------------------------------
def test_a_candidate_fires_exactly_at_its_threshold_and_not_below(fakes):
    pc = pack_cost.build(_views())
    hooks = {c.harness for c in pc.candidates if c.rule == "hook_wall_share"}
    assert hooks == {"claude-code"}  # 3,000 / 15,000 = 0.2 fires; 3,000 / 15,001 (copilot, grok) does not
    assert pc.thresholds["HOOK_WALL_SHARE"] == str(pack_cost.HOOK_WALL_SHARE) == "0.20"
    hook = next(c for c in pc.candidates if c.rule == "hook_wall_share")
    assert hook.threshold == "HOOK_WALL_SHARE = 0.20" and "0.2" in hook.figure
    rules = {(c.rule, c.harness) for c in pc.candidates}
    assert ("always_applied_share", "claude-code") in rules and ("skill_catalogue_share", "claude-code") in rules
    page = pack_cost.render(pc)
    for name, value in pc.thresholds.items():
        assert f"<code>{name}</code>" in page and value in page


def test_no_candidate_names_an_effect_it_did_not_measure(fakes):
    for c in pack_cost.build(_views()).candidates:
        assert "would save" not in c.lever and "saves" not in c.lever


# --- the outcome header --------------------------------------------------------------------------------------------
def test_the_outcome_header_repeats_the_lean_summary_per_harness(fakes):
    views = _views()
    pc = pack_cost.build(views)
    summary = lean.build([lean.BatchInput(v, None, None, None, None) for v in views], None)
    want = {r.harness: (r.statement, r.effect, r.lo, r.hi, r.mde) for r in summary.rows}
    assert {o.harness: (o.statement, o.effect, o.lo, o.hi, o.mde) for o in pc.outcomes} == want
    header = re.search(r'<section id="header">.*?</section>', pack_cost.render(pc), re.DOTALL).group(0)
    for r in summary.rows:
        assert f"MDE {r.mde}" in header and html.escape(r.statement) in header


def test_a_non_lean_run_says_why_it_has_no_outcome(fakes):
    views = _views()
    views[0].plan["ring"] = {"tag": "other"}
    pc = pack_cost.build(views)
    assert pc.outcomes == () and "ring tag" in pc.outcome_reason


# --- the analyst section ---------------------------------------------------------------------------------------------
def _args(tmp_path, analysis: str | None, monkeypatch) -> argparse.Namespace:
    monkeypatch.setattr(pack_cost, "load_views", lambda args: _views())
    md = None
    if analysis is not None:
        md = tmp_path / "tuning.md"
        md.write_text(analysis, encoding="utf-8")
    return argparse.Namespace(pack_cost=["b1"], out=str(tmp_path / "pack-cost.html"), open=False,
                              analysis=None if md is None else str(md), runs=str(tmp_path / "runs"), root=str(tmp_path))


def test_analysis_is_embedded_under_its_heading_through_publish(fakes, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(publish, "publish", lambda html, out, open: (calls.append((html, out, open)), "not opened")[1])
    args = _args(tmp_path, f"Claude Code's residual is {RESIDUAL:,} tokens.\n", monkeypatch)
    assert pack_cost.cli_main(args) == 0
    (page, out, opened), = calls
    assert out == Path(args.out) and opened is False
    assert "<h2>Analysis (written by an analyst, not generated)</h2>" in page and "777" in page


def test_an_analysis_citing_an_absent_number_is_refused_with_the_number_listed(fakes, tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "publish", lambda *a: pytest.fail("published a refused page"))
    args = _args(tmp_path, "Copilot's hooks cost 173 s per cell.\n", monkeypatch)
    with pytest.raises(BenchError) as exc:
        pack_cost.cli_main(args)
    assert "173" in str(exc.value)


def test_without_analysis_the_page_is_complete_without_that_section(fakes):
    page = pack_cost.render(pack_cost.build(_views()))
    assert 'id="analysis"' not in page and 'id="decomposition"' in page


# --- the page ------------------------------------------------------------------------------------------------------
def test_the_page_carries_no_price(fakes):
    page = pack_cost.render(pack_cost.build(_views()))
    for refused in ("$", "USD", "cost_usd"):
        assert refused not in page


def _golden_page() -> str:
    return pack_cost.render(pack_cost.build(_views()))


def test_the_golden_is_byte_equal_on_re_render(fakes):
    page = _golden_page()
    if os.environ.get("HB_REGOLD") == "1":  # re-capture: HB_REGOLD=1 uv run pytest tests/test_pack_cost.py
        GOLDEN.write_text(page, encoding="utf-8", newline="\n")
    assert page == GOLDEN.read_text(encoding="utf-8")
    assert page == _golden_page()


def test_the_golden_root_reads_nothing_from_the_repositorys_bench():
    assert FROZEN_ROOT.name == "bench-root" and (FROZEN_ROOT / "bench" / "profiles" / "copilot.yaml").is_file()


@pytest.fixture
def pc_page(tmp_path, fakes):
    sync_playwright = pytest.importorskip("playwright.sync_api").sync_playwright
    path = tmp_path / "pack-cost.html"
    md = "Claude Code's always-applied file is 6,000 tokens per cell.\n"
    pc = pack_cost.build(_views())
    from harness_bench.report import analysis
    section = analysis.check_and_render(md, analysis.table_numbers(pack_cost.render(pc)))
    path.write_text(pack_cost.render(pc, section), encoding="utf-8", newline="\n")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(path.as_uri())
        yield page
        browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_reports_0_violations_for_the_pack_cost_page_in_light_and_dark(pc_page, scheme):
    assert pc_page.locator("section").count() >= 7
    pc_page.emulate_media(color_scheme=scheme)
    pc_page.evaluate(AXE.read_text(encoding="utf-8"))
    found = pc_page.evaluate(
        "axe.run(document, {runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']}).then(r =>"
        " ({violations: r.violations.map(v => v.id + ': ' + v.nodes.length), passes: r.passes.length}))")
    assert found["passes"] > 0, "axe ran no rule on the page"
    assert found["violations"] == []


