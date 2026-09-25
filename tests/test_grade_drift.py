"""Drift grader: scope_creep, scope_creep_files and convention_drift (design phase3-graders, section Drift, GR-CODE c3).

- The D1 fixtures are the frozen `tasks/D1/workspace` in a temporary git repo that reproduces the archive's commits
  (G9; `d1_cell` from the correctness tests, the same builder c1's change-reader tests use). They need git only.
- Every grade asserts the archive's bytes did not move (F9).
"""

import dataclasses
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import ROOT
from test_grade_correctness import d1_cell, tree_digest

from harness_bench import config, procs
from harness_bench.archive import make_writable
from harness_bench.grade import CellInput, drift, runner
from harness_bench.grade.runner import applicable

CATALOG = config.load_yaml(ROOT / "bench" / "metrics.yaml")
MEASURED = ("scope_creep", "scope_creep_files", "convention_drift")


def encode(score) -> tuple:
    """(value, reason); convention_drift is a Decimal written at scale 2 (design: per 100 changed lines, scale 2)."""
    v = score.value
    return (f"{v:.2f}" if isinstance(v, Decimal) else v), score.reason


def drift_input(run_dir: Path, archive: Path, cell: dict, out_dir: Path, timeout: int = 900) -> CellInput:
    task_dir = ROOT / "tasks" / cell["task"]
    out_dir.mkdir(parents=True, exist_ok=True)
    return CellInput(run_dir=run_dir, root=ROOT, plan={"parameters": {"grading_step_timeout": timeout}}, cell=cell,
                     task=config.load_yaml(task_dir / "task.yaml"), task_dir=task_dir, archive=archive, out_dir=out_dir,
                     events=(), record_reason=None, model_calls=(), tool_calls=(), turn_usage=(),
                     metrics=applicable(CATALOG, ["drift"])["drift"], allow_model_calls=False, extraction=None, prices=None)


def grade_d1(tmp_path: Path, folder: Path, cell: dict) -> dict[str, tuple]:
    """Every drift Score of the cell as (value, reason); the archive's bytes must not move (F9)."""
    before = tree_digest(folder)
    out = drift.grade_cell(drift_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "drift"))
    assert tree_digest(folder) == before, "grading wrote under the archive"
    return {m: encode(s) for m, s in out.items()}


# --- the design's seeds ----------------------------------------------------------------------------------------------

MCP = "src/AiDe.Mcp/ServerContext.cs"


def test_a_3_line_edit_outside_the_blast_radius_is_scope_creep_3_in_1_file(tmp_path):  # design: Seeded
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {MCP: lambda text: "// one\n// two\n// three\n" + text}))
    assert {m: got.get(m) for m in MEASURED} == \
        {"scope_creep": (3, None), "scope_creep_files": (1, None), "convention_drift": ("0.00", None)}


PROJECTION = "src/AiDe.Core/Projections/EvidenceCensusProjection.cs"
REFERENCE = {PROJECTION: (ROOT / "tasks" / "D1" / "oracle" / "reference" / PROJECTION).read_text(encoding="utf-8")}


def test_a_pack_commit_stand_in_outside_the_blast_radius_is_not_scope_creep(tmp_path):  # design: Seeded, pack-on
    got = grade_d1(tmp_path, *d1_cell(tmp_path, REFERENCE, pack=True))  # .editorconfig and docs/pack/: outside the radius
    assert {m: got.get(m) for m in ("scope_creep", "scope_creep_files")} == {"scope_creep": (0, None), "scope_creep_files": (0, None)}


BLOCK = {"src/AiDe.Core/Projections/Block.cs":  # 10 lines; line 4 breaks R1 (a file-scoped namespace)
         "// seeded: a block-scoped namespace\nusing System;\n\nnamespace AiDe.Core.Projections\n{\n"
         "    public static class Block\n    {\n        public static int X() => 1;\n    }\n}\n"}


def test_a_block_scoped_namespace_in_a_10_line_file_is_convention_drift_10(tmp_path):  # design: Seeded, 1 per 10 lines
    got = grade_d1(tmp_path, *d1_cell(tmp_path, BLOCK))
    assert {m: got.get(m) for m in MEASURED} == \
        {"scope_creep": (0, None), "scope_creep_files": (0, None), "convention_drift": ("10.00", None)}


# --- every other branch, with the design's NA reasons verbatim --------------------------------------------------------

NA_BY_DESIGN = {"spec_coverage": (None, "hidden-test coverage is partial_credit (not counted twice); no rubric for this task"),
                "constraint_violations": (None, "no constraint checklist in this task version"),
                "instruction_reread_rate": (None, "read targets not in the tool record (no arguments extracted)")}


def test_the_unmeasured_drift_metrics_are_na_with_the_design_reasons(tmp_path):  # R-67 DR-G2, R-68
    got = grade_d1(tmp_path, *d1_cell(tmp_path, BLOCK))
    assert {m: got[m] for m in NA_BY_DESIGN} == NA_BY_DESIGN
    assert set(got) == set(applicable(CATALOG, ["drift"])["drift"]) == {*NA_BY_DESIGN, *MEASURED}


def test_a_cell_that_changed_nothing_is_0_and_convention_drift_no_lines_changed(tmp_path):  # the gate's 35af shape
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {}))
    assert {m: got[m] for m in MEASURED} == \
        {"scope_creep": (0, None), "scope_creep_files": (0, None), "convention_drift": (None, "no lines changed")}


def test_only_lines_of_the_rules_file_type_are_the_convention_denominator(tmp_path):
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {"docs/notes.md": "one\ntwo\n"}))
    assert {m: got[m] for m in MEASURED} == \
        {"scope_creep": (2, None), "scope_creep_files": (1, None), "convention_drift": (None, "no lines changed")}


def test_a_changed_line_counts_twice_a_deleted_file_counts_every_line_and_crlf_counts_nothing(tmp_path):
    folder, cell = d1_cell(tmp_path, {MCP: lambda text: text.replace("namespace AiDe.Mcp;", "namespace AiDe.Mcp.Moved;", 1)})
    mcp = folder / "ws" / "src" / "AiDe.Mcp"
    for name in ("Program.cs", "ServerContext.cs"):  # CRLF alone is no change, and it is not one in the edited file
        (mcp / name).write_bytes((mcp / name).read_bytes().replace(b"\n", b"\r\n"))
    (mcp / "Tools.cs").write_bytes((mcp / "Tools.cs").read_bytes().removesuffix(b"\n"))  # its last line: 1 out, 1 in
    (mcp / "SessionIdentity.cs").unlink()  # 181 lines, the last one ending in LF
    got = grade_d1(tmp_path, folder, cell)
    assert {m: got[m] for m in MEASURED} == \
        {"scope_creep": (2 + 2 + 181, None), "scope_creep_files": (3, None), "convention_drift": ("0.00", None)}


BOM = chr(0xFEFF)  # written as UTF-8 by d1_cell: the three bytes EF BB BF


def test_a_block_namespace_on_a_first_line_after_a_utf8_bom_is_a_violation(tmp_path):
    got = grade_d1(tmp_path, *d1_cell(tmp_path, {"src/AiDe.Core/Projections/Bom.cs": BOM + "namespace AiDe.Core.Projections\n{\n}\n"}))
    assert got["convention_drift"] == ("33.33", None)


def test_a_symlink_is_its_target_text_and_never_followed(monkeypatch):  # as _changes (F17); no symlink privilege needed
    class Link:
        def is_symlink(self) -> bool:
            return True

        def read_bytes(self) -> bytes:
            raise AssertionError("the link was followed")

    monkeypatch.setattr(drift.os, "readlink", lambda path: "../../outside.txt")
    assert drift._lines(Link()) == [b"../../outside.txt"]


def test_an_added_line_that_opens_a_block_namespace_is_a_violation_and_a_file_scoped_one_is_not(tmp_path):
    folder, cell = d1_cell(tmp_path, {**REFERENCE, MCP: lambda text: text.replace("namespace AiDe.Mcp;", "namespace AiDe.Mcp {", 1)})
    got = grade_d1(tmp_path, folder, cell)
    assert got["convention_drift"] == ("2.22", None)  # 1 violation in 44 reference lines + 1 changed line


def test_a_task_with_no_rule_table_is_na_no_convention_rules(tmp_path):
    folder, cell = d1_cell(tmp_path, BLOCK)
    got = grade_d1(tmp_path, folder, {**cell, "task": "B1"})
    assert got["convention_drift"] == (None, "no convention rules for this task")


@pytest.mark.parametrize(("fault", "reason"), [("no ws", "no working copy in the archive"),
                                               ("no builder commit", "pre-turn commit not found in the working copy")])
def test_the_shared_na_reasons_hold_for_every_measured_metric(tmp_path, fault, reason):
    folder, cell = d1_cell(tmp_path, BLOCK)
    if fault == "no ws":
        shutil.rmtree(folder / "ws", onexc=make_writable)
    else:
        cell["pack"] = "on"  # a pack-on cell whose pack commit is missing (F11)
    got = grade_d1(tmp_path, folder, cell)
    assert {m: got[m] for m in MEASURED} == dict.fromkeys(MEASURED, (None, reason))


def test_a_git_archive_timeout_is_na_hb_grd_002(tmp_path, monkeypatch):
    folder, cell = d1_cell(tmp_path, BLOCK)
    real = procs.run

    def run(argv, **kwargs):
        if "archive" in argv:
            return procs.Completed(returncode=None, stdout="", stderr="", timed_out=True, truncated=False, seconds=7.0)
        return real(argv, **kwargs)

    monkeypatch.setattr(procs, "run", run)
    out = drift.grade_cell(drift_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "drift", 7))
    assert {m: encode(out[m]) for m in MEASURED} == dict.fromkeys(MEASURED, (None, "HB-GRD-002 grading step timeout after 7 s"))


def test_drift_is_registered_and_returns_only_the_applicable_metrics_with_its_log_as_evidence(tmp_path):
    folder, cell = d1_cell(tmp_path, BLOCK)
    inp = drift_input(tmp_path / "run", folder, cell, tmp_path / "run" / "grading" / "g" / "c1" / "drift")
    out = drift.grade_cell(dataclasses.replace(inp, metrics={"scope_creep": inp.metrics["scope_creep"]}))
    assert runner.GRADERS["drift"] is drift.grade_cell
    assert {m: (s.value, s.reason, s.evidence) for m, s in out.items()} == {"scope_creep": (0, None, "grading/g/c1/drift/drift.log")}
    assert (tmp_path / "run" / "grading" / "g" / "c1" / "drift" / "drift.log").read_text(encoding="utf-8") == \
        "added\tsrc/AiDe.Core/Projections/Block.cs\tinside\t+10 -0\tR1 file-scoped namespace:4\n"
