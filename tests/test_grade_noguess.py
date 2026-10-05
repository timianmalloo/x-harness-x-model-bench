"""Tests for grade/noguess.py skeleton and registration (W1-L rev 2 section 7; X-LG)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_bench import errors, identity
from harness_bench.grade import noguess
from harness_bench.grade import property as property_grader
from harness_bench.grade.property import GradeContext


def test_noguess_unresolved_count():
    """W1-L section 15 K3: count == 2 fails on -1 by assertion, never KeyError/ImportError."""
    count, unresolved_names = noguess.unresolved(
        Path("tasks/NG1/oracle/solutions/naive"),
        ["src/cachetools/limiter.py"],
        Path("tasks/NG1/workspace/vendor/quotakit"),
    )
    assert count == 2
    assert unresolved_names == ["quotakit.RateLimiter", "quotakit.RateLimitExceeded"]


def test_noguess_strategy_registered():
    """W1-L section 3 K3: STRATEGIES['no-guessing'] registered to noguess.grade."""
    assert "no-guessing" in property_grader.STRATEGIES
    assert property_grader.STRATEGIES["no-guessing"] is noguess.grade


def test_errors_hb_rdy_009_meaning():
    """W0 rev 6.10 section 11: HB-RDY-009 text has the built meaning."""
    assert errors.RUN_CODES["HB-RDY-009"] == (
        "a frozen task value differs from the canonical function's output (HASH-A)"
    )


def test_identity_planned_noguess_retired():
    """W0 rev 6.10 R6.10a: grade/noguess.py is classed and retired from PLANNED."""
    assert "grade/noguess.py" not in identity.PLANNED
    assert identity.CLASSES["grade/noguess.py"] == "grade"


def make_ng_input(
    tmp_path: Path,
    task_dir: Path,
    *,
    runner_kind: str = "unittest",
    metrics: tuple[str, ...] = ("property_check_pass", "hallucinated_symbol_errors", "verified_before_use"),
    timeout: int = 30,
) -> property_grader.CellInput:
    run_dir = tmp_path / "run"
    (run_dir / "archive" / "c" / "attempt-1" / "ws").mkdir(parents=True, exist_ok=True)
    out_dir = run_dir / "grading" / "g" / "c" / "property"
    out_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "id": "NG1",
        "blast_radius": ["src/cachetools/limiter.py", "src/cachetools/__init__.py"],
        "property": {
            "name": "no-guessing",
            "latent_requirement": "test",
            "evidence_paths": ["vendor/quotakit/README.md"],
            "latent_terms": ["read"],
            "primary_metric": "property_check_pass",
            "ceilings": {},
        },
        "oracle": {"runner": runner_kind, "command": ["{python}", "-m", "unittest"]},
    }
    return property_grader.CellInput(
        run_dir=run_dir,
        root=Path("."),
        plan={"parameters": {"grading_step_timeout": timeout}},
        cell={"cell_id": "c", "task": "NG1", "task_version": "tv"},
        task=task,
        task_dir=task_dir,
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


def test_noguess_resolver_counts_distinct_unresolved_names(tmp_path: Path):
    """W1-L s15: ast collection, typed receivers, documented self.attr, call keywords, agent code not imported."""
    vendor_dir = tmp_path / "vendor"
    lib_dir = vendor_dir / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "__init__.py").write_text(
        "class C:\n"
        "    def __init__(self):\n"
        "        self.attr = 42\n"
        "    def existing(self):\n"
        "        pass\n"
        "class Gate:\n"
        "    def __init__(self, max_calls, *, clock=None):\n"
        "        self.clock = clock\n"
        "    def admit(self, cost=1):\n"
        "        return True\n",
        encoding="utf-8",
    )

    tree = tmp_path / "ws"
    src = tree / "src"
    src.mkdir(parents=True)

    # 1. from lib import A, B -> gives 2 (lib.A, lib.B)
    (src / "from_import.py").write_text("from lib import A, B\n", encoding="utf-8")
    count, names = noguess.unresolved(tree, ["src/from_import.py"], vendor_dir)
    assert count == 2
    assert sorted(names) == ["lib.A", "lib.B"]

    # 2. getattr form -> gives 0
    (src / "dynamic.py").write_text("import lib\ngetattr(lib, 'nope')\n", encoding="utf-8")
    count, names = noguess.unresolved(tree, ["src/dynamic.py"], vendor_dir)
    assert count == 0
    assert names == []

    # 3. x = lib.C(); x.nope() -> gives 1 (lib.C.nope)
    (src / "typed_local.py").write_text("import lib\nx = lib.C()\nx.nope()\n", encoding="utf-8")
    count, names = noguess.unresolved(tree, ["src/typed_local.py"], vendor_dir)
    assert count == 1
    assert names == ["lib.C.nope"]

    # 4. self.g = lib.C(); self.g.nope -> gives 1 (lib.C.nope)
    (src / "typed_attr.py").write_text(
        "import lib\n"
        "class W:\n"
        "    def __init__(self):\n"
        "        self.g = lib.C()\n"
        "    def run(self):\n"
        "        self.g.nope\n",
        encoding="utf-8",
    )
    count, names = noguess.unresolved(tree, ["src/typed_attr.py"], vendor_dir)
    assert count == 1
    assert names == ["lib.C.nope"]

    # 5. annotated parameter s: lib.C; s.nope() -> gives 1 (lib.C.nope)
    (src / "annotated.py").write_text("import lib\ndef f(s: lib.C):\n    s.nope()\n", encoding="utf-8")
    count, names = noguess.unresolved(tree, ["src/annotated.py"], vendor_dir)
    assert count == 1
    assert names == ["lib.C.nope"]

    # 6. documented self.attr -> gives 0
    (src / "doc_attr.py").write_text("import lib\nx = lib.C()\ny = x.attr\n", encoding="utf-8")
    count, names = noguess.unresolved(tree, ["src/doc_attr.py"], vendor_dir)
    assert count == 0
    assert names == []

    # 7. call keywords: lib.Gate.__init__:period -> gives 1
    (src / "kw.py").write_text("import lib\ng = lib.Gate(5, period=10)\n", encoding="utf-8")
    count, names = noguess.unresolved(tree, ["src/kw.py"], vendor_dir)
    assert count == 1
    assert names == ["lib.Gate.__init__:period"]

    # 8. agent code never imported: module that writes marker file on import
    marker = tmp_path / "agent_marker.txt"
    (src / "side_effect.py").write_text(
        f"from pathlib import Path\nPath(r'{marker}').write_text('bad')\n",
        encoding="utf-8",
    )
    noguess.unresolved(tree, ["src/side_effect.py"], vendor_dir)
    assert not marker.exists(), "Agent code must never be imported"


def test_hse_resolver_failure_is_na(tmp_path: Path):
    """W1-L s15: resolver failure (import error, timeout, malformed) or syntax error gives NA, never 0."""
    import shutil

    # Syntax error in radius
    inp = make_ng_input(tmp_path, Path("tasks/NG1"))
    ws = inp.archive / "ws"
    shutil.copytree("tasks/NG1/workspace", ws, dirs_exist_ok=True)
    (ws / "src" / "cachetools").mkdir(parents=True, exist_ok=True)
    (ws / "src" / "cachetools" / "limiter.py").write_text("def def bad syntax error:\n", encoding="utf-8")

    res = noguess.grade(inp, GradeContext(30.0))
    hse = res["hallucinated_symbol_errors"]
    assert hse.value is None
    assert hse.reason == "syntax error: src/cachetools/limiter.py"

    with pytest.raises(noguess.ResolverError) as exc_info:
        noguess.unresolved(ws, ["src/cachetools/limiter.py"], Path("tasks/NG1/workspace/vendor/quotakit"))
    assert exc_info.value.reason == "syntax error: src/cachetools/limiter.py"

    # Resolver failure (broken vendor that cannot import)
    broken_vendor = tmp_path / "broken_vendor" / "quotakit"
    broken_vendor.mkdir(parents=True)
    (broken_vendor / "__init__.py").write_text("raise ImportError('cannot import library')\n", encoding="utf-8")

    (ws / "src" / "cachetools" / "limiter.py").write_text("from quotakit import Gate\n", encoding="utf-8")
    with pytest.raises(noguess.ResolverError) as exc_info2:
        noguess.unresolved(ws, ["src/cachetools/limiter.py"], tmp_path / "broken_vendor")
    assert exc_info2.value.reason.startswith("resolver failed: ")


def test_noguess_uses_pristine_vendor(tmp_path: Path):
    """W1-L s15: v-vendor-edit count stays 1 against pristine vendor; mutant resolving agent copy reads 0."""
    import shutil

    inp = make_ng_input(tmp_path, Path("tasks/NG1"))
    ws = inp.archive / "ws"
    shutil.copytree("tasks/NG1/workspace", ws, dirs_exist_ok=True)

    # Agent edits vendor/quotakit in their own working tree
    agent_vendor_gate = ws / "vendor" / "quotakit" / "quotakit" / "gate.py"
    agent_vendor_gate.write_text(
        agent_vendor_gate.read_text(encoding="utf-8") + "\n    def try_acquire(self):\n        return True\n",
        encoding="utf-8",
    )

    # Solution references the added method
    (ws / "src" / "cachetools").mkdir(parents=True, exist_ok=True)
    (ws / "src" / "cachetools" / "limiter.py").write_text(
        "from quotakit import Gate\n"
        "g = Gate(1, 1)\n"
        "g.try_acquire()\n",
        encoding="utf-8",
    )

    res = noguess.grade(inp, GradeContext(30.0))
    hse = res["hallucinated_symbol_errors"]
    assert hse.value == 1
    assert hse.reason is None


def test_noguess_compiled_runner_is_na_not_built(tmp_path: Path):
    """W1-L s15: task with a compiled runner scores NA 'not built for <runner>'."""
    inp = make_ng_input(tmp_path, Path("tasks/NG1"), runner_kind="dotnet")
    res = noguess.grade(inp, GradeContext(30.0))
    assert res["hallucinated_symbol_errors"].value is None
    assert res["hallucinated_symbol_errors"].reason == "not built for dotnet"
    assert res["property_check_pass"].value is None
    assert res["property_check_pass"].reason == "not built for dotnet"


def test_ng_verified_before_use_is_na_not_built(tmp_path: Path):
    """W1-L s15: verified_before_use is NA 'not built' for every cell."""
    inp = make_ng_input(tmp_path, Path("tasks/NG1"))
    res = noguess.grade(inp, GradeContext(30.0))
    assert res["verified_before_use"].value is None
    assert res["verified_before_use"].reason == "not built"


def test_noguess_grade_cell_uses_registered_strategy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """W1-L s15: STRATEGIES line removed gives NA 'not built'."""
    import shutil

    inp = make_ng_input(tmp_path, Path("tasks/NG1"))
    ws = inp.archive / "ws"
    shutil.copytree("tasks/NG1/workspace", ws, dirs_exist_ok=True)
    shutil.copytree("tasks/NG1/oracle/solutions/naive", ws, dirs_exist_ok=True)

    # When registered: grade_cell calls STRATEGIES['no-guessing'] -> noguess.grade
    scores = property_grader.grade_cell(inp)
    assert scores["hallucinated_symbol_errors"].value == 2
    assert scores["hallucinated_symbol_errors"].reason is None

    # When removed: grade_cell returns NA 'not built'
    monkeypatch.delitem(property_grader.STRATEGIES, "no-guessing")
    scores_removed = property_grader.grade_cell(inp)
    for s in scores_removed.values():
        assert s.value is None
        assert s.reason == "not built"


