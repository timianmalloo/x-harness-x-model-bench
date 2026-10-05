"""Power analysis references (W1-H §11.1). Literal z lives here, not in the module."""

import ast
import re
from decimal import Decimal
from pathlib import Path
from statistics import NormalDist

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from harness_bench import power
from harness_bench.errors import BenchError

# Design §11.1 literals. They are not read from statistics.NormalDist.
Z_ALPHA = 1.959963984540054
Z_BETA = 0.8416212335729143
Z_ALPHA_OVER_90 = 3.2608

POWER_SOURCE = Path(__file__).resolve().parents[1] / "src" / "harness_bench" / "power.py"
HARNESSES = ["claude-code", "codex", "copilot"]
COMPARISONS = [["off", "x"], ["off", "y"], ["x", "y"]]


def hand_unpaired(p0: float, p1: float, z_alpha: float, z_beta: float) -> float:
    delta = p1 - p0
    pbar = (p0 + p1) / 2.0
    qbar = 1.0 - pbar
    term = z_alpha * (2.0 * pbar * qbar) ** 0.5 + z_beta * (p0 * (1.0 - p0) + p1 * (1.0 - p1)) ** 0.5
    return (term * term) / (delta * delta)


def hand_paired(psi: float, delta: float, z_alpha: float, z_beta: float) -> float:
    term = z_alpha * (psi ** 0.5) + z_beta * ((psi - delta * delta) ** 0.5)
    return (term * term) / (delta * delta)


def _property(pairing: str) -> dict:
    body = {
        "primary_metric": "property_check_pass",
        "tasks": ["t1", "t2"],
        "control_rate": Decimal("0.5"),
        "mde": Decimal("0.2"),
    }
    if pairing == "task-harness-rep":
        body["discordance"] = Decimal("0.28")
    return body


def _campaign(method: str = "none", m: int = 1, pairing: str = "unpaired") -> dict:
    return {
        "alpha": Decimal("0.05"),
        "power": Decimal("0.8"),
        "correction": {"method": method, "m": m},
        "pairing_unit": pairing,
        "harnesses": list(HARNESSES),
        "comparisons": [list(pair) for pair in COMPARISONS],
        "slots": 2,
        "mean_wall_per_cell_s": 130.44,
        "mean_tokens_per_cell": 1000,
        "properties": {"security": _property(pairing)},
    }


def _five(method: str, m: int, pairing: str) -> dict:
    inputs = _campaign(method, m, pairing)
    inputs["properties"] = {f"p{i}": _property(pairing) for i in range(5)}
    return inputs


def _only(results):
    assert len(results) == 1
    return next(iter(results.values()))


def _ns(result) -> list[int]:
    return [row["n"] for row in result.required_pairs]


def check_references(analyse) -> None:
    """The three closed-form sizes. A one-sided z fails this; the real analyse passes it."""
    assert _ns(_only(analyse(_campaign()))) == [93] * (len(HARNESSES) * len(COMPARISONS))
    paired = _only(analyse(_campaign(pairing="task-harness-rep")))
    assert _ns(paired) == [53] * (len(HARNESSES) * len(COMPARISONS))
    corrected = _only(analyse(_campaign("bonferroni", 45, "task-harness-rep")))
    assert _ns(corrected) == [115] * (len(HARNESSES) * len(COMPARISONS))


def _level_rules_loaded_outside_level_for() -> list[int]:
    tree = ast.parse(POWER_SOURCE.read_text(encoding="utf-8"))
    bad: list[int] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.function: str | None = None

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            previous = self.function
            self.function = node.name
            self.generic_visit(node)
            self.function = previous

        def visit_Name(self, node: ast.Name) -> None:
            if node.id == "LEVEL_RULES" and isinstance(node.ctx, ast.Load) and self.function != "level_for":
                bad.append(node.lineno)

    Visitor().visit(tree)
    return bad


def test_unpaired_reference_93():
    exact = power.n_unpaired_exact(0.5, 0.7, 0.05, 0.8)
    assert exact == pytest.approx(92.99884, abs=1e-4)
    assert hand_unpaired(0.5, 0.7, Z_ALPHA, Z_BETA) == pytest.approx(exact, abs=1e-4)
    result = _only(power.analyse(_campaign()))
    assert _ns(result) == [93] * (len(HARNESSES) * len(COMPARISONS))


def test_paired_reference_53():
    exact = power.n_paired_exact(0.28, 0.20, 0.05, 0.8)
    assert exact == pytest.approx(52.52075, abs=1e-4)
    assert hand_paired(0.28, 0.20, Z_ALPHA, Z_BETA) == pytest.approx(exact, abs=1e-4)
    result = _only(power.analyse(_campaign(pairing="task-harness-rep")))
    assert result.required_pairs[0]["n"] == 53
    assert result.assumed == []
    with_spread = _campaign(pairing="task-harness-rep")
    with_spread["properties"]["security"]["sd"] = 1
    with_spread["properties"]["security"]["rep_spread"] = 0
    same = _only(power.analyse(with_spread))
    assert same.required_pairs[0]["n"] == result.required_pairs[0]["n"]
    assert not hasattr(same, "descriptive")
    assert not hasattr(same, "sd")
    assert not hasattr(same, "rep_spread")


def test_bonferroni_reference_115():
    alpha = 0.05 / 45
    exact = power.n_paired_exact(0.28, 0.20, alpha, 0.8)
    assert exact == pytest.approx(114.24879, abs=1e-4)
    # Four-place z is only good to the integer; the module pin is exact.
    assert hand_paired(0.28, 0.20, Z_ALPHA_OVER_90, Z_BETA) == pytest.approx(115, abs=1)
    result = _only(power.analyse(_campaign("bonferroni", 45, "task-harness-rep")))
    assert result.required_pairs[0]["n"] == 115


def test_holm_is_sized_like_bonferroni():
    holm = _only(power.analyse(_campaign("holm", 45, "task-harness-rep")))
    bonferroni = _only(power.analyse(_campaign("bonferroni", 45, "task-harness-rep")))
    uncorrected = _only(power.analyse(_campaign("none", 45, "task-harness-rep")))
    assert holm.required_pairs[0]["n"] == 115
    assert bonferroni.required_pairs[0]["n"] == 115
    assert uncorrected.required_pairs[0]["n"] == 53


def test_level_rule_table():
    alpha = Decimal("0.05")
    assert power.level_for("bonferroni", alpha, 45) == (alpha / 45, "alpha/m (Bonferroni)")
    assert power.level_for("holm", alpha, 45) == (alpha / 45, "alpha/m (Bonferroni; Holm's first step)")
    assert power.level_for("none", alpha, 45) == (alpha, "alpha (no correction)")
    result = _only(power.analyse(_campaign("holm", 45, "task-harness-rep")))
    assert result.alpha_per_test == alpha / 45
    assert result.level_rule == "alpha/m (Bonferroni; Holm's first step)"
    assert _level_rules_loaded_outside_level_for() == []


def test_alpha_and_power_echo_exactly():
    result = _only(power.analyse(_campaign("holm", 45, "task-harness-rep")))
    assert result.alpha == Decimal("0.05")
    assert result.power == Decimal("0.8")
    assert result.alpha != result.alpha_per_test


def test_mde_solves_back_within_0_005():
    unpaired = _only(power.analyse(_campaign()))
    solved_93 = power.mde_for(93, lambda delta: power.n_unpaired_exact(0.5, 0.5 + delta, 0.05, 0.8))
    assert abs(unpaired.mde - 0.20) < 0.005
    assert abs(solved_93 - 0.20) < 0.005
    assert hand_unpaired(0.5, 0.5 + solved_93, Z_ALPHA, Z_BETA) == pytest.approx(
        power.n_unpaired_exact(0.5, 0.5 + solved_93, 0.05, 0.8), abs=1e-3)

    paired = _only(power.analyse(_campaign(pairing="task-harness-rep")))
    solved_53 = power.mde_for(53, lambda delta: power.n_paired_exact(0.28, delta, 0.05, 0.8))
    assert abs(paired.mde - 0.20) < 0.005
    assert abs(solved_53 - 0.20) < 0.005
    assert hand_paired(0.28, solved_53, Z_ALPHA, Z_BETA) == pytest.approx(
        power.n_paired_exact(0.28, solved_53, 0.05, 0.8), abs=1e-3)

    corrected = _only(power.analyse(_campaign("bonferroni", 45, "task-harness-rep")))
    alpha = 0.05 / 45
    solved_115 = power.mde_for(115, lambda delta: power.n_paired_exact(0.28, delta, alpha, 0.8))
    assert abs(corrected.mde - 0.20) < 0.005
    assert abs(solved_115 - 0.20) < 0.005
    assert hand_paired(0.28, solved_115, Z_ALPHA_OVER_90, Z_BETA) == pytest.approx(
        power.n_paired_exact(0.28, solved_115, alpha, 0.8), abs=1)


def test_seeded_wrong_one_sided_variant_fails(monkeypatch):
    check_references(power.analyse)
    real = NormalDist.inv_cdf

    def one_sided(self, quantile: float) -> float:
        # A two-sided critical value (q > 0.9) becomes the one-sided z. Power's 0.8 is left alone.
        if quantile >= 0.9:
            quantile = 2 * quantile - 1
        return real(self, quantile)

    monkeypatch.setattr(NormalDist, "inv_cdf", one_sided)
    with pytest.raises(AssertionError):
        check_references(power.analyse)


def test_assumed_control_rate_is_labelled():
    labelled_inputs = _campaign()
    labelled_inputs["properties"]["security"]["control_rate"] = "assumed"
    labelled = _only(power.analyse(labelled_inputs))
    assert labelled.assumed == ["control_rate"]
    assert labelled.required_pairs[0]["n"] == 93

    given = _only(power.analyse(_campaign()))
    assert given.assumed == []

    paired_inputs = _campaign(pairing="task-harness-rep")
    paired_inputs["properties"]["security"]["discordance"] = "assumed"
    paired = _only(power.analyse(paired_inputs))
    assert paired.assumed == ["discordance"]
    assert paired.required_pairs[0]["n"] == power._snap(power.n_paired_exact(0.5, 0.2, 0.05, 0.8))


@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=6, max_value=20))
@example(6)
@example(20)
def test_mde_roundtrip_property(n: int):
    """n_for(mde_for(n)) <= n, and 0.005 less effect needs more than n - 2. n stays <= 20 so hi=0.5 is too low."""
    psi = 0.999

    def n_for(delta: float) -> float:
        return power.n_paired_exact(psi, delta, 0.05, 0.8)

    mde = power.mde_for(n, n_for)
    assert n_for(mde) <= n
    assert n_for(mde - 0.005) > n - 2


def _psi_too_small(inputs: dict) -> None:
    inputs["pairing_unit"] = "task-harness-rep"
    inputs["properties"]["security"]["discordance"] = Decimal("0.03")
    inputs["properties"]["security"]["mde"] = Decimal("0.2")


_INVALID = [
    ("alpha-0", "alpha", lambda inputs: inputs.update(alpha=Decimal(0))),
    ("alpha-1", "alpha", lambda inputs: inputs.update(alpha=Decimal(1))),
    ("power", "power", lambda inputs: inputs.update(power=Decimal("1.2"))),
    ("m", "m", lambda inputs: inputs["correction"].update(m=0)),
    ("method", "method", lambda inputs: inputs["correction"].update(method="sidak")),
    ("pairing", "pairing", lambda inputs: inputs.update(pairing_unit="paired")),
    ("psi", "psi", _psi_too_small),
    ("tasks", "tasks", lambda inputs: inputs["properties"]["security"].update(tasks=[])),
    ("mde", "mde", lambda inputs: inputs["properties"]["security"].update(mde=Decimal(0))),
    ("slots-0", "slots", lambda inputs: inputs.update(slots=0)),
    ("slots-absent", "slots", lambda inputs: inputs.pop("slots")),
    ("planned", "planned_reps_per_task", lambda inputs: inputs.update(planned_reps_per_task=0)),
    ("sd", "sd", lambda inputs: inputs["properties"]["security"].update(sd=-1)),
    ("rep-spread", "rep_spread", lambda inputs: inputs["properties"]["security"].update(rep_spread=-1)),
    ("control_rate-0", "control_rate", lambda inputs: inputs["properties"]["security"].update(control_rate=Decimal(0))),
    ("control_rate-1", "control_rate", lambda inputs: inputs["properties"]["security"].update(control_rate=Decimal(1))),
    ("control_rate-1.5", "control_rate",
     lambda inputs: inputs["properties"]["security"].update(control_rate=Decimal("1.5"))),
    ("mde-over-rate", "mde", lambda inputs: _rate_and_mde(inputs, "unpaired", "0.9", "0.2", None)),
    ("mde-over-assumed-rate", "mde", lambda inputs: _rate_and_mde(inputs, "unpaired", "assumed", "0.6", None)),
    ("mde-over-rate-paired-assumed", "mde",
     lambda inputs: _rate_and_mde(inputs, "task-harness-rep", "0.9", "0.2", "assumed")),
]


def _rate_and_mde(inputs: dict, pairing: str, rate: str, mde: str, discordance: str | None) -> None:
    """Both paths that compute p1 = p0 + mde (H1a carry-over 1): unpaired, and paired with discordance assumed."""
    inputs["pairing_unit"] = pairing
    body = inputs["properties"]["security"]
    body["control_rate"] = rate if rate == "assumed" else Decimal(rate)
    body["mde"] = Decimal(mde)
    if discordance is None:
        body.pop("discordance", None)
    else:
        body["discordance"] = discordance


def test_a_rate_plus_mde_of_exactly_one_is_legal():
    """p0 + mde == 1 gives p1 = 1 and a finite n; only above 1 is refused."""
    inputs = _campaign(pairing="unpaired")
    inputs["properties"]["security"].update(control_rate=Decimal("0.9"), mde=Decimal("0.1"))
    assert _only(power.analyse(inputs)).required_pairs[0]["n"] > 0


@pytest.mark.parametrize(
    ("field", "change"),
    [(field, change) for _name, field, change in _INVALID],
    ids=[name for name, _field, _change in _INVALID],
)
def test_power_inputs_each_invalid_field_is_named(field, change):
    inputs = _campaign(pairing="task-harness-rep")
    change(inputs)
    with pytest.raises(BenchError) as caught:
        power.analyse(inputs)
    assert caught.value.code == "HB-PWR-001"
    assert re.search(rf"\b{re.escape(field)}\b", caught.value.message)


def test_cells_hours_tokens_reference_table():
    specs = (
        ("none", 1, "task-harness-rep", 2430, 44.02),
        ("none", 1, "unpaired", 4230, 76.63),
        ("bonferroni", 45, "task-harness-rep", 5220, 94.57),
    )
    for method, m, pairing, cells, hours in specs:
        results = power.analyse(_five(method, m, pairing))
        assert sum(row.cells for row in results.values()) == cells
        assert sum(row.hours for row in results.values()) == pytest.approx(hours, abs=0.05)
        assert sum(row.tokens for row in results.values()) == cells * 1000


def test_reachable_mde_when_plan_is_short():
    inputs = _campaign(pairing="task-harness-rep")
    inputs["planned_reps_per_task"] = 10
    result = _only(power.analyse(inputs))

    def sizer(delta: float) -> float:
        return power.n_paired_exact(0.28, delta, 0.05, 0.8)

    assert result.reachable_mde == pytest.approx(power.mde_for(20, sizer), abs=1e-9)
    assert result.reachable_mde > result.mde
    absent = _only(power.analyse(_campaign(pairing="task-harness-rep")))
    assert absent.reachable_mde is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [(93.0000000001, 93), (93.001, 94), (93.0, 93)],
    ids=["epsilon", "above", "exact"],
)
def test_snap_at_the_integer_edge(value, expected):
    assert power._snap(value) == expected
