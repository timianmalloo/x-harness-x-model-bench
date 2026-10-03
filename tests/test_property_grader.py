"""Property grader tests (design: docs/design/eval-property-grader.md, W1-F rev 3). F0: the skeleton exists."""

import importlib.util
import inspect
import re
from pathlib import Path


def test_property_module_exists_as_docstring_only_skeleton():
    spec = importlib.util.find_spec("harness_bench.grade.property")
    assert spec is not None, (
        "grade/property.py is missing (W0 section 7: X-G1 needs the module)"
    )
    module = importlib.import_module("harness_bench.grade.property")
    assert inspect.getdoc(module), "the skeleton carries a docstring"
    public = [n for n in vars(module) if not n.startswith("_")]
    assert public == [], f"F0 is a docstring only; found {public}"


# --- F1: G4, the one allowlist (W0 section 10 G4; ADR-0018 section 9) ---

SRC = Path(__file__).resolve().parents[1] / "src" / "harness_bench"
HOST_ENV_DEFINERS = {"grade/_env.py"}
ENVIRON_READERS = {"grade/_env.py"}
HOST_ENV_TOKEN = re.compile(r"\bHOST_ENV\s*=")


def scan(root: Path, rels, token) -> set[str]:
    return {r for r in rels if token.search((root / r).read_text(encoding="utf-8"))}


def test_host_env_defined_once():
    grade = SRC / "grade"
    rels = [p.relative_to(SRC).as_posix() for p in grade.rglob("*.py")]
    assert scan(SRC, rels, HOST_ENV_TOKEN) == HOST_ENV_DEFINERS
    readers = scan(
        SRC, ["grade/property.py", "grade/_env.py"], re.compile(r"os\.environ")
    )
    assert readers <= ENVIRON_READERS


def test_host_env_scan_catches_a_second_definition_and_ignores_dotnet_tuple(tmp_path):
    (tmp_path / "a.py").write_text('HOST_ENV = ("PATH",)\n')
    (tmp_path / "b.py").write_text('DOTNET_HOST_ENV = ("PATH",)\n')
    assert scan(tmp_path, ["a.py", "b.py"], HOST_ENV_TOKEN) == {"a.py"}
