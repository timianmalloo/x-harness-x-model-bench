"""The judge grader (design phase3-gateway-judges sections 4.1, 6, 10 and 16 row s3; W3-GW-I slice 3).

T-GW-12, 20, 21 and 22. The grader runs through the real grading pass (`runner.run_pass`) on a real archived run
(`archived_runs`). The one judge call that is made replays a committed placeholder record through the fake judge CLI
(`fixtures/gateway/fake_judge_cli.py`) launched by the real headless backend, and the real readers decide the outcome
(directive D7). No real model CLI is launched and no network call is made. The credential is a synthetic temp file
and the operator's identifiers are random synthetic strings (R-42). The stipulation is the committed test fixture copy
`fixtures/gateway/gateway.yaml`: bench/gateway.yaml waits for the Leader's measured turn (R-70).
"""

import shutil
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from archived_runs import GOOD, ROOT, make_root, make_run, pass_rows

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
