"""Structural rules (design test plan D0 and D3), checked on the source, not by review.

- D3: engine, driver and archive never import grade or report; only procs.py calls subprocess; only
  gitsafe.py runs git; only driver.py speaks ACP.
- D0: no path of the retired coordinator runner (`coord-run/1`) remains in the benchmark's code, its
  skills (and their synced copies) or its README (owner ruling: the benchmark never runs in the
  coordinator's runner).
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "harness_bench"
MODULES = sorted(SRC.rglob("*.py"))
SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}
OS_SPAWNS = {"system", "popen", "startfile", "execv", "execve", "spawnv", "spawnve"}
ACP_METHODS = {"initialize", "session/new", "session/prompt", "session/set_mode", "session/cancel", "session/request_permission"}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(tree: ast.Module) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names |= {f"{node.module}.{a.name}" for a in node.names}
    return names


@pytest.mark.parametrize("name", ["engine", "driver", "archive"])
def test_the_run_path_never_imports_grading_or_reports(name):
    imported = _imports(_tree(SRC / f"{name}.py"))
    assert not {i for i in imported if i.startswith(("harness_bench.grade", "harness_bench.report"))}


def test_only_procs_calls_subprocess_or_spawns():
    offenders = []
    for path in MODULES:
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                owner, attr = node.func.value.id, node.func.attr
                if ((owner == "subprocess" and attr in SUBPROCESS_CALLS) or (owner == "os" and attr in OS_SPAWNS)) and path != SRC / "procs.py":
                    offenders.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}")
    assert offenders == []


def _string_constants(path: Path) -> set[str]:
    return {n.value for n in ast.walk(_tree(path)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def test_only_gitsafe_runs_git():
    assert [p.name for p in MODULES if {"git", "git.exe"} & _string_constants(p)] == ["gitsafe.py"]


def test_only_driver_speaks_acp():
    assert [p.name for p in MODULES if ACP_METHODS - {"initialize"} & _string_constants(p) or
            ("initialize" in _string_constants(p) and "session/new" in _string_constants(p))] == ["driver.py"]


def test_only_the_gateway_reaches_a_judge_backend_and_only_beside_egress():
    """US-47 / ADR-0005 / R-60: `egress.check` is the only path to a judge backend.

    The spawner is `harness_bench.gateway.backend` (assume: W3-GW-I names its CLI spawner module so; confirm
    at its join; if it is named otherwise, SPAWNER changes in the same commit, since a lint on a name nothing
    uses passes vacuously). A module outside `gateway/` never imports it, and a gateway module that imports it
    also imports `harness_bench.egress`. Relative imports are resolved. Today no gateway package exists, so
    the scan finds no importer; the self-check below proves the rule fires on the shapes it must catch.
    """
    spawner, gateway = "harness_bench.gateway.backend", ("harness_bench", "gateway")

    def offends(rel: str, source: str) -> bool:
        package = tuple(Path(rel).with_suffix("").parts[1:-1])  # rel is "src/harness_bench/.../x.py"
        names = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                names |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                base = list(package[:len(package) - node.level + 1]) if node.level else []
                module = ".".join(base + ([node.module] if node.module else []))
                names |= {module} | {f"{module}.{a.name}" for a in node.names}
        if not any(n == spawner or n.startswith(spawner + ".") for n in names):
            return False
        return package[:2] != gateway or "harness_bench.egress" not in names

    assert offends("src/harness_bench/grade/judge.py", "from harness_bench.gateway.backend import spawn")
    assert offends("src/harness_bench/gateway/judge.py", "from .backend import spawn")
    assert not offends("src/harness_bench/gateway/judge.py", "from . import backend\nfrom harness_bench import egress")
    assert not offends("src/harness_bench/grade/judge.py", "from harness_bench.gateway import judge")
    assert [p.relative_to(ROOT).as_posix() for p in MODULES
            if offends(p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8"))] == []


D0_PATHS = [ROOT / "README.md", ROOT / "bench", SRC,
            *(ROOT / folder / "skills" / skill for folder in ("", ".claude", ".agents") for skill in ("start-benchmark", "new-bench-task"))]


def test_no_coordinator_runner_path_remains():
    found = []
    for base in D0_PATHS:
        for f in ([base] if base.is_file() else sorted(base.rglob("*")) if base.exists() else []):
            if f.is_file() and f.suffix in (".py", ".md", ".yaml", ".json"):
                text = f.read_text(encoding="utf-8", errors="replace")
                for word in ("coord-run", "coord_contract", "coord-runner", "MAX_WORKERS_PER_CONTRACT"):
                    if word in text:
                        found.append(f"{f.relative_to(ROOT)}: {word}")
    assert found == []
