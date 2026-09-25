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
from archived_runs import ROOT, gate_runs_root
from test_grade_correctness import d1_cell, tree_digest

from harness_bench import config, plan, procs, views
from harness_bench.archive import make_writable
from harness_bench.grade import CellInput, drift, runner
from harness_bench.grade.runner import applicable

CATALOG = config.load_yaml(ROOT / "bench" / "metrics.yaml")
SCOPE = ("scope_creep", "scope_creep_files")
MEASURED = (*SCOPE, "convention_drift")


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


@pytest.mark.parametrize("step", ["archive", "check-ignore"])  # the pre-turn tree, then its ignore rules
def test_a_git_timeout_is_na_hb_grd_002(tmp_path, monkeypatch, step):
    folder, cell = d1_cell(tmp_path, BLOCK)
    real = procs.run

    def run(argv, **kwargs):
        if step in argv:
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
    assert [p.name for p in inp.out_dir.iterdir()] == ["drift.log"]  # the trees and the ignore-rules git dir are gone


# --- files the pre-turn tree's own ignore rules exclude (the pack hook's marker in the gate's pack-on cells) ----------

MARKER = "docs/audit/.run-starts.json"  # the pack's session-start marker, ignored by the pack's .gitignore


def pack_cell_with_ignore(tmp_path: Path, overlay: dict) -> tuple[Path, dict]:
    """A pack-on cell whose pack commit also carries `.gitignore` naming the marker, then `overlay`, uncommitted."""
    from test_grade_correctness import git

    folder, cell = d1_cell(tmp_path, {}, pack=True)
    ws = folder / "ws"
    (ws / ".gitignore").write_text(f"{MARKER}\nLICENSE\nscratch/\n", encoding="utf-8", newline="")  # LICENSE is tracked
    git(ws, "add", ".gitignore")
    git(ws, "commit", "-q", "--amend", "-m", "ai-forward pack revision 95")
    for rel, text in overlay.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text, encoding="utf-8", newline="")
    return folder, cell


def test_an_untracked_file_the_pre_turn_ignore_rules_name_is_not_scope_creep(tmp_path):  # the gate's 35af and 4a62
    got = grade_d1(tmp_path, *pack_cell_with_ignore(tmp_path, {MARKER: '{\n  "s": "2026-09-25T06:27:25Z"\n}\n'}))
    assert {m: got[m] for m in MEASURED} == \
        {"scope_creep": (0, None), "scope_creep_files": (0, None), "convention_drift": (None, "no lines changed")}


def test_more_ignored_files_than_one_check_ignore_call_takes_are_all_asked(tmp_path):  # 100 paths per call
    got = grade_d1(tmp_path, *pack_cell_with_ignore(tmp_path, {f"scratch/f{i:03}.txt": "x\n" for i in range(150)}))
    assert {m: got[m] for m in SCOPE} == {"scope_creep": (0, None), "scope_creep_files": (0, None)}


def test_the_cells_own_ignore_rule_hides_nothing_and_a_tracked_file_under_a_pre_turn_rule_still_counts(tmp_path):
    folder, cell = pack_cell_with_ignore(tmp_path, {"src/AiDe.Mcp/Extra.cs": "// x\n// y\n"})
    ws = folder / "ws"
    (ws / ".gitignore").write_text(f"{MARKER}\nLICENSE\nscratch/\nsrc/AiDe.Mcp/Extra.cs\n", encoding="utf-8", newline="")
    (ws / "LICENSE").write_bytes((ws / "LICENSE").read_bytes() + b"one more line\n")
    got = grade_d1(tmp_path, folder, cell)
    assert {m: got[m] for m in MEASURED} == \
        {"scope_creep": (1 + 1 + 2, None), "scope_creep_files": (3, None), "convention_drift": ("0.00", None)}


# --- the gate run row15-d1-1, read-only (HB_GATE_RUNS) ---------------------------------------------------------------

GATE_RUNS = gate_runs_root()
D1_GATE = {  # cp = copilot-sol, cx = codex-sol, cc = cc-opus; on/off = the pack (design: Drift, Fixtures)
    "4a6250261f80ded4": ("0.00", None),  # cp on
    "3ff04431d3b5ac27": ("0.00", None),  # cx on: committed its two files after the pack commit
    "35af195cfe821dca": (None, "no lines changed"),  # cc on: nothing in ws/ changed
    "caa8ca38b1a929a8": ("0.00", None),  # cp off
    "2535962f830d7718": ("0.00", None),  # cx off
    "c3d40fa1377ba0dc": ("0.00", None),  # cc off
}


def test_the_d1_gate_cells_have_no_scope_creep_and_the_archive_is_unchanged(tmp_path):
    run = GATE_RUNS / "row15-d1-1"
    if not (run / "plan.json").is_file():
        pytest.skip("gate run row15-d1-1 is not on this host (set HB_GATE_RUNS to the runs folder)")
    attempts = {e["cell_id"]: e["archive_attempt"] for e in views.rows(run, "events") if e["kind"] == "cell.archived"}
    cells = {c["cell_id"]: c for c in plan.load_confirmed(run)["cells"]}
    got = {}
    for cid, attempt in sorted(attempts.items()):
        folder = run / "archive" / cid / f"attempt-{attempt}"
        before = tree_digest(folder)
        out = drift.grade_cell(drift_input(tmp_path, folder, cells[cid], tmp_path / "grading" / cid / "drift"))
        got[cid] = {m: encode(out[m]) for m in MEASURED}
        assert tree_digest(folder) == before, f"grading wrote under the archive of {cid}"
    assert got == {cid: {"scope_creep": (0, None), "scope_creep_files": (0, None), "convention_drift": cd}
                   for cid, cd in D1_GATE.items()}


def test_convention_drift_has_its_catalog_scale_of_2():
    # the runner refuses a Decimal for a metric with no catalog scale (runner.py), which would make the whole drift
    # grader NA "HB-GRD-003" in a real pass; the design gives convention_drift at scale 2 (GR-CODE c3 finding)
    catalog = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    scales = {m["id"]: m.get("scale") for a in catalog["areas"].values() for m in a.get("metrics") or []}
    assert scales["convention_drift"] == 2
