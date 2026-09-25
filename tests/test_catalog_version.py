"""The US-4 control: a score, weight, rubric or definition never changes under one catalog version (R-59 c1, c3;
design docs/design/phase3-graders.md, "Catalog-version rule" 4; CORE s2).

For a current `version` that does not end in `.dev`, the control fails when:
- (a) a committed fixture, graded offline under the current catalog, exports other bytes than its golden file
      `tests/fixtures/catalog/<version>/<fixture>.export` (a score or reason moved with no bump);
- (b) the current `catalog_hash` differs from the one pinned for the version in `bench/catalog-freeze.yaml` (a weight,
      rubric, definition or anchor edit, which the export cannot see), or none is pinned;
- (c) the golden files' sha256 differ from the digests pinned there (a same-commit rewrite of a golden file);
- (d) no golden file exists for the version (a freeze needs a golden export);
- (e) an entry present in `bench/catalog-freeze.yaml` at the merge base was changed or removed (append-only per version).
A `.dev` version is a probe and is exempt from (a)-(d) only here; the control prints `probe: exempt`. (e) always applies.

`bench/catalog-freeze.yaml` is Leader-owned (written at each freeze); this file only reads it.
The fixtures are the two committed X1 mini-runs (D6); the judge is not applicable to X1, so no model is called.
"""

import hashlib
import os
import shutil
import subprocess
import tomllib
import uuid
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import conftest
import pytest
import yaml
from archived_runs import ROOT, make_root, set_catalog_version

from harness_bench import config, views
from harness_bench.grade import Score, runner

FIXTURES = {name: Path(__file__).parent / "fixtures" / "ledger" / name / "run" for name in ("c44dd2b-no-heads", "heads")}
GOLDEN = Path(__file__).parent / "fixtures" / "catalog"
FREEZE = "bench/catalog-freeze.yaml"
PROBE = "probe: exempt"


def graded_export(root: Path, name: str, tmp: Path) -> bytes:
    """The export of fixture `name` after one pass under `root`'s catalog, read by that catalog's version."""
    run_dir = tmp / f"us4-{name}-{uuid.uuid4().hex}" / "run"
    shutil.copytree(FIXTURES[name], run_dir)
    runner.run_pass(run_dir, root)
    return views.export(views.load(run_dir, str(config.load_yaml(root / "bench" / "metrics.yaml")["version"])))


def us4_problems(root: Path, golden: Path, freeze: dict, base: dict, export: Callable[[str], bytes]) -> list[str]:
    """Checks (a)-(e) for `root`'s current catalog; [] when the control passes."""
    versions, was = freeze.get("versions") or {}, base.get("versions") or {}
    problems = [f"(e) {FREEZE} entry {v!r} was changed or removed since the merge base" for v in sorted(was) if versions.get(v) != was[v]]
    version = str(config.load_yaml(root / "bench" / "metrics.yaml")["version"])
    if version.endswith(".dev"):
        print(PROBE)
        return problems
    pinned = versions.get(version)
    current = runner.catalog_hash(root)
    if pinned is None:
        problems.append(f"(b) no catalog_hash pinned for {version} in {FREEZE}")
    elif pinned.get("catalog_hash") != current:
        problems.append(f"(b) catalog_hash {current} != {pinned.get('catalog_hash')} pinned for {version}: a weight, rubric or "
                        "definition changed without a version bump")
    files = sorted((golden / version).glob("*.export"))
    if not files:
        problems.append(f"(d) no golden export for {version} (a freeze needs a golden export)")
    digests = {f.stem: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if pinned is not None and digests != (pinned.get("golden") or {}):
        problems.append(f"(c) golden exports for {version} differ from the digests pinned in {FREEZE}")
    for f in files:
        if f.stem not in FIXTURES:
            problems.append(f"(a) {f.stem}: no committed fixture of that name")
        elif export(f.stem) != f.read_bytes():
            problems.append(f"(a) {f.stem}: the export differs from its golden file (a score or reason moved without a bump)")
    return sorted(problems)


def _git(*args: str) -> str | None:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60,
                          check=False)
    return done.stdout if done.returncode == 0 else None


def merge_base_freeze() -> dict:
    """bench/catalog-freeze.yaml at the merge base with HB_FREEZE_BASE (default main), read-only; HEAD when there is no
    such ref (a shallow CI checkout); {} when the file did not exist there."""
    ref = os.environ.get("HB_FREEZE_BASE", "main")
    base = (_git("merge-base", "HEAD", ref) or "HEAD").strip()
    text = _git("show", f"{base}:{FREEZE}")
    return (yaml.safe_load(text) or {}) if text else {}


# --- the control on this repository --------------------------------------------------------------------------------


def test_the_current_catalog_passes_the_us4_control(tmp_path, capsys):
    root = make_root(tmp_path, release=False)  # the real catalog byte for byte, and X1; bench/rubrics/ as well
    if (ROOT / "bench" / "rubrics").is_dir():
        shutil.copytree(ROOT / "bench" / "rubrics", root / "bench" / "rubrics")
    assert runner.catalog_hash(root) == runner.catalog_hash(ROOT)
    freeze = config.load_yaml(ROOT / FREEZE) if (ROOT / FREEZE).is_file() else {}
    assert us4_problems(root, GOLDEN, freeze, merge_base_freeze(), lambda name: graded_export(root, name, tmp_path)) == []
    version = str(config.load_yaml(ROOT / "bench" / "metrics.yaml")["version"])
    assert (PROBE in capsys.readouterr().out) == version.endswith(".dev")  # the exemption is visible, and only for a probe


# --- red first: each violation fails the control (TA 5, TA re-review 6) -------------------------------------------


@pytest.fixture
def frozen(tmp_path):
    """A root whose catalog is released as 9.1, with its golden exports and a freeze record pinning both: it passes."""
    root = make_root(tmp_path)
    set_catalog_version(root, "9.1")
    golden = tmp_path / "golden"
    (golden / "9.1").mkdir(parents=True)
    pins = {}
    for name in FIXTURES:
        data = graded_export(root, name, tmp_path / "freeze")
        (golden / "9.1" / f"{name}.export").write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
    freeze = {"schema": "bench-catalog-freeze/1", "versions": {"9.0": {"catalog_hash": "0" * 64, "golden": {}},
                                                                "9.1": {"catalog_hash": runner.catalog_hash(root), "golden": pins}}}
    return root, golden, freeze


def problems(frozen, tmp_path, base: dict | None = None, freeze: dict | None = None) -> list[str]:
    root, golden, pinned = frozen
    freeze = freeze or pinned
    return us4_problems(root, golden, freeze, pinned if base is None else base, lambda name: graded_export(root, name, tmp_path))


def test_a_frozen_catalog_with_unchanged_scores_passes(frozen, tmp_path):
    assert problems(frozen, tmp_path) == []


def test_a_grader_change_without_a_bump_is_red_through_a(frozen, tmp_path, monkeypatch):
    real = runner.GRADERS["correctness"]

    def changed(inp):  # a changed grader constant: cell a's partial credit moves
        out = dict(real(inp))
        if inp.cell["cell_id"] == "a":
            out["partial_credit"] = Score(Decimal("0.5000"), None)
        return out

    monkeypatch.setitem(runner.GRADERS, "correctness", changed)
    assert problems(frozen, tmp_path) == [f"(a) {name}: the export differs from its golden file (a score or reason moved without a bump)"
                                          for name in sorted(FIXTURES)]


def test_a_weight_changed_without_a_bump_is_red_through_b(frozen, tmp_path):
    root, _, freeze = frozen
    path = root / "bench" / "metrics.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("kind: score, weight: 1, scale: 6", "kind: score, weight: 2, scale: 6"),
                    encoding="utf-8")
    assert problems(frozen, tmp_path) == [  # the export does not carry weights, so only the hash sees it
        (f"(b) catalog_hash {runner.catalog_hash(root)} != {freeze['versions']['9.1']['catalog_hash']} pinned for 9.1: a weight, "
         "rubric or definition changed without a version bump")]


def test_a_rubric_added_without_a_bump_is_red_through_b(frozen, tmp_path):
    root, _, _ = frozen
    (root / "bench" / "rubrics").mkdir()
    (root / "bench" / "rubrics" / "adr_quality.md").write_text("# rubric\n", encoding="utf-8")
    assert [p[:4] for p in problems(frozen, tmp_path)] == ["(b) "]


def test_a_rewritten_golden_file_is_red_through_c(frozen, tmp_path):
    _, golden, _ = frozen
    path = golden / "9.1" / "heads.export"
    path.write_bytes(path.read_bytes() + b" ")
    assert problems(frozen, tmp_path) == [
        "(a) heads: the export differs from its golden file (a score or reason moved without a bump)",
        f"(c) golden exports for 9.1 differ from the digests pinned in {FREEZE}"]


def test_a_released_version_with_no_golden_export_is_red_through_d(frozen, tmp_path):
    _, golden, freeze = frozen
    shutil.rmtree(golden / "9.1")
    freeze["versions"]["9.1"]["golden"] = {}
    assert problems(frozen, tmp_path) == ["(d) no golden export for 9.1 (a freeze needs a golden export)"]


def test_a_released_version_with_no_freeze_entry_is_red_through_b(frozen, tmp_path):
    _, _, freeze = frozen
    del freeze["versions"]["9.1"]
    assert problems(frozen, tmp_path, base={}) == [f"(b) no catalog_hash pinned for 9.1 in {FREEZE}"]


def test_an_edited_or_removed_freeze_entry_is_red_through_e(frozen, tmp_path):
    _, _, base = frozen
    edited = {"versions": {**base["versions"], "9.0": {"catalog_hash": "1" * 64, "golden": {}}}}
    removed = {"versions": {"9.1": base["versions"]["9.1"]}}
    appended = {"versions": {**base["versions"], "9.2": {"catalog_hash": "2" * 64, "golden": {}}}}
    assert problems(frozen, tmp_path, base=base, freeze=edited) == [f"(e) {FREEZE} entry '9.0' was changed or removed since the merge base"]
    assert problems(frozen, tmp_path, base=base, freeze=removed) == [f"(e) {FREEZE} entry '9.0' was changed or removed since the merge base"]
    assert problems(frozen, tmp_path, base=base, freeze=appended) == []  # append-only: a new version is fine


def test_a_dev_version_is_exempt_and_says_so(frozen, tmp_path, capsys):
    root, _, _ = frozen
    set_catalog_version(root, "9.2.dev")
    path = root / "bench" / "metrics.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("kind: score, weight: 1, scale: 6", "kind: score, weight: 2, scale: 6"),
                    encoding="utf-8")  # no pin, no golden, a moved weight: all exempt for a probe
    assert problems(frozen, tmp_path) == []
    assert capsys.readouterr().out == f"{PROBE}\n"


# --- the slow ring: dotnet fixtures run only on the grading host (design: Catalog-version rule 4; seam V-4) ---------


def test_both_selectors_exclude_the_slow_ring():  # TA re-review 1: a command-line -m replaces addopts, so both change
    ini = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    assert ini["addopts"] == "-m 'not credentials and not slow'"
    assert any(m.startswith("slow:") for m in ini["markers"])
    ci = [line.strip() for line in (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").splitlines()]
    assert [line for line in ci if "pytest" in line] == ['- run: uv run pytest -q -m "not credentials and not slow"']


@pytest.mark.parametrize(("env", "which", "outcome"), [
    ({}, None, "skip: dotnet not required"),
    ({}, "C:/dotnet/dotnet.exe", "skip: dotnet not required"),
    ({"HB_REQUIRE_DOTNET": "1"}, None, "fail: HB_REQUIRE_DOTNET=1 but dotnet is not on PATH"),
    ({"HB_REQUIRE_DOTNET": "1"}, "C:/dotnet/dotnet.exe", "run"),
])
def test_hb_require_dotnet_fails_a_missing_dotnet_and_its_absence_skips(env, which, outcome):
    try:
        conftest.dotnet_gate(env, lambda name: which)
        got = "run"
    except pytest.skip.Exception as exc:
        got = f"skip: {exc.msg}"
    except pytest.fail.Exception as exc:
        got = f"fail: {exc.msg}"
    assert got == outcome
