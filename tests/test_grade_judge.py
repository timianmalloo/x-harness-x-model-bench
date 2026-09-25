"""The judge grader (design phase3-gateway-judges sections 4.1, 6, 10 and 16 row s3; W3-GW-I slice 3).

T-GW-12, 20, 21 and 22. The grader runs through the real grading pass (`runner.run_pass`) on a real archived run
(`archived_runs`). The one judge call that is made replays a committed placeholder record through the fake judge CLI
(`fixtures/gateway/fake_judge_cli.py`) launched by the real headless backend, and the real readers decide the outcome
(directive D7). No real model CLI is launched and no network call is made. The credential is a synthetic temp file
and the operator's identifiers are random synthetic strings (R-42). The stipulation is the committed test fixture copy
`fixtures/gateway/gateway.yaml`: bench/gateway.yaml waits for the Leader's measured turn (R-70).
"""

from decimal import Decimal

from harness_bench.gateway import pipeline
from harness_bench.grade import Score, judge

CLAUDE, COPILOT = "claude-fable-5-1", "gpt-6-sol"
DISAGREE = "judges disagree by 2 steps"


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
