"""D1 proof: W0 §9/§11, W1-D T-7, T-8, T-10/10b, T-12..12d, T-22.

G2 root: src/harness_bench/; recursion: yes; tokens: every file path except
under __pycache__/; allowlist: none (CLASSES is the classification table).
G2b root: run-class Python modules there; recursion: yes; tokens: every
resolved grade-class import; allowlist: RUN_IMPORTS_GRADE_ALLOWED; cli.py is
the composition root exemption. Both guards take fixture tables.
"""

import re
from pathlib import Path

import pytest
from import_graph import import_violations, stale_allowed

from harness_bench import errors, identity, plan
from harness_bench.grade import runner

ROOT = Path(__file__).resolve().parents[1]
EXEMPT = frozenset({"cli.py"})


def write_source(root, name, source=""):
    path = root / "src" / "harness_bench" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def w0_modules(text):
    section = text.split("## 9. Planned new modules", 1)[1].split("## 10.", 1)[0]
    return {name: kind for name, kind in re.findall(
        r"\| `src/harness_bench/([^`]+)`[^|]*\| (run|grade)\b", section)}


def test_every_e1_error_row_is_registered_with_w0_meaning():
    text = (ROOT / "docs/design/eval-seam-contracts.md").read_text(encoding="utf-8")
    rows = [(parts[1].strip(), parts[2].strip()) for line in text.splitlines()
            if line.startswith("| HB-") and "E1" in line
            for parts in [line.split("|")]]
    expected = {"HB-LED-007", "HB-IDN-001", "HB-IDN-002", "HB-PWR-001", "HB-GRD-007"}
    expected |= {f"HB-PLN-{n:03d}" for n in (1, 2, 4, 5)}
    expected |= {f"HB-CHK-{n:03d}" for n in range(1, 5)}
    expected |= {f"HB-RDY-{n:03d}" for n in range(1, 12)}
    expected |= {f"HB-CMP-{n:03d}" for n in range(1, 11)}

    assert {code for code, _ in rows} == expected
    assert {code: errors.RUN_CODES.get(code) for code, _ in rows} == dict(rows)
    for code in expected:
        assert errors.BenchError(code, "fixture").code == code


def test_unclassed_flags_each_new_file_kind(tmp_path):
    for name in ("new.py", "schemas/new.json", "assets/new.js", "__pycache__/ignored.pyc"):
        write_source(tmp_path, name)

    assert identity.unclassed(tmp_path, {}, frozenset({"future.py"})) == [
        "assets/new.js", "new.py", "schemas/new.json"]


def test_classed_files_and_missing_planned_files_are_silent(tmp_path):
    write_source(tmp_path, "known.json")

    assert identity.unclassed(tmp_path, {"known.json": "grade", "future.py": "run"},
                              frozenset({"future.py"})) == []


@pytest.mark.parametrize("landed", [False, True])
def test_stale_flags_ghost_and_landed_keys(tmp_path, landed):
    if landed:
        write_source(tmp_path, "future.py")
    classes = {"ghost.py": "run", "future.py": "grade"}

    assert identity.stale(tmp_path, classes, frozenset({"future.py"})) == (
        ["future.py", "ghost.py"] if landed else ["ghost.py"])


def test_every_src_file_has_a_class():
    assert len(identity.CLASSES) >= 69
    assert identity.unclassed(ROOT, identity.CLASSES, identity.PLANNED) == []
    assert identity.stale(ROOT, identity.CLASSES, identity.PLANNED) == []
    assert set(identity.CLASSES.values()) == {"run", "grade"}
    assert all(identity.CLASSES[name] == "run" for name in identity.CLASSES if name.startswith("telemetry/"))
    assert all(identity.CLASSES[name] == "grade" for name in identity.CLASSES if name.startswith("gateway/"))


def test_classes_match_w0_section_9():
    text = (ROOT / "docs/design/eval-seam-contracts.md").read_text(encoding="utf-8")
    expected = w0_modules(text)

    assert len(expected) == 18
    assert {name: identity.CLASSES.get(name) for name in expected} == expected
    assert identity.PLANNED == frozenset(name for name in expected
                                       if not (ROOT / "src/harness_bench" / name).is_file())
    wrong = text.replace("| `src/harness_bench/identity.py` | run |", "| `src/harness_bench/identity.py` | grade |", 1)
    assert {name: identity.CLASSES.get(name) for name in w0_modules(wrong)} != w0_modules(wrong)


@pytest.mark.parametrize("source", [
    "from harness_bench.grade.x import y\n",
    "def lazy():\n    from harness_bench.grade.x import y\n",
    "from ..grade.x import y\n",
    "import harness_bench.grade.x as g\n",
    "from harness_bench import grade\n",
    "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from harness_bench.grade.x import y\n",
])
def test_import_violations_red_fixtures(tmp_path, source):
    write_source(tmp_path, "telemetry/run.py", source)
    write_source(tmp_path, "grade/x.py")
    write_source(tmp_path, "grade/__init__.py")
    classes = {"telemetry/run.py": "run", "grade/x.py": "grade", "grade/__init__.py": "grade"}
    target = "grade/__init__.py" if source == "from harness_bench import grade\n" else "grade/x.py"

    assert import_violations(tmp_path, classes, {}, frozenset()) == [("telemetry/run.py", target)]


def test_allowed_pair_and_cli_are_silent(tmp_path):
    source = "from harness_bench.grade.x import y\n"
    for name in ("allowed.py", "other.py", "cli.py"):
        write_source(tmp_path, name, source)
    write_source(tmp_path, "grade/x.py")
    classes = {"allowed.py": "run", "other.py": "run", "cli.py": "run", "grade/x.py": "grade"}

    assert import_violations(tmp_path, classes, {("allowed.py", "grade/x.py"): "fixture"}, EXEMPT) == [
        ("other.py", "grade/x.py")]


def test_stale_allowed_pair_fails(tmp_path):
    write_source(tmp_path, "allowed.py")
    write_source(tmp_path, "grade/x.py")
    classes = {"allowed.py": "run", "grade/x.py": "grade"}
    allowed = {("allowed.py", "grade/x.py"): "fixture"}

    assert stale_allowed(tmp_path, classes, allowed) == [("allowed.py", "grade/x.py")]
    write_source(tmp_path, "allowed.py", "from harness_bench.grade.x import y\n")
    assert stale_allowed(tmp_path, classes, allowed) == []


def test_real_tree_edges_equal_the_allowlist():
    expected = {("config.py", "egress.py"), ("config.py", "gateway/backend.py"),
                ("config.py", "gateway/scrub.py")}

    assert set(identity.RUN_IMPORTS_GRADE_ALLOWED) == expected
    assert set(import_violations(ROOT, identity.CLASSES, {}, EXEMPT)) == expected
    assert import_violations(ROOT, identity.CLASSES, identity.RUN_IMPORTS_GRADE_ALLOWED, EXEMPT) == []
    assert stale_allowed(ROOT, identity.CLASSES, identity.RUN_IMPORTS_GRADE_ALLOWED) == []
    assert all("review 2027-10-03" in reason and "remove when" in reason
               for reason in identity.RUN_IMPORTS_GRADE_ALLOWED.values())


def test_catalog_component_equals_runner_catalog_hash(tmp_path):
    bench = tmp_path / "bench"
    (bench / "rubrics/nested").mkdir(parents=True)
    (bench / "metrics.yaml").write_bytes(b"metrics:\r\n  - id: score\r\n")
    (bench / "rubrics/nested/score.md").write_bytes(b"rubric\r\n")
    files = [bench / "metrics.yaml", bench / "rubrics/nested/score.md"]

    assert identity.catalog_hash(tmp_path) == plan.tree_hash(bench, files)
    assert runner.catalog_hash is identity.catalog_hash
    before = identity.catalog_hash(tmp_path)
    (bench / "rubrics/nested/score.md").write_bytes(b"changed\n")
    assert identity.catalog_hash(tmp_path) != before
    assert identity.catalog_hash(ROOT) == runner.catalog_hash(ROOT)


def test_catalog_without_rubrics_uses_the_original_recipe(tmp_path):
    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "metrics.yaml").write_bytes(b"metrics: []\n")

    assert identity.catalog_hash(tmp_path) == plan.tree_hash(bench, [bench / "metrics.yaml"])
