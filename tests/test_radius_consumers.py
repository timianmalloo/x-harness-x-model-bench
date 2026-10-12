"""RADIUS-TEST-A's control (ADR-0026 s6): one radius definition, and every consumer accounts for test paths.

A radius consumer is a module under `src/harness_bench` that reads the `blast_radius` key (a `"blast_radius"` string
literal; a docstring that mentions it is not one). Each must match paths through `_changes.in_radius` (never its own
`fnmatch`), and either call `_changes.is_test_path` or be named exempt here with its reason. A consumer that hands
the radius to another consumer is named as a delegate, and the module it hands it to must pass the same rule.
"""

import ast

from archived_runs import ROOT

SRC = ROOT / "src" / "harness_bench"
DELEGATES = {"readiness.py": ("diffstats", "measure")}  # readiness.size_reference_lines: diffstats.measure(base, final, radius)
PRESENCE_ONLY = {"grade/runner.py": "applicable(has_radius=...) asks whether the task has a radius, never matches a path"}
EXEMPT_TEST_PATH = {  # module -> why it may match the radius without `is_test_path`
    "report/pack_improvement.py": "classify() decides test_write by its own TEST_PATH before product_write, so a test "
                                  "path is never a product write; diverted_delivery compares bytes, not scope",
}


def _tree(rel: str) -> ast.Module:
    return ast.parse((SRC / rel).read_text(encoding="utf-8"))


def _consumers() -> list[str]:
    out = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(n, ast.Constant) and n.value == "blast_radius" for n in ast.walk(tree)):
            out.append(path.relative_to(SRC).as_posix())
    return out


def _calls(tree: ast.Module, owner: str, name: str) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == name
               and isinstance(n.func.value, ast.Name) and n.func.value.id == owner for n in ast.walk(tree))


def _imports_fnmatch(tree: ast.Module) -> bool:
    return any((isinstance(n, ast.Import) and any(a.name == "fnmatch" for a in n.names))
               or (isinstance(n, ast.ImportFrom) and n.module == "fnmatch") for n in ast.walk(tree))


def test_the_sweep_finds_every_radius_consumer_the_register_names():
    assert set(_consumers()) == {"grade/diffstats.py", "grade/drift.py", "grade/noguess.py", "grade/rework.py",
                                 "grade/runner.py", "readiness.py", "report/pack_improvement.py"}


def test_every_radius_consumer_calls_in_radius_and_is_test_path_or_is_named_exempt():
    problems = []
    for rel in _consumers():
        tree = _tree(rel)
        if rel in PRESENCE_ONLY:
            if _imports_fnmatch(tree) or _calls(tree, "_changes", "in_radius"):
                problems.append(f"{rel}: named presence-only but matches paths")
            continue
        if rel in DELEGATES:
            module, fn = DELEGATES[rel]
            if not _calls(tree, module, fn):
                problems.append(f"{rel}: named a delegate of {module}.{fn} but never calls it")
            continue
        if not _calls(tree, "_changes", "in_radius"):
            problems.append(f"{rel}: matches the radius without _changes.in_radius")
        if _imports_fnmatch(tree):
            problems.append(f"{rel}: imports fnmatch (a second radius definition)")
        if not _calls(tree, "_changes", "is_test_path") and rel not in EXEMPT_TEST_PATH:
            problems.append(f"{rel}: never calls _changes.is_test_path and is not named exempt")
    assert problems == []


def test_each_delegate_hands_the_radius_to_a_consumer_that_passes_the_rule():
    for rel, (module, _fn) in DELEGATES.items():
        target = f"grade/{module}.py"
        assert target in _consumers(), rel
        tree = _tree(target)
        assert _calls(tree, "_changes", "in_radius") and _calls(tree, "_changes", "is_test_path"), target


def test_one_radius_definition_case_sensitive_on_every_host():
    from harness_bench.grade import _changes
    from harness_bench.report import pack_improvement

    assert _changes.in_radius("SRC/x.py", ["src/*"]) is False  # fnmatchcase: no host case folding
    write = pack_improvement.ToolInput(1, "Write", ("SRC/x.py",), None, True)
    assert "product_write" not in pack_improvement.classify(write, ["src/*"])  # the same answer through the report
    assert "product_write" in pack_improvement.classify(write, ["SRC/*"])
