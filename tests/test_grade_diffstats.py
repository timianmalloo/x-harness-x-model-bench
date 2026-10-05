"""Tests for grade/diffstats.py skeleton and registration (W1-L rev 2 section 8; X-LG)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from harness_bench import identity
from harness_bench.grade import Score, diffstats
from harness_bench.grade import property as property_grader
from harness_bench.grade.property import GradeContext


@pytest.mark.xfail(strict=True, reason="LGc: simplicity diffstats measure behavior")
def test_diffstats_measure_size():
    """W1-L section 15 K4: size == Decimal('3.5000') fails on -1 by assertion, never KeyError/ImportError."""
    stats = diffstats.measure(
        Path("base"),
        Path("final"),
        ["tinydb/table.py"],
    )
    assert stats["size_vs_reference"] == Decimal("3.5000")


def test_diffstats_strategy_registered():
    """W1-L section 3 K4: STRATEGIES['simplicity'] registered to diffstats.grade."""
    assert "simplicity" in property_grader.STRATEGIES
    assert property_grader.STRATEGIES["simplicity"] is diffstats.grade


def test_identity_planned_diffstats_retired():
    """W0 rev 6.10 R6.10a: grade/diffstats.py is classed and retired from PLANNED."""
    assert "grade/diffstats.py" not in identity.PLANNED
    assert identity.CLASSES["grade/diffstats.py"] == "grade"


def test_diffstats_grade_skeleton_returns_scores():
    """Skeleton grade() returns Score(None, 'not built') for metrics."""
    metrics = ["property_check_pass", "size_vs_reference", "new_abstractions", "new_dependencies"]

    import types

    inp = types.SimpleNamespace(metrics=metrics)
    res = diffstats.grade(inp, GradeContext(30.0))  # type: ignore[arg-type]
    assert set(res.keys()) == set(metrics)
    for score in res.values():
        assert isinstance(score, Score)
        assert score.value is None
        assert score.reason == "not built"


def test_sm_product_lines_ignore_blank_comment_docstring(tmp_path: Path):
    """W1-L s15: product lines ignore blanks, comment-only lines, and module/function docstrings."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "mod.py").write_text("def run():\n    return 42\n", encoding="utf-8")

    final = tmp_path / "final"
    final.mkdir()
    (final / "mod.py").write_text(
        '"""\n'
        'A six-line docstring\n'
        'that should be ignored\n'
        'by the product-lines counter\n'
        'so documentation\n'
        'does not inflate size.\n'
        '"""\n'
        '\n'
        '# A comment line that is also ignored\n'
        'def run():\n'
        '    """Inner function docstring."""\n'
        '    return 42\n',
        encoding="utf-8",
    )

    stats = diffstats.measure(base, final, ["mod.py"], size_reference_lines=2)
    assert stats["inside_lines"] == 0
    assert stats["size_vs_reference"] == Decimal("0.0000")
    assert stats["outside_radius_lines"] == 0
    assert stats["clause"] is None


def test_sm_each_metric_and_clause_has_a_flipping_variant(tmp_path: Path):
    """W1-L s15 + Errata 1 & 2: bloat, class, dep, launderlines, launderclass each flip exactly one clause."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "table.py").write_text(
        "class Table:\n"
        "    def search(self, cond):\n"
        "        return []\n",
        encoding="utf-8",
    )

    ceilings = {
        "size_vs_reference": "3.0000",
        "new_abstractions": 0,
        "new_dependencies": 0,
        "outside_radius_lines": 4,
    }
    radius = ["table.py"]

    # 1. v-bloat: adds a 5-line helper; size ratio 3.5000 > 3.0000 -> clause 'size'
    final_bloat = tmp_path / "bloat"
    final_bloat.mkdir()
    (final_bloat / "table.py").write_text(
        "class Table:\n"
        "    def search(self, cond):\n"
        "        return []\n"
        "    def first(self, cond):\n"
        "        return self._first_or_none(self.search(cond))\n"
        "    def _first_or_none(self, it):\n"
        "        for x in it:\n"
        "            return x\n"
        "        return None\n",
        encoding="utf-8",
    )
    s_bloat = diffstats.measure(base, final_bloat, radius, size_reference_lines=2, ceilings=ceilings)
    assert s_bloat["clause"] == "size"
    assert s_bloat["size_vs_reference"] == Decimal("3.5000")
    assert s_bloat["new_abstractions"] == 0
    assert s_bloat["new_dependencies"] == 0

    # 2. v-class: adds empty class; new_abstractions 1 > 0 -> clause 'abstractions'
    final_class = tmp_path / "class"
    final_class.mkdir()
    (final_class / "table.py").write_text(
        "class _Sentinel:\n"
        "    pass\n"
        "class Table:\n"
        "    def search(self, cond):\n"
        "        return []\n"
        "    def first(self, cond):\n"
        "        return next(iter(self.search(cond)), None)\n",
        encoding="utf-8",
    )
    s_class = diffstats.measure(base, final_class, radius, size_reference_lines=2, ceilings=ceilings)
    assert s_class["clause"] == "abstractions"
    assert s_class["new_abstractions"] == 1

    # 3. v-dep: adds external dependency; new_dependencies 1 > 0 -> clause 'dependencies'
    final_dep = tmp_path / "dep"
    final_dep.mkdir()
    (final_dep / "table.py").write_text(
        "import httpx\n"
        "class Table:\n"
        "    def search(self, cond):\n"
        "        return []\n"
        "    def first(self, cond):\n"
        "        return next(iter(self.search(cond)), None)\n",
        encoding="utf-8",
    )
    s_dep = diffstats.measure(base, final_dep, radius, package="tinydb", size_reference_lines=2, ceilings=ceilings)
    assert s_dep["clause"] == "dependencies"
    assert s_dep["new_dependencies"] == 1

    # 4. launderlines (drops clause b): in-radius 3 lines, outside 25 lines -> clause 'scope'
    final_launderlines = tmp_path / "launderlines"
    final_launderlines.mkdir()
    (final_launderlines / "table.py").write_text(
        "from ._first import find_first\n"
        "class Table:\n"
        "    def search(self, cond):\n"
        "        return []\n"
        "    def first(self, cond):\n"
        "        return find_first(self.search(cond))\n",
        encoding="utf-8",
    )
    funcs = "\n".join(f"def helper_{i}():\n    return {i}" for i in range(12))  # 24 lines + 1 = 25 lines
    (final_launderlines / "_first.py").write_text(f"def find_first(it):\n    return next(iter(it), None)\n{funcs}\n", encoding="utf-8")
    s_launderlines = diffstats.measure(base, final_launderlines, radius, size_reference_lines=2, ceilings=ceilings)
    assert s_launderlines["clause"] == "scope"
    assert s_launderlines["outside_radius_lines"] > 4
    assert s_launderlines["size_vs_reference"] <= Decimal("3.0000")
    assert s_launderlines["new_abstractions"] == 0

    # 5. launderclass (drops clause a): 2 outside lines holding two classes -> clause 'abstractions'
    final_launderclass = tmp_path / "launderclass"
    final_launderclass.mkdir()
    (final_launderclass / "table.py").write_text(
        "class Table:\n"
        "    def search(self, cond):\n"
        "        return []\n"
        "    def first(self, cond):\n"
        "        return next(iter(self.search(cond)), None)\n",
        encoding="utf-8",
    )
    (final_launderclass / "_first.py").write_text("class _M1:\n    pass\nclass _M2:\n    pass\n", encoding="utf-8")
    s_launderclass = diffstats.measure(base, final_launderclass, radius, size_reference_lines=2, ceilings=ceilings)
    assert s_launderclass["clause"] == "abstractions"
    assert s_launderclass["new_abstractions"] == 2
    assert s_launderclass["outside_radius_lines"] <= 4


def test_sm_ceiling_boundary_pairs(tmp_path: Path):
    """W1-L s15: exact boundary values pass, values exceeding ceiling fail."""
    ceilings = {
        "size_vs_reference": "3.0000",
        "new_abstractions": 0,
        "new_dependencies": 0,
        "outside_radius_lines": 4,
    }

    base = tmp_path / "base"
    base.mkdir()
    (base / "in.py").write_text("x = 1\n", encoding="utf-8")
    (base / "out.py").write_text("y = 1\n", encoding="utf-8")
    radius = ["in.py"]

    # 1. Size: 6 lines / 2 = 3.0000 passes (None); 7 lines / 2 = 3.5000 fails ('size')
    f_pass_size = tmp_path / "f_pass_size"
    f_pass_size.mkdir()
    (f_pass_size / "in.py").write_text("x = 1\na1=1\na2=2\na3=3\na4=4\na5=5\na6=6\n", encoding="utf-8")
    s1 = diffstats.measure(base, f_pass_size, radius, size_reference_lines=2, ceilings=ceilings)
    assert s1["size_vs_reference"] == Decimal("3.0000")
    assert s1["clause"] is None

    f_fail_size = tmp_path / "f_fail_size"
    f_fail_size.mkdir()
    (f_fail_size / "in.py").write_text("x = 1\na1=1\na2=2\na3=3\na4=4\na5=5\na6=6\na7=7\n", encoding="utf-8")
    s2 = diffstats.measure(base, f_fail_size, radius, size_reference_lines=2, ceilings=ceilings)
    assert s2["size_vs_reference"] == Decimal("3.5000")
    assert s2["clause"] == "size"

    # 2. Abstractions: 0 passes (None); 1 fails ('abstractions')
    f_fail_abs = tmp_path / "f_fail_abs"
    f_fail_abs.mkdir()
    (f_fail_abs / "in.py").write_text("x = 1\nclass A: pass\n", encoding="utf-8")
    s3 = diffstats.measure(base, f_fail_abs, radius, size_reference_lines=2, ceilings=ceilings)
    assert s3["new_abstractions"] == 1
    assert s3["clause"] == "abstractions"

    # 3. Outside lines: 4 passes (None); 5 fails ('scope')
    f_pass_out = tmp_path / "f_pass_out"
    f_pass_out.mkdir()
    (f_pass_out / "out.py").write_text("y = 1\nb1=1\nb2=2\nb3=3\nb4=4\n", encoding="utf-8")
    s4 = diffstats.measure(base, f_pass_out, radius, size_reference_lines=2, ceilings=ceilings)
    assert s4["outside_radius_lines"] == 4
    assert s4["clause"] is None

    f_fail_out = tmp_path / "f_fail_out"
    f_fail_out.mkdir()
    (f_fail_out / "out.py").write_text("y = 1\nb1=1\nb2=2\nb3=3\nb4=4\nb5=5\n", encoding="utf-8")
    s5 = diffstats.measure(base, f_fail_out, radius, size_reference_lines=2, ceilings=ceilings)
    assert s5["outside_radius_lines"] == 5
    assert s5["clause"] == "scope"


def test_sm_abstractions_counts_classdef_once(tmp_path: Path):
    """W1-L s15: ClassDef with base counts once; moved class is new."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "mod_a.py").write_text("class Existing: pass\n", encoding="utf-8")

    final = tmp_path / "final"
    final.mkdir()
    # class P(Protocol) has a base; should count as 1, not 2
    (final / "mod_a.py").write_text("class Existing: pass\nclass P(Protocol): pass\n", encoding="utf-8")
    # Existing class moved to mod_b.py is counted as new in mod_b.py
    (final / "mod_b.py").write_text("class Moved: pass\n", encoding="utf-8")

    stats = diffstats.measure(base, final, ["mod_a.py"], size_reference_lines=1)
    assert stats["new_abstractions"] == 2  # P(Protocol) + Moved


def test_sm_radius_partition_counts_each_line_once(tmp_path: Path):
    """W1-L s15: EV-6 in-radius feeds size_vs_reference only, outside feeds outside_radius_lines only."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "inside.py").write_text("a = 1\n", encoding="utf-8")
    (base / "outside.py").write_text("b = 1\n", encoding="utf-8")

    final = tmp_path / "final"
    final.mkdir()
    (final / "inside.py").write_text("a = 1\nx1=1\nx2=2\nx3=3\nx4=4\nx5=5\n", encoding="utf-8")  # +5 lines
    (final / "outside.py").write_text("b = 1\ny1=1\ny2=2\ny3=3\n", encoding="utf-8")             # +3 lines

    radius = ["inside.py"]
    stats = diffstats.measure(base, final, radius, size_reference_lines=1)
    assert stats["inside_lines"] == 5
    assert stats["outside_radius_lines"] == 3
    assert stats["inside_lines"] + stats["outside_radius_lines"] == 8
    assert stats["size_vs_reference"] == Decimal("5.0000")


def test_sm_frozen_reference_size_equals_function_output(tmp_path: Path):
    """W1-L s15: contract_failures checks size_reference_lines; unequal frozen value is HB-RDY-009."""
    # 1. Real tasks SM1 and SM2 reference overlay diffs match frozen size_reference_lines (2 and 3)
    sm1_dir = Path("tasks/SM1")
    sm2_dir = Path("tasks/SM2")
    assert (sm1_dir / "task.yaml").is_file()
    assert (sm2_dir / "task.yaml").is_file()

    # 2. Fixture task with hand-edited frozen value reports HB-RDY-009
    from harness_bench import readiness
    import shutil

    (tmp_path / "bench").mkdir(parents=True, exist_ok=True)
    shutil.copy("bench/metrics.yaml", tmp_path / "bench" / "metrics.yaml")

    task_dir = tmp_path / "tasks" / "SM_FIXTURE"
    ws = task_dir / "workspace" / "pkg"
    ws.mkdir(parents=True)
    (ws / "core.py").write_text("def run():\n    return 0\n", encoding="utf-8")

    ref = task_dir / "oracle" / "solutions" / "reference" / "pkg"
    ref.mkdir(parents=True)
    (ref / "core.py").write_text("def run():\n    return 0\ndef first():\n    return 1\n", encoding="utf-8")

    naive = task_dir / "oracle" / "solutions" / "naive" / "pkg"
    naive.mkdir(parents=True)
    (naive / "core.py").write_text("def run():\n    return 0\n", encoding="utf-8")

    variants_dir = task_dir / "oracle"
    (variants_dir / "variants.py").write_text("VARIANTS = {}\n", encoding="utf-8")

    (task_dir / "task.yaml").write_text(
        "schema: bench-task/1\n"
        "id: SM_FIXTURE\n"
        "scenario: 5\n"
        "language: python\n"
        "source: {kind: authored, repo: '', commit: '', license: MIT}\n"
        "graders: [correctness, property]\n"
        "blast_radius: ['pkg/core.py']\n"
        "property:\n"
        "  name: simplicity\n"
        "  latent_requirement: 'test requirement'\n"
        "  evidence_paths: ['pkg/core.py']\n"
        "  latent_terms: ['minimal']\n"
        "  primary_metric: property_check_pass\n"
        "  size_reference_lines: 99\n"  # Hand-edited wrong value (computed is 2)
        "  ceilings: {size_vs_reference: '3.0000', new_abstractions: 0, new_dependencies: 0, outside_radius_lines: 4}\n"
        "oracle: {runner: unittest, command: ['python', '-m', 'unittest']}\n"
        "expected:\n"
        "  reference: {property_check_pass: 1, size_vs_reference: '1.0000', new_abstractions: 0, new_dependencies: 0}\n"
        "  naive: {property_check_pass: 0, size_vs_reference: '1.0000', new_abstractions: 0, new_dependencies: 0}\n",
        encoding="utf-8",
    )

    failures = readiness.contract_failures(tmp_path, "SM_FIXTURE")
    rdy_009 = [f for f in failures if f.code == "HB-RDY-009"]
    assert len(rdy_009) == 1
    assert "99" in rdy_009[0].detail and "2" in rdy_009[0].detail


def make_sm_input(
    tmp_path: Path,
    *,
    metrics: tuple[str, ...] = ("property_check_pass", "size_vs_reference", "new_abstractions", "new_dependencies"),
    timeout: float = 30.0,
) -> property_grader.CellInput:
    run_dir = tmp_path / "run"
    (run_dir / "archive" / "c" / "attempt-1" / "ws").mkdir(parents=True, exist_ok=True)
    out_dir = run_dir / "grading" / "g" / "c" / "property"
    out_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "SM_FIXTURE",
        "blast_radius": ["tinydb/table.py"],
        "property": {
            "name": "simplicity",
            "latent_requirement": "test",
            "evidence_paths": ["tinydb/table.py"],
            "latent_terms": ["minimal"],
            "primary_metric": "property_check_pass",
            "size_reference_lines": 2,
            "ceilings": {"size_vs_reference": "3.0000", "new_abstractions": 0, "new_dependencies": 0, "outside_radius_lines": 4},
        },
        "oracle": {"runner": "unittest", "command": ["{python}", "-m", "unittest"]},
    }
    return property_grader.CellInput(
        run_dir=run_dir,
        root=tmp_path,
        plan={"parameters": {"grading_step_timeout": timeout}},
        cell={"cell_id": "c", "task": "SM_FIXTURE", "task_version": "tv_fixture"},
        task=task,
        task_dir=tmp_path / "tasks" / "SM_FIXTURE",
        archive=run_dir / "archive" / "c" / "attempt-1",
        out_dir=out_dir,
        events=(),
        record_reason=None,
        model_calls=(),
        tool_calls=(),
        turn_usage=(),
        metrics={m: {} for m in metrics},
        allow_model_calls=False,
        extraction=None,
        prices=None,
        work_root=tmp_path / "work",
    )


def test_diffstats_grade_cell_uses_registered_strategy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """W1-L s15: STRATEGIES line removed gives NA 'not built'."""
    inp = make_sm_input(tmp_path)

    # When registered: grade_cell calls STRATEGIES['simplicity'] -> diffstats.grade
    scores = property_grader.grade_cell(inp)
    assert "property_check_pass" in scores
    assert scores["property_check_pass"].reason is None

    # When removed: grade_cell returns NA 'not built'
    monkeypatch.delitem(property_grader.STRATEGIES, "simplicity")
    scores_removed = property_grader.grade_cell(inp)
    for s in scores_removed.values():
        assert s.value is None
        assert s.reason == "not built"

