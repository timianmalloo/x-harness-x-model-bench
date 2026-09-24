"""`bench` (design: Exposed contracts, exit codes, CLI states; T-CLI-exit, T6 stdout-only JSON).

Exit codes: 0 ok · 1 invalid input · 2 usage (argparse) · 3 run incomplete · 4 not built · 5 integrity.
"""

import hashlib
import json

import pytest
from archived_runs import GOOD, make_root, make_run
from test_tools import _fake_tree

from harness_bench import cli, gitsafe, ledger, oslock, status


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _bench(capsys, root, tmp_path, *args):
    code = cli.main(["--root", str(root), "--runs", str(tmp_path / "runs"), *args])
    out, err = capsys.readouterr()
    return code, out, err


def test_an_unknown_run_is_exit_1_with_the_exact_message(capsys, root, tmp_path):
    for command in ("status", "grade", "report", "verify", "teardown", "run"):
        code, out, err = _bench(capsys, root, tmp_path, command, "nope")
        assert (code, out, err) == (1, "", "HB-USR-001: no run nope under runs/. Run bench plan to create one.\n"), command


def test_usage_errors_are_exit_2(capsys, root, tmp_path):
    with pytest.raises(SystemExit) as e:
        _bench(capsys, root, tmp_path, "status")
    assert e.value.code == 2


def test_status_json_writes_only_bench_status_to_stdout(capsys, root, tmp_path, monkeypatch):
    make_run(root, tmp_path, {"a": GOOD})
    monkeypatch.setenv("NO_COLOR", "1")
    code, out, err = _bench(capsys, root, tmp_path, "status", "r1", "--json")
    assert code == 0 and err == ""
    assert status.parse(out).run_id == "r1" and out.endswith("\n") and out.count("\n") == 1


def test_status_text(capsys, root, tmp_path):
    make_run(root, tmp_path, {"a": GOOD})
    code, out, _ = _bench(capsys, root, tmp_path, "status", "r1")
    assert code == 0 and out.startswith("Run r1: not running (incomplete). 1/1 cells ended.")


def test_grade_then_report_writes_the_page(capsys, root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    assert _bench(capsys, root, tmp_path, "report", "r1")[0] == 4  # not graded yet
    assert not (run_dir / "report.html").exists()
    code, out, _ = _bench(capsys, root, tmp_path, "grade", "r1")
    assert code == 0 and "graded 1 cell" in out
    code, out, _ = _bench(capsys, root, tmp_path, "report", "r1")
    assert code == 0 and "pass@1" in out and (run_dir / "report.html").is_file()


def test_grade_while_another_pass_holds_the_lock_is_exit_1(capsys, root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with oslock.RunLock.acquire(run_dir / "grade.lock"):
        code, _, err = _bench(capsys, root, tmp_path, "grade", "r1")
    assert code == 1 and err.startswith("HB-GRD-001")


def test_verify_passes_a_sound_run(capsys, root, tmp_path):
    make_run(root, tmp_path, {"a": GOOD})
    code, out, _ = _bench(capsys, root, tmp_path, "verify", "r1")
    assert code == 0 and out.endswith("verify: ok\n")


def test_verify_finds_an_edited_ledger_line(capsys, root, tmp_path):  # HB-LED-002, exit 5
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    seg = run_dir / "events" / "engine-1.jsonl"
    seg.write_bytes(seg.read_bytes().replace(b'"outcome":"completed"', b'"outcome":"failed"'))
    code, _, err = _bench(capsys, root, tmp_path, "verify", "r1")
    assert code == 5 and "HB-LED-002" in err


def test_verify_finds_an_edited_archive_file(capsys, root, tmp_path):  # HB-LED-005, exit 5
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    (run_dir / "archive" / "a" / "attempt-1" / "ws" / "slug.py").write_text("tampered", encoding="utf-8")
    code, _, err = _bench(capsys, root, tmp_path, "verify", "r1")
    assert code == 5 and "HB-LED-005" in err


def test_an_archive_row_added_afterwards_breaks_the_archive_hash(capsys, root, tmp_path):  # HB-LED-005
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    extra = run_dir / "archive" / "a" / "attempt-1" / "ws" / "added.py"
    extra.write_text("x = 1\n", encoding="utf-8")
    with ledger.SegmentWriter.create(run_dir / "archive_files", "engine-2") as af:
        af.append({"run_id": "r1", "cell_id": "a", "path": "ws/added.py", "kind": "file", "size": extra.stat().st_size,
                   "sha256": hashlib.sha256(extra.read_bytes()).hexdigest(), "link_target": "", "archive_attempt": 1})
    code, _, err = _bench(capsys, root, tmp_path, "verify", "r1")
    assert code == 5 and "HB-LED-005" in err and "archive_hash" in err


def test_a_broken_ledger_is_an_integrity_failure_for_every_reader(capsys, root, tmp_path):  # exit 5
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    seg = run_dir / "events" / "engine-1.jsonl"
    seg.write_bytes(seg.read_bytes().replace(b'"outcome":"completed"', b'"outcome":"failed"'))
    for command in ("status", "report", "grade"):
        code, _, err = _bench(capsys, root, tmp_path, command, "r1")
        assert (code, err[:10]) == (5, "HB-LED-002"), command


def test_verify_warns_about_an_abandoned_pass_and_exits_0(capsys, root, tmp_path):  # HB-LED-004
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "scores", "grade-dead") as dead:
        dead.append({"kind": "score"})
    code, _, err = _bench(capsys, root, tmp_path, "verify", "r1")
    assert code == 0 and "HB-LED-004" in err and "scores/grade-dead" in err


def test_teardown_removes_archived_cells_and_keeps_the_rest(capsys, root, tmp_path, base):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": GOOD}, archived={"a"})
    cells = base / "cells"
    for cid in ("a", "b"):
        (cells / "r1" / cid / "ws").mkdir(parents=True)
    with oslock.RunLock.acquire(run_dir / ".lock", "HB-RUN-003"):
        code, _, err = _bench(capsys, root, tmp_path, "--cells-root", str(cells), "teardown", "r1")
    assert code == 1 and err.startswith("HB-RUN-003")
    code, out, _ = _bench(capsys, root, tmp_path, "--cells-root", str(cells), "teardown", "r1")
    assert code == 0 and not (cells / "r1" / "a").exists() and (cells / "r1" / "b").exists()
    assert "kept b: not archived" in out


def test_run_refuses_a_run_that_already_started(capsys, root, tmp_path, base):
    make_run(root, tmp_path, {"a": GOOD})
    code, _, err = _bench(capsys, root, tmp_path, "--cells-root", str(base / "cells"), "--tools-dir", str(_fake_tree(tmp_path / "t")),
                          "run", "r1")
    assert code == 1 and err.startswith("HB-USR-002")


def _pack_repo(path):
    (path / "pack" / "adapters").mkdir(parents=True)
    (path / "pack" / "adapters" / "INSTALL.md").write_text("revision: 7\n", encoding="utf-8")
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "pack"]):
        gitsafe.git(args, cwd=path, timeout=60, identity=True)
    return gitsafe.git(["rev-parse", "HEAD"], cwd=path, timeout=60).stdout.strip()


def test_plan_confirm_freezes_builds_pack_and_prompt(capsys, root, tmp_path):
    for name in ("bom.yaml", "matrix.phase1.yaml"):
        (root / "bench" / name).write_bytes((cli.config.repo_root() / "bench" / name).read_bytes())
    commit = _pack_repo(tmp_path / "ai-forward")
    tools_dir = _fake_tree(tmp_path / "tools")
    code, out, err = _bench(capsys, root, tmp_path, "--tools-dir", str(tools_dir), "plan", "--matrix", str(root / "bench" / "matrix.phase1.yaml"),
                            "--run-id", "p1", "--pack-source", str(tmp_path / "ai-forward"), "--confirm")
    assert code == 0, err
    p = json.loads((tmp_path / "runs" / "p1" / "plan.json").read_text(encoding="utf-8"))
    assert p["pack"] == {"source": str(tmp_path / "ai-forward"), "commit": commit, "revision": 7}
    assert p["builds"]["codex"]["version"] == "0.156.0" and len(p["cells"]) == 4
    assert "envelope" in out and "4 cells" in out
    assert _bench(capsys, root, tmp_path, "--tools-dir", str(tools_dir), "plan", "--matrix", str(root / "bench" / "matrix.phase1.yaml"),
                  "--run-id", "p1", "--pack-source", str(tmp_path / "ai-forward"), "--confirm")[0] == 1  # frozen


def test_plan_json_ids_equal_the_frozen_plans_cell_ids(capsys, root, tmp_path):  # T4-2: two cell-id definitions (Simplifier)
    for name in ("bom.yaml", "matrix.phase1.yaml"):
        (root / "bench" / name).write_bytes((cli.config.repo_root() / "bench" / name).read_bytes())
    _pack_repo(tmp_path / "ai-forward")
    tools_dir = _fake_tree(tmp_path / "tools")
    matrix_path = str(root / "bench" / "matrix.phase1.yaml")
    code, out, err = _bench(capsys, root, tmp_path, "--tools-dir", str(tools_dir), "plan", "--matrix", matrix_path, "--json")
    assert code == 0, err
    json_ids = {c["id"] for c in json.loads(out)}
    code, out, err = _bench(capsys, root, tmp_path, "--tools-dir", str(tools_dir), "plan", "--matrix", matrix_path,
                            "--run-id", "p2", "--pack-source", str(tmp_path / "ai-forward"), "--confirm")
    assert code == 0, err
    frozen = json.loads((tmp_path / "runs" / "p2" / "plan.json").read_text(encoding="utf-8"))
    assert json_ids == {c["cell_id"] for c in frozen["cells"]}
