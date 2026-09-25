"""The judge grader (design phase3-gateway-judges sections 4.1, 6, 10 and 16 row s3; W3-GW-I slice 3).

T-GW-12, 20, 21 and 22. The grader runs through the real grading pass (`runner.run_pass`) on a real archived run
(`archived_runs`). The one judge call that is made replays a committed placeholder record through the fake judge CLI
(`fixtures/gateway/fake_judge_cli.py`) launched by the real headless backend, and the real readers decide the outcome
(directive D7). No real model CLI is launched and no network call is made. The credential is a synthetic temp file
and the operator's identifiers are random synthetic strings (R-42). The stipulation is the committed test fixture copy
`fixtures/gateway/gateway.yaml`: bench/gateway.yaml waits for the Leader's measured turn (R-70).
"""

import dataclasses
import json
import shutil
import sys
from decimal import Decimal
from pathlib import Path
from secrets import token_hex

import pytest
import yaml
from archived_runs import GOOD, ROOT, make_root, make_run, pass_rows

from harness_bench import egress, ledger, profiles, tools, views
from harness_bench.gateway import pipeline
from harness_bench.grade import Score, judge, runner

FIX = Path(__file__).resolve().parent / "fixtures" / "gateway"
CLAUDE, COPILOT, CODEX = "claude-fable-5-1", "gpt-6-sol", "gpt-6-sol"
DISAGREE = "judges disagree by 2 steps"
JUDGED = {"honest_completion_claims", "error_handling", "goal_drift_slope", "unrequested_behaviour",
          "assumption_disclosure", "spec_quality", "adr_quality", "handoff_fidelity", "mast_failure_codes"}
NOTE = "No mechanical oracle applies: an architecture note is judged against its rubric."
ITEMS = tuple(f"adr_quality#{n}" for n in range(1, 8))


def judged_root(tmp_path, judges: tuple[int, ...] | None = (0, 1)) -> Path:
    """A bench root whose X1 is judged: graders [judge]; adr_quality carries C1's 7-item rubric for X1 (the catalog
    fields of design section 13 and graders `rubrics:`), judging slug.py; `judges` picks the fixture stipulation's
    entries (None: no bench/gateway.yaml)."""
    root = make_root(tmp_path)
    shutil.copy(ROOT / "bench" / "pack-markers.txt", root / "bench" / "pack-markers.txt")  # the scrub's denylist
    task_path = root / "tasks" / "X1" / "task.yaml"
    task = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    task_path.write_text(yaml.safe_dump(task | {"graders": ["judge"]}, sort_keys=False), encoding="utf-8")
    catalog = yaml.safe_load((root / "bench" / "metrics.yaml").read_text(encoding="utf-8"))
    for area in catalog["areas"].values():
        for m in area["metrics"]:
            if m["id"] == "adr_quality":
                m.update(rubrics={"X1": "adr_quality.md"}, artifact=["slug.py"], scale=1, note=NOTE)
    (root / "bench" / "metrics.yaml").write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    (root / "bench" / "rubrics").mkdir()
    shutil.copy(ROOT / "tasks" / "C1" / "oracle" / "rubric.md", root / "bench" / "rubrics" / "adr_quality.md")
    if judges is not None:
        stipulation = yaml.safe_load((FIX / "gateway.yaml").read_text(encoding="utf-8"))
        stipulation["judges"] = [stipulation["judges"][i] for i in judges]
        (root / "bench" / "gateway.yaml").write_text(yaml.safe_dump(stipulation, sort_keys=False), encoding="utf-8")
    return root


def judged_pass(root, tmp_path) -> tuple[Path, str, dict[str, tuple]]:
    """One pass over a one-cell run: (run folder, grading id, judged metric -> (value, reason))."""
    run_dir = make_run(root, tmp_path, {"a": GOOD}, combos={"a": "combo-placeholder"})
    gid = runner.run_pass(run_dir, root).grading_id
    return run_dir, gid, {r["metric_id"]: (r["value"], r["reason"]) for r in pass_rows(run_dir, "scores", gid)}


def uses(run_dir, gid) -> list[tuple]:
    path = run_dir / "verdict_uses" / f"{gid}.jsonl"
    rows = pass_rows(run_dir, "verdict_uses", gid) if path.is_file() else []
    return sorted((r["cell_id"], r["item_id"], r["judge_or_matcher"], r["outcome"], r["code"]) for r in rows)


def recorded(*scores: int) -> pipeline.Result:
    """A recorded lookup (a hit) whose verdict set scores item n with scores[n - 1]."""
    return pipeline.Result("hit", None, "k" * 64, "e" * 64,
                           tuple({"item": n, "score": s, "rationale": "r"} for n, s in enumerate(scores, 1)))


# --------------------------------------------------------------------------------------------------- T-GW-20
def test_t_gw_20_the_synthesis_table_is_the_mean_within_one_step_and_not_recorded_at_two():
    synthesize = getattr(judge, "synthesize", None)
    assert synthesize is not None, "grade.judge.synthesize (design section 10.1) is not built"
    table = {(a, b): synthesize(a, b) for a in range(3) for b in range(3)}
    assert table == {
        (0, 0): Score(Decimal("0.0"), None), (0, 1): Score(Decimal("0.5"), None), (0, 2): Score(None, DISAGREE),
        (1, 0): Score(Decimal("0.5"), None), (1, 1): Score(Decimal("1.0"), None), (1, 2): Score(Decimal("1.5"), None),
        (2, 0): Score(None, DISAGREE), (2, 1): Score(Decimal("1.5"), None), (2, 2): Score(Decimal("2.0"), None)}
    assert [str(table[k].value) for k in ((0, 0), (1, 2), (2, 2))] == ["0.0", "1.5", "2.0"]  # scale 1


def test_t_gw_20_an_item_needs_both_judges_recorded_and_names_the_one_that_is_not():
    item = getattr(judge, "item_score", None)
    assert item is not None, "grade.judge.item_score (design section 10.1) is not built"
    both = ((CLAUDE, recorded(2, 0)), (COPILOT, recorded(1, 2)))
    assert [item(*both, n) for n in (1, 2)] == [Score(Decimal("1.5"), None), Score(None, DISAGREE)]
    # while the second judge is not qualified, or not stipulated at all, no single verdict is a judged score (R-63 b)
    assert item((CLAUDE, recorded(2)), (COPILOT, pipeline.Result("failed", "HB-GW-007")), 1) == \
        Score(None, "second judge not qualified")
    assert item((CLAUDE, recorded(2)), None, 1) == Score(None, "second judge not qualified")
    # a judge that is not recorded is named with its outcome and code (design section 10.1)
    assert item((CLAUDE, pipeline.Result("failed", "HB-GW-002")), (COPILOT, recorded(2)), 1) == \
        Score(None, "judge claude-fable-5-1: failed HB-GW-002")
    assert item((CLAUDE, recorded(2)), (COPILOT, pipeline.Result("not_allowed")), 1) == \
        Score(None, "judge gpt-6-sol: not_allowed")


def test_t_gw_20_the_metric_is_the_sum_of_all_seven_items_or_not_recorded_naming_them():
    metric = getattr(judge, "metric_score", None)
    assert metric is not None, "grade.judge.metric_score (design section 10.2) is not built"
    halves = {n: Score(Decimal(v), None) for n, v in enumerate(("2.0", "1.5", "0.0", "1.0", "2.0", "0.5", "1.5"), 1)}
    assert metric(halves) == Score(Decimal("8.5"), None)
    gaps = halves | {3: Score(None, DISAGREE), 6: Score(None, "judge gpt-6-sol: failed HB-GW-001"),
                     7: Score(None, DISAGREE)}
    assert metric(gaps) == Score(None, "items 3, 7: judges disagree by 2 steps; items 6: judge gpt-6-sol: failed HB-GW-001")


# --------------------------------------------------------------------------------------------------- T-GW-22
def test_t_gw_22_with_no_stipulation_every_judged_metric_is_no_qualified_judge_and_no_lookup_is_made(tmp_path):
    root = judged_root(tmp_path, judges=None)  # bench/gateway.yaml is not in the tree (R-70)
    run_dir, gid, got = judged_pass(root, tmp_path)
    assert got == {m: (None, "no qualified judge") for m in JUDGED}
    assert uses(run_dir, gid) == []


@pytest.mark.parametrize("judges", [(0, 1), (0,)], ids=["second judge unqualified", "no second judge"])
def test_t_gw_22_na_reasons_no_rubric_and_second_judge_not_qualified(tmp_path, judges):
    root = judged_root(tmp_path, judges=judges)
    run_dir, gid, got = judged_pass(root, tmp_path)
    assert got == {**{m: (None, "no rubric for this task") for m in JUDGED - {"adr_quality"}},
                   "adr_quality": (None, "items 1, 2, 3, 4, 5, 6, 7: second judge not qualified")}
    # one row per (cell, item, judge): the qualified judge's cache-only miss, and the unqualified judge never spawned
    assert uses(run_dir, gid) == sorted([("a", i, CLAUDE, "not_allowed", None) for i in ITEMS] +
                                        [("a", i, CODEX, "failed", "HB-GW-007") for i in ITEMS if 1 in judges])


# --------------------------------------------------------------------------------------------------- T-GW-21
def test_t_gw_21_verdict_uses_is_append_only_and_a_rewrite_fails_verify(tmp_path):
    run_dir, gid, _ = judged_pass(judged_root(tmp_path), tmp_path)
    [done] = [e for e in ledger.read_segment(run_dir / "events" / f"{gid}.jsonl") if e["kind"] == "grading.completed"]
    assert "verdict_uses" in done["heads"]  # the pass seals its own segment and records its head (ADR-0006, R-2)
    assert [f for f in views.verify(run_dir) if f.level == "error"] == []
    path = run_dir / "verdict_uses" / f"{gid}.jsonl"
    lines = path.read_bytes().splitlines(keepends=True)
    row = json.loads(lines[0])
    lines[0] = ledger.canonical(row | {"outcome": "hit"}) + b"\n"  # a rewrite of one recorded lookup
    path.write_bytes(b"".join(lines))
    errors = [f for f in views.verify(run_dir) if f.level == "error"]
    assert [(f.code, f.message.split(":")[0]) for f in errors] == [("HB-LED-002", f"verdict_uses/{gid}.jsonl")]


# --------------------------------------------------------------------------------------------------- T-GW-12
ANSWER = (2, 1, 2, 0, 1, 2, 1)  # the fake judge's scores for items 1..7


def fake_calls(tmp_path, cells_root: Path, calls_type):
    """The call environment of a pass that may call a judge: the fake judge CLI replaying the committed placeholder
    record `claude-fable-text` with a 7-item answer on stdout; a synthetic credential and synthetic operator."""
    stdout = json.loads((FIX / "records" / "claude-fable-text.stdout.json").read_text(encoding="utf-8"))
    stdout["result"] = json.dumps({"items": [{"item": n, "score": s, "rationale": f"placeholder rationale {n}"}
                                             for n, s in enumerate(ANSWER, 1)]})
    (tmp_path / "answer.stdout.json").write_text(json.dumps(stdout), encoding="utf-8")
    credential = tmp_path / "synthetic-login" / ".credentials.json"
    credential.parent.mkdir(parents=True)
    credential.write_text(json.dumps({"placeholder": token_hex(8)}), encoding="utf-8")
    cfg = {"record": str(FIX / "records" / "claude-fable-text.record.jsonl"),
           "stdout": str(tmp_path / "answer.stdout.json"), "capture": str(tmp_path / "capture")}
    profile = profiles.Profile(harness="claude-code", home_env="CLAUDE_CONFIG_DIR", credential_source=credential,
                               credential_name=".credentials.json", command=("{exe}",),
                               env={"HB_FAKE_JUDGE": json.dumps(cfg)}, record_glob="projects/**/{session_id}.jsonl",
                               auxiliary_models=("claude-haiku-4-5",))
    build = tools.Build(harness="claude-code", version="2.1.282", exe=FIX / "fake_judge_cli.py", sha256="0" * 64,
                        adapter=None, adapter_version=None, adapter_sha256=None)
    operator = egress.Operator(email=f"op-{token_hex(6)}@example.invalid", username=f"u{token_hex(5)}",
                               home=f"C:\\Users\\u{token_hex(5)}")
    return calls_type(cells_root=cells_root, builds={"claude-code": build}, profiles={"claude-code": profile},
                      operator=operator, prefix=(sys.executable,))


def spawns(tmp_path) -> int:
    return len(list((tmp_path / "capture").glob("*.json")))


def test_t_gw_12_a_warm_regrade_spawns_no_judge_and_reads_the_same_entries(tmp_path, base, monkeypatch):
    grade, calls_type = getattr(judge, "grade", None), getattr(judge, "Calls", None)
    assert grade is not None and calls_type is not None, "grade.judge.grade and grade.judge.Calls are not built"
    calls = fake_calls(tmp_path, base / "cells", calls_type)
    # slice 4's `bench grade --allow-model-calls` sets the flag and supplies the call environment; stood in here
    monkeypatch.setitem(runner.GRADERS, "judge",
                        lambda inp: grade(dataclasses.replace(inp, allow_model_calls=True), calls))
    root = judged_root(tmp_path)
    run_dir = make_run(root, tmp_path, {"a": GOOD}, combos={"a": "combo-placeholder"})
    first = runner.run_pass(run_dir, root).grading_id
    assert spawns(tmp_path) == 1  # one call: the qualified judge's one request; the unqualified judge never spawned
    stored = pass_rows(run_dir, "verdict_uses", first)
    assert uses(run_dir, first) == sorted([("a", i, CLAUDE, "stored", None) for i in ITEMS] +
                                          [("a", i, CODEX, "failed", "HB-GW-007") for i in ITEMS])
    [key] = {(r["cache_key"], r["entry_sha256"]) for r in stored if r["outcome"] == "stored"}
    entry = json.loads((root / "cache" / "verdicts" / f"{key[0]}.json").read_text(encoding="utf-8"))
    assert [v["score"] for v in entry["verdicts"]] == list(ANSWER)
    [call] = [r for r in pass_rows(run_dir, "model_calls", first) if r["principal"] == "gateway"]
    assert (call["run_id"], call["cell_id"], call["model"], call["native_session_id"], call["output"]) == \
        ("r1", None, CLAUDE, entry["native_session_id"], 284)

    second = runner.run_pass(run_dir, root).grading_id
    assert spawns(tmp_path) == 1  # pass 2, calls allowed, spawned nothing: every lookup was a hit (R-58 c6)
    assert uses(run_dir, second) == sorted([("a", i, CLAUDE, "hit", None) for i in ITEMS] +
                                           [("a", i, CODEX, "failed", "HB-GW-007") for i in ITEMS])
    assert {(r["cache_key"], r["entry_sha256"]) for r in pass_rows(run_dir, "verdict_uses", second)
            if r["outcome"] == "hit"} == {key}
    assert [r for r in pass_rows(run_dir, "model_calls", second) if r["principal"] == "gateway"] == []
    export = [[(r["metric_id"], r["value"], r["reason"]) for r in sorted(pass_rows(run_dir, "scores", gid),
                                                                        key=lambda r: r["metric_id"])]
              for gid in (first, second)]
    assert ledger.canonical({"scores": export[0]}) == ledger.canonical({"scores": export[1]})
    assert {m: (v, r) for m, v, r in export[1]}["adr_quality"] == \
        (None, "items 1, 2, 3, 4, 5, 6, 7: second judge not qualified")
