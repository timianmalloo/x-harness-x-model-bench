"""Architecture grader: architecture_conformance (design phase3-graders, section Architecture, GR-CODE c4).

- The C1 and D1 fixtures are the frozen `tasks/<id>/workspace` in a temporary git repo that reproduces the archive's
  commits (`d1_cell` from the correctness tests; `c1_cell` below builds C1 the same way). They need git only.
- A value is asserted as `str(Decimal)`, so the scale of 4 is part of the expectation (rules passed / rules, scale 4).
- Every grade asserts the archive's bytes did not move (F9).
"""

import dataclasses
import os
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import ROOT
from test_grade_correctness import d1_cell, git, tree_digest

from harness_bench import config, plan, procs, views
from harness_bench.archive import make_writable
from harness_bench.grade import CellInput, architecture, runner
from harness_bench.grade.runner import applicable

CATALOG = config.load_yaml(ROOT / "bench" / "metrics.yaml")
METRIC = "architecture_conformance"
C1 = ROOT / "tasks" / "C1"
C1_VERSION = plan.task_version_hash(C1)
C1_REFERENCE = {rel: (C1 / "oracle" / "reference" / rel).read_text(encoding="utf-8")
                for rel in ("priority_queue.py", "docs/architecture.md")}
PROJECTION = "src/AiDe.Core/Projections/EvidenceCensusProjection.cs"
D1_REFERENCE = {PROJECTION: (ROOT / "tasks" / "D1" / "oracle" / "reference" / PROJECTION).read_text(encoding="utf-8")}


def encode(score) -> tuple:
    """(value, reason); a Decimal as its own string, so `1.0000` and `1` differ (scale 4)."""
    v = score.value
    return (str(v) if isinstance(v, Decimal) else v), score.reason


def c1_cell(tmp_path: Path, overlay: dict) -> tuple[Path, dict]:
    """(archive folder, plan cell): C1's base commit, then `overlay` (path -> text), uncommitted; pack off."""
    folder = tmp_path / "run" / "archive" / "c1" / "attempt-1"
    ws = folder / "ws"
    shutil.copytree(C1 / "workspace", ws)
    git(ws, "init", "-q", "-b", "main")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", f"C1 base ({C1_VERSION[:12]})")
    for rel, text in overlay.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text, encoding="utf-8", newline="")
    return folder, {"cell_id": "c1", "task": "C1", "task_version": C1_VERSION, "pack": "off"}


def arch_input(run_dir: Path, archive: Path, cell: dict, out_dir: Path, timeout: int = 900) -> CellInput:
    task_dir = ROOT / "tasks" / cell["task"]
    out_dir.mkdir(parents=True, exist_ok=True)
    return CellInput(run_dir=run_dir, root=ROOT, plan={"parameters": {"grading_step_timeout": timeout}}, cell=cell,
                     task=config.load_yaml(task_dir / "task.yaml"), task_dir=task_dir, archive=archive, out_dir=out_dir,
                     events=(), record_reason=None, model_calls=(), tool_calls=(), turn_usage=(),
                     metrics=applicable(CATALOG, ["architecture"])["architecture"], allow_model_calls=False,
                     extraction=None, prices=None)


def grade(tmp_path: Path, folder: Path, cell: dict) -> tuple:
    """architecture_conformance as (value, reason); the archive's bytes must not move (F9)."""
    before = tree_digest(folder)
    out = architecture.grade_cell(arch_input(tmp_path / "run", folder, cell,
                                             tmp_path / "run" / "grading" / "g" / "c1" / "architecture"))
    assert tree_digest(folder) == before, "grading wrote under the archive"
    return encode(out[METRIC])


# --- the design's exact fixtures ------------------------------------------------------------------------------------


def test_the_c1_reference_with_no_imports_is_1(tmp_path):  # design: Architecture, Fixtures
    assert grade(tmp_path, *c1_cell(tmp_path, C1_REFERENCE)) == ("1.0000", None)


def test_the_c1_reference_plus_import_numpy_is_0(tmp_path):  # design: Architecture, Fixtures
    overlay = {**C1_REFERENCE, "priority_queue.py": "import numpy\n" + C1_REFERENCE["priority_queue.py"]}
    assert grade(tmp_path, *c1_cell(tmp_path, overlay)) == ("0.0000", None)


def test_the_d1_reference_plus_using_newtonsoft_json_is_0(tmp_path):  # design: Architecture, Fixtures
    overlay = {PROJECTION: "using Newtonsoft.Json;\n" + D1_REFERENCE[PROJECTION]}
    assert grade(tmp_path, *d1_cell(tmp_path, overlay)) == ("0.0000", None)


# --- D1: the using directives of a Projections file ------------------------------------------------------------------


def test_the_d1_reference_is_1(tmp_path):  # its only using is AiDe.Core.Facts
    assert grade(tmp_path, *d1_cell(tmp_path, D1_REFERENCE)) == ("1.0000", None)


def projection(tmp_path: Path, head: str) -> tuple:
    """The D1 reference with `head` before it, as the cell's added Projections file."""
    return grade(tmp_path, *d1_cell(tmp_path, {PROJECTION: head + D1_REFERENCE[PROJECTION]}))


def test_every_platform_and_own_layer_form_conforms_and_using_statements_are_not_directives(tmp_path):
    head = ("using System;\nusing System.Linq;\nusing AiDe.Core;\nusing static System.Math;\nglobal using AiDe.Core.Facts;\n"
            "using J = System.Text.Json;\nusing global::System.IO;\nusing L = System.Collections.Generic.List<int>;\n"
            "// using Newtonsoft.Json;\n/* using Newtonsoft.Json;\n   using Serilog; */\n"
            "static class U { static void M() { using var s = new Newtonsoft.Json.JsonTextReader(null); "
            "using (var t = Serilog.Log.Logger) { } } }\n")
    assert projection(tmp_path, head) == ("1.0000", None)


@pytest.mark.parametrize("head", [
    "using AiDe.CoreX;\n",  # a name that only starts with the layer's name
    "using Systemic;\n",
    "using static Newtonsoft.Json.JsonConvert;\n",
    "using J = Newtonsoft.Json;\n",
    "using N = Newtonsoft.Json.Linq.JEnumerable<int>;\n",
    "global using Newtonsoft.Json;\n",
    "using global::Newtonsoft.Json;\n",
    "using System; using Newtonsoft.Json;\n",  # the second directive on a line
    "namespace A {using Newtonsoft.Json;}\n",  # a directive inside a namespace block
    "﻿using Newtonsoft.Json;\n",  # the first line after a UTF-8 BOM
])
def test_a_using_outside_system_and_aide_core_breaks_the_rule(tmp_path, head):
    assert projection(tmp_path, head) == ("0.0000", None)


def test_a_projections_file_that_is_not_utf8_is_read_not_raised(tmp_path):  # cp1252 bytes in a comment
    folder, cell = d1_cell(tmp_path, {})
    (folder / "ws" / PROJECTION).write_bytes(b"// caf\xe9\nusing Newtonsoft.Json;\n")
    assert grade(tmp_path, folder, cell) == ("0.0000", None)


def test_a_changed_projections_file_is_read_whole(tmp_path):  # an edit to a pre-turn file, not only an added one
    folder, cell = d1_cell(tmp_path, {"src/AiDe.Core/Projections/GraphPaths.cs": lambda text: "using Serilog;\n" + text})
    assert grade(tmp_path, folder, cell) == ("0.0000", None)


@pytest.mark.parametrize("overlay", [
    {},  # the gate's 35af: nothing in ws/ changed
    {"src/AiDe.Mcp/Extra.cs": "using Newtonsoft.Json;\n"},  # outside the Projections folder
    {"src/AiDe.Core/ProjectionsExtra/A.cs": "using Newtonsoft.Json;\n"},  # a sibling folder, not the Projections folder
    {"src/AiDe.Core/Projections/notes.md": "using Newtonsoft.Json;\n"},  # not a .cs file
])
def test_no_file_in_the_rule_scope_is_na_no_source_file_changed(tmp_path, overlay):
    assert grade(tmp_path, *d1_cell(tmp_path, overlay)) == (None, "no source file changed")


def test_a_deleted_projections_file_is_not_read(tmp_path):
    folder, cell = d1_cell(tmp_path, {})
    (folder / "ws" / "src" / "AiDe.Core" / "Projections" / "GraphPaths.cs").unlink()
    assert grade(tmp_path, folder, cell) == (None, "no source file changed")


def test_the_pack_commit_is_not_a_change(tmp_path):  # a pack-on cell's base is the pack commit (_changes)
    folder, cell = d1_cell(tmp_path, {}, pack=True)
    ws = folder / "ws"
    (ws / "src" / "AiDe.Core" / "Projections" / "Pack.cs").write_text("using Newtonsoft.Json;\n", encoding="utf-8")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "--amend", "-m", "ai-forward pack revision 95")
    (ws / PROJECTION).write_text(D1_REFERENCE[PROJECTION], encoding="utf-8", newline="")
    assert grade(tmp_path, folder, cell) == ("1.0000", None)


# --- C1: the imports of every .py the cell added or changed -----------------------------------------------------------


def c1(tmp_path: Path, overlay: dict) -> tuple:
    return grade(tmp_path, *c1_cell(tmp_path, {**C1_REFERENCE, **overlay}))


def with_head(head: str) -> dict:
    return {"priority_queue.py": head + C1_REFERENCE["priority_queue.py"]}


@pytest.mark.parametrize("head", [
    "from __future__ import annotations\nimport os, json\nfrom collections import deque\nimport importlib.util\n",
    "from . import helpers\nfrom .helpers import x\n",  # a relative import is the working copy's
    "import helpers\nfrom helpers import x\n",  # a module at the root of the working copy
])
def test_stdlib_and_working_copy_imports_conform(tmp_path, head):
    assert c1(tmp_path, {**with_head(head), "helpers.py": "x = 1\n"}) == ("1.0000", None)


@pytest.mark.parametrize("head", [
    "from numpy import array\n",
    "import numpy.linalg\n",
    "import os, numpy\n",
    "def f():\n    import numpy\n",  # an import inside a function
    "import helpers\n",  # the module is not in the working copy
    "def (:\n",  # a file that does not parse shows no imports
])
def test_an_import_outside_stdlib_and_the_working_copy_breaks_the_rule(tmp_path, head):
    assert c1(tmp_path, with_head(head)) == ("0.0000", None)


def test_a_test_file_may_import_the_root_module_and_its_own_neighbour_but_not_pytest(tmp_path):
    folder = {"tests/test_pq.py": "import priority_queue\nimport fakes\n", "tests/fakes.py": "\n"}
    assert c1(tmp_path, folder) == ("1.0000", None)
    shutil.rmtree(tmp_path / "run", onexc=make_writable)
    assert c1(tmp_path, {**folder, "tests/test_pq.py": "import pytest\nimport priority_queue\n"}) == ("0.0000", None)


def test_a_module_deeper_in_the_tree_is_not_the_working_copys_for_an_import(tmp_path):  # the assume: in _py_breaks
    assert c1(tmp_path, {**with_head("import deep\n"), "pkg/deep.py": "\n"}) == ("0.0000", None)


def test_a_c1_cell_that_changed_only_docs_is_na_no_source_file_changed(tmp_path):
    assert grade(tmp_path, *c1_cell(tmp_path, {"docs/architecture.md": C1_REFERENCE["docs/architecture.md"]})) == \
        (None, "no source file changed")


# --- the ratio, the NA reasons and the registration -----------------------------------------------------------------


def test_the_value_is_rules_passed_over_rules_with_files_in_scope(tmp_path, monkeypatch):
    rule = architecture.RULES["D1"][0]
    monkeypatch.setitem(architecture.RULES, "D1", (
        rule,  # passes: the reference's only using is AiDe.Core.Facts
        ("fails", rule[1], rule[2], lambda work, path: ["X"]),
        ("no file in scope", "nowhere/", ".cs", lambda work, path: ["X"]),
    ))
    assert grade(tmp_path, *d1_cell(tmp_path, D1_REFERENCE)) == ("0.5000", None)


def test_a_task_with_no_rule_row_is_na_before_the_archive_is_read(tmp_path):
    folder, cell = d1_cell(tmp_path, {})
    shutil.rmtree(folder / "ws", onexc=make_writable)
    assert grade(tmp_path, folder, {**cell, "task": "B1"}) == (None, "no architecture rules for this task")


@pytest.mark.parametrize(("fault", "reason"), [("no ws", "no working copy in the archive"),
                                               ("no builder commit", "pre-turn commit not found in the working copy")])
def test_the_shared_na_reasons(tmp_path, fault, reason):
    folder, cell = d1_cell(tmp_path, D1_REFERENCE)
    if fault == "no ws":
        shutil.rmtree(folder / "ws", onexc=make_writable)
    else:
        cell["pack"] = "on"  # a pack-on cell whose pack commit is missing (F11)
    assert grade(tmp_path, folder, cell) == (None, reason)


def test_a_git_archive_timeout_is_na_hb_grd_002(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, D1_REFERENCE)
    real = procs.run

    def run(argv, **kwargs):
        if "archive" in argv:
            return procs.Completed(returncode=None, stdout="", stderr="", timed_out=True, truncated=False, seconds=7.0)
        return real(argv, **kwargs)

    monkeypatch.setattr(procs, "run", run)
    out = architecture.grade_cell(arch_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "arch", 7))
    assert encode(out[METRIC]) == (None, "HB-GRD-002 grading step timeout after 7 s")


def test_architecture_is_registered_and_writes_its_log_as_evidence(tmp_path):
    folder, cell = d1_cell(tmp_path, {**D1_REFERENCE, "src/AiDe.Core/Projections/Bad.cs": "using Serilog;\n"})
    inp = arch_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "architecture")
    out = architecture.grade_cell(inp)
    assert runner.GRADERS["architecture"] is architecture.grade_cell
    assert {m: (s.value, s.reason, s.evidence) for m, s in out.items()} == \
        {METRIC: (Decimal("0.0000"), None, "grading/g/c1/architecture/architecture.log")}
    rule = "D1 Projections usings: System or AiDe.Core"
    assert (inp.out_dir / "architecture.log").read_text(encoding="utf-8") == \
        f"fail\t{rule}\tsrc/AiDe.Core/Projections/Bad.cs\tSerilog\npass\t{rule}\t{PROJECTION}\t\n"
    assert [p.name for p in inp.out_dir.iterdir()] == ["architecture.log"]  # the two trees are gone
    assert architecture.grade_cell(dataclasses.replace(inp, metrics={})) == {}


def test_the_rule_table_is_in_a_module_grader_build_hashes():  # design: hashed by grader_build
    assert Path(architecture.__file__).resolve() in {p.resolve() for p in Path(runner.__file__).parent.glob("*.py")}
    assert set(architecture.RULES) == {"C1", "D1"}


# --- the gate run row15-d1-1, read-only (HB_GATE_RUNS) ---------------------------------------------------------------

GATE_RUNS = Path(os.environ.get("HB_GATE_RUNS") or ROOT / "runs")
D1_GATE = {  # cp = copilot-sol, cx = codex-sol, cc = cc-opus; on/off = the pack (design: Architecture, Fixtures)
    "4a6250261f80ded4": ("1.0000", None),  # cp on
    "3ff04431d3b5ac27": ("1.0000", None),  # cx on: committed its two files after the pack commit
    "35af195cfe821dca": (None, "no source file changed"),  # cc on: nothing in ws/ changed
    "caa8ca38b1a929a8": ("1.0000", None),  # cp off
    "2535962f830d7718": ("1.0000", None),  # cx off
    "c3d40fa1377ba0dc": ("1.0000", None),  # cc off
}


def test_the_d1_gate_cells_conform_and_the_archive_is_unchanged(tmp_path):
    run = GATE_RUNS / "row15-d1-1"
    if not (run / "plan.json").is_file():
        pytest.skip("gate run row15-d1-1 is not on this host (set HB_GATE_RUNS to the runs folder)")
    attempts = {e["cell_id"]: e["archive_attempt"] for e in views.rows(run, "events") if e["kind"] == "cell.archived"}
    cells = {c["cell_id"]: c for c in plan.load_confirmed(run)["cells"]}
    got = {}
    for cid, attempt in sorted(attempts.items()):
        folder = run / "archive" / cid / f"attempt-{attempt}"
        before = tree_digest(folder)
        out = architecture.grade_cell(arch_input(tmp_path, folder, cells[cid], tmp_path / "grading" / cid / "architecture"))
        got[cid] = encode(out[METRIC])
        assert tree_digest(folder) == before, f"grading wrote under the archive of {cid}"
    assert got == D1_GATE
