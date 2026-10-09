"""L-CONTRACT: the `LeanSummary` seam pinned to `docs/architecture-lean-benchmark.md`, *Contracts at the seams*.

Each dataclass's field names, order and annotations, the `ESTIMATE` values (LB-3's Inferred estimates) and the
`build` signature are copied from the architecture's block, never read from `lean.py`, so a drift on either side
fails here. L-SUM-A may change the contract only additively, on the Coordinator's ruling, and updates this pin then.
"""

import dataclasses
import importlib
import importlib.util
import inspect
from decimal import Decimal

import pytest

MODULE = "harness_bench.lean"

FIELDS = {
    "BatchInput": (
        ("view", "RunView"),
        ("run_wall_ns", "int | None"),
        ("grading_ns", "int | None"),
        ("cells_graded", "int | None"),
        ("first_cell_started_at", "datetime | None"),  # additive: Leader ruling on req-01M4H8D2JGF50ZP7F1Z65GR8B9
    ),
    "Prereg": (
        ("sha256", "str"),
        ("committed_at", "datetime | None"),
    ),
    "LeanSummary": (
        ("batches", "int"),
        ("run_ids", "tuple[str, ...]"),
        ("plan_hashes", "tuple[str, ...]"),
        ("prereg_status", "str"),
        ("rows", "tuple[LeanRow, ...]"),
        ("pooled", "LeanRow"),
        ("disagree", "bool"),
        ("properties", "tuple[PropertyRow, ...]"),
        ("checkpoint", "tuple[BatchCheckpoint, ...]"),
    ),
    "LeanRow": (
        ("combo", "str"),
        ("harness", "str"),
        ("model", "str"),
        ("effect", "Decimal | None"),
        ("lo", "Decimal | None"),
        ("hi", "Decimal | None"),
        ("mde", "Decimal"),
        ("pairs", "int"),
        ("planned_pairs", "int"),
        ("excluded", "tuple[tuple[str, str], ...]"),
        ("statement", "str"),
        ("token_ratio", "Interval | None"),
        ("ratio_excluded", "int"),
    ),
    "PropertyRow": (
        ("family", "str"),
        ("harness", "str"),
        ("off", "tuple[int, int]"),
        ("on", "tuple[int, int]"),
        ("direction", "Literal['up', 'down', 'same']"),  # the postponed annotation is stored unparsed (PEP 563)
    ),
    "BatchCheckpoint": (
        ("run_id", "str"),
        ("cells", "int"),
        ("run_min_per_cell", "Decimal | None"),
        ("grade_min_per_cell", "Decimal | None"),
        ("tokens_per_cell", "Mapping[tuple[str, str], Decimal | None]"),
        ("infra_failures", "Mapping[str, tuple[int, int, tuple[str, ...]]]"),
    ),
}

ESTIMATE = (
    ("run_min_per_cell", Decimal("1.12")),
    ("grade_min_per_cell", Decimal("1.16")),
    ("tokens_per_cell", 1_060_000),
)


def _lean():
    assert importlib.util.find_spec(MODULE) is not None, f"{MODULE} is absent (L-CONTRACT)"
    return importlib.import_module(MODULE)


@pytest.mark.parametrize("name", sorted(FIELDS))
def test_each_contract_dataclass_has_the_architecture_fields_in_order(name):
    cls = getattr(_lean(), name)
    assert dataclasses.is_dataclass(cls)
    assert tuple((f.name, f.type) for f in dataclasses.fields(cls)) == FIELDS[name]


@pytest.mark.parametrize("name", sorted(FIELDS))
def test_each_contract_dataclass_is_frozen(name):
    cls = getattr(_lean(), name)
    assert cls.__dataclass_params__.frozen is True


def test_estimate_holds_lb3s_inferred_values_exactly():
    estimate = _lean().ESTIMATE
    assert dataclasses.is_dataclass(estimate) and type(estimate).__dataclass_params__.frozen is True
    assert tuple((f.name, getattr(estimate, f.name)) for f in dataclasses.fields(estimate)) == ESTIMATE
    assert type(estimate.run_min_per_cell) is Decimal and type(estimate.grade_min_per_cell) is Decimal
    assert type(estimate.tokens_per_cell) is int


def test_build_has_the_contract_signature():
    signature = inspect.signature(_lean().build)
    assert [(p.name, p.annotation) for p in signature.parameters.values()] == [
        ("batches", "Sequence[BatchInput]"), ("prereg", "Prereg | None")]
    assert signature.return_annotation == "LeanSummary"


def test_build_is_l_sum_as_to_write():
    with pytest.raises(NotImplementedError, match="^L-SUM-A$"):
        _lean().build((), None)
