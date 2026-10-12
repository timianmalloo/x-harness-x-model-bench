"""GOLD-A (docs/lessons/defect-classes.md): the default fixture root is frozen and self-contained.

`archived_runs.make_root` used to copy the repository's live `bench/` and `tasks/X1`, so a profile or pin edit
moved the plan hash inside `tests/goldens/report-nonlean-arms.html` with `report/html.py` unchanged. The default
root now copies `tests/fixtures/bench-root/` (catalog 0.7, the three profiles, the tools pin, X1). Only the named
consumers of the real catalog's identity (`archived_runs.LIVE_CONSUMERS`) ask for the live tree, with
`release=False`. Each test below edits a scratch copy of the live inputs and points `archived_runs.ROOT` at it.
"""

import ast
import shutil
from pathlib import Path

import archived_runs
import pytest
import yaml
from archived_runs import FROZEN_ROOT, LIVE_CONSUMERS, ROOT, make_root

# The inputs a fixture root carries, relative to the bench root (the R-GOLD contract).
INPUTS = ("bench/metrics.yaml", "bench/profiles", "bench/tools/package.json", "bench/tools/package-lock.json",
          "tasks/X1")


def _files(base: Path) -> dict[str, bytes]:
    out = {}
    for rel in INPUTS:
        path = base / rel
        for f in sorted(path.rglob("*")) if path.is_dir() else [path]:
            if f.is_file():
                out[f.relative_to(base).as_posix()] = f.read_bytes()
    return out


@pytest.fixture
def edited_live(tmp_path, monkeypatch) -> Path:
    """A scratch copy of the live inputs with one byte appended to every file, set as `archived_runs.ROOT`."""
    live = tmp_path / "live"
    for rel in INPUTS:
        src, dst = ROOT / rel, live / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy)(src, dst)
    for f in live.rglob("*"):
        if f.is_file():
            f.write_bytes(f.read_bytes() + (b"\n" if f.suffix in (".yaml", ".py", ".md") else b" "))
    monkeypatch.setattr(archived_runs, "ROOT", live)
    return live


def test_the_frozen_root_holds_exactly_the_contracted_inputs():
    listed = {f.relative_to(FROZEN_ROOT).as_posix() for f in FROZEN_ROOT.rglob("*") if f.is_file()}
    assert listed - {"conftest.py"} == set(_files(FROZEN_ROOT))
    assert {p.name for p in (FROZEN_ROOT / "bench" / "profiles").iterdir()} == {"claude-code.yaml", "codex.yaml",
                                                                                "copilot.yaml"}


def test_the_frozen_catalog_is_the_0_7_release_so_a_default_pass_is_current():
    # R-59 DR-4: a probe (.dev) pass is never current in a default view; the frozen catalog needs no relabel.
    catalog = yaml.safe_load((FROZEN_ROOT / "bench" / "metrics.yaml").read_text(encoding="utf-8"))
    assert str(catalog["version"]) == "0.7"


def test_the_default_root_reads_nothing_from_the_repository(tmp_path, edited_live):
    root = make_root(tmp_path)
    got = _files(root)
    assert got == _files(FROZEN_ROOT)
    assert all(got[k] != v for k, v in _files(edited_live).items())


def test_an_edited_live_profile_leaves_the_nonlean_report_golden_byte_equal(tmp_path, edited_live):
    from test_lean_section import test_nonlean_report_golden

    test_nonlean_report_golden(tmp_path)


def test_release_false_is_the_live_mode_byte_for_byte(tmp_path, edited_live):
    assert _files(make_root(tmp_path, release=False)) == _files(edited_live)


def _live_calls(path: Path) -> dict[str, int]:
    """Per function in `path`: its `make_root(..., release=False)` calls."""
    out: dict[str, int] = {}
    for fn in (n for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, ast.FunctionDef)):
        calls = sum(1 for n in ast.walk(fn)
                    if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "make_root"
                    and any(k.arg == "release" and isinstance(k.value, ast.Constant) and k.value.value is False
                            for k in n.keywords))
        if calls:
            out[fn.name] = out.get(fn.name, 0) + calls
    return out


@pytest.mark.parametrize(("module", "function"), LIVE_CONSUMERS)
def test_each_live_consumer_still_reads_the_live_catalog(module, function):
    assert _live_calls(Path(__file__).parent / f"{module}.py").get(function) == 1


def test_no_other_caller_asks_for_the_live_tree():
    here = Path(__file__).parent
    callers = {(path.stem, fn) for path in sorted([*here.glob("*.py"), *here.glob("e2e/*.py")])
               if path.name != Path(__file__).name for fn in _live_calls(path)}
    assert callers == set(LIVE_CONSUMERS)
