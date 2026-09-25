"""`bench` (design: Exposed contracts, exit codes, CLI states; T-CLI-exit, T6 stdout-only JSON).

Exit codes: 0 ok · 1 invalid input · 2 usage (argparse) · 3 run incomplete · 4 not built · 5 integrity.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest
from archived_runs import GOOD, make_root, make_run
from test_tools import _fake_tree

from harness_bench import cli, gitsafe, ledger, oslock, status


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


@pytest.fixture(autouse=True)
def _no_real_credential_home(monkeypatch, tmp_path):
    """bench/profiles/*.yaml (copied by make_root) still points at ~/.claude, ~/.codex: `bench report`'s
    exact-value credential scan (HB-SEC-001) resolves that with Path.expanduser(). Redirect every test's
    `~` to an empty, unwritten folder so no test in this file ever reads the operator's real credential
    file -- tests that exercise the scan itself always plant fake tokens under tmp_path instead."""
    fake_home = tmp_path / "fake-home"
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("HOME", str(fake_home))


def _bench(capsys, root, tmp_path, *args):
    code = cli.main(["--root", str(root), "--runs", str(tmp_path / "runs"), *args])
    out, err = capsys.readouterr()
    return code, out, err


def test_an_unknown_run_is_exit_1_with_the_exact_message(capsys, root, tmp_path):
    for command in ("status", "grade", "report", "verify", "teardown", "run"):
        code, out, err = _bench(capsys, root, tmp_path, command, "nope")
        assert (code, out, err) == (1, "", "HB-USR-001: no run nope under runs/. Run bench plan to create one.\n"), command


def test_stop_refuses_unknown_and_unlocked_runs(capsys, root, tmp_path):  # CLI-1
    assert _bench(capsys, root, tmp_path, "stop", "nope")[0] == 1
    make_run(root, tmp_path, {"a": GOOD})
    code, out, err = _bench(capsys, root, tmp_path, "stop", "r1")
    assert code == 1 and out == "" and "not running" in err


def test_stop_writes_an_atomic_control_file(capsys, root, tmp_path):  # CLI-2
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with oslock.RunLock.acquire(run_dir / ".lock", "HB-RUN-003"):
        code, out, err = _bench(capsys, root, tmp_path, "stop", "r1")
    files = list((run_dir / "control").glob("*.json"))
    assert code == 0 and err == "" and "stop requested" in out
    assert len(files) == 1 and not list((run_dir / "control").glob("*.tmp"))
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["schema"] == "bench-control/1" and data["control"] == "stop"
    assert data["uuid"] == files[0].stem and data["decision_id"] is None and data["option"] is None


def test_usage_errors_are_exit_2(capsys, root, tmp_path):
    with pytest.raises(SystemExit) as e:
        _bench(capsys, root, tmp_path, "status")
    assert e.value.code == 2


def test_plan_flags_and_confirmation_name_the_timeout_and_token_cap(monkeypatch, capsys, root, tmp_path):  # P-3
    import argparse

    parser = cli.build_parser()
    args = parser.parse_args(["--root", str(root), "plan", "--decision-timeout-minutes", "5", "--spend-cap-tokens", "900"])
    assert (args.decision_timeout_minutes, args.spend_cap_tokens) == (5, 900)
    matrix = {"bom": {"subset": ["X1"]}, "combos": []}
    monkeypatch.setattr(cli.config, "load_yaml", lambda path: {"version": 1} if Path(path).name == "bom.yaml" else matrix)
    monkeypatch.setattr(cli.config, "validate_matrix", lambda *a: None)
    monkeypatch.setattr(cli.tools, "resolve", lambda path: {})
    monkeypatch.setattr(cli, "_pack", lambda *a: {"source": "pack", "commit": "c" * 40, "revision": 1})
    received = {}

    def fake_build_plan(*a, **kw):
        received.update(kw)
        return {"cells": [], "builds": {}, "pack": {"revision": 1, "commit": "c" * 40},
                "parameters": {"parallelism": 2, **kw.get("parameters", {})}, "envelope_seconds": 0, "price_list_hash": ""}

    monkeypatch.setattr(cli.plan, "build_plan", fake_build_plan)
    args = argparse.Namespace(**{**vars(args), "runs": str(tmp_path / "runs"), "cells_root": str(tmp_path / "cells"),
                                 "tools_dir": str(tmp_path / "tools"), "pack_source": str(tmp_path / "pack"),
                                 "run_id": "p", "json": False, "confirm": False, "matrix": None, "parallelism": 2})
    assert cli.cmd_plan(args) == 0
    output = capsys.readouterr().out
    assert received["parameters"] == {"decision_timeout": 300, "spend_cap_tokens": 900}
    assert "decision timeout: 5 min" in output
    assert "spend cap: 900 tokens, checked when each cell ends" in output


def test_plan_flags_refuse_non_positive_values(root):
    parser = cli.build_parser()
    for flag, value in (("--decision-timeout-minutes", "0"), ("--spend-cap-tokens", "-1")):
        with pytest.raises(SystemExit) as error:
            parser.parse_args(["--root", str(root), "plan", flag, value])
        assert error.value.code == 2


def test_bench_run_refuses_a_confirmed_old_plan_before_starting(capsys, root, tmp_path):  # P-2
    make_run(root, tmp_path, {"a": GOOD})  # the fixture's confirmed plan lacks newer engine parameters
    code, out, err = _bench(capsys, root, tmp_path, "run", "r1")
    assert code == 1 and out == ""
    assert "HB-USR-002: old plan missing parameters" in err


def test_status_json_writes_only_bench_status_to_stdout(capsys, root, tmp_path, monkeypatch):
    make_run(root, tmp_path, {"a": GOOD})
    monkeypatch.setenv("NO_COLOR", "1")
    code, out, err = _bench(capsys, root, tmp_path, "status", "r1", "--json")
    assert code == 0 and err == ""
    assert status.parse(out).run_id == "r1" and out.endswith("\n") and out.count("\n") == 1


def test_status_json_is_plain_even_under_a_tty(capsys, root, tmp_path, monkeypatch):  # T4-7
    make_run(root, tmp_path, {"a": GOOD})
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    code, out, err = _bench(capsys, root, tmp_path, "status", "r1", "--json")
    assert code == 0 and err == ""
    assert status.parse(out).run_id == "r1" and out.endswith("\n") and out.count("\n") == 1
    assert "\x1b[" not in out  # no ANSI escapes leak in under a real terminal


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


def test_report_refuses_when_the_hosts_credential_value_leaks_into_the_report(capsys, root, tmp_path):  # T4-1
    fake_home = tmp_path / "fake-home"  # _no_real_credential_home points USERPROFILE/HOME here
    (fake_home / ".claude").mkdir(parents=True)
    token = "ROTATEDINTEGRATIONtoken0123456789"
    (fake_home / ".claude" / ".credentials.json").write_text(json.dumps({"accessToken": token}), encoding="utf-8")
    run_dir = make_run(root, tmp_path, {"a": GOOD}, combos={"a": token})  # the value leaks into the cell's label
    code, _, err = _bench(capsys, root, tmp_path, "grade", "r1")
    assert code == 0
    code, _, err = _bench(capsys, root, tmp_path, "report", "r1")
    assert code == 5 and "HB-SEC-001" in err and token not in err
    assert not (run_dir / "report.html").exists()


def test_report_does_not_print_a_label_before_the_credential_scan(capsys, root, tmp_path):
    """cmd_report prints the CLI table before html.write scans. A label that carries a
    credential value must not reach stdout (residual 5)."""
    fake_home = tmp_path / "fake-home"
    (fake_home / ".claude").mkdir(parents=True)
    token = "ROTATEDLABELSCAN0123456789"
    (fake_home / ".claude" / ".credentials.json").write_text(json.dumps({"accessToken": token}), encoding="utf-8")
    run_dir = make_run(root, tmp_path, {"a": GOOD}, combos={"a": token})
    code, _, _ = _bench(capsys, root, tmp_path, "grade", "r1")
    assert code == 0
    code, out, err = _bench(capsys, root, tmp_path, "report", "r1")
    assert token not in out
    assert code == 5 and "HB-SEC-001" in err and token not in err
    assert not (run_dir / "report.html").exists()


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


def test_run_closes_its_engine_log_handler_so_the_file_is_deletable(capsys, root, tmp_path, monkeypatch):  # T9-2
    """cmd_run must release the FileHandler configure_logging installs, or engine.log stays open and
    (on Windows) the run's folder can never be removed. The engine itself is stubbed out: this test is
    about cmd_run's own handler lifecycle, not a full run."""
    from harness_bench import engine, plan, preflight, status

    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "plan.json").write_text("{}", encoding="utf-8")
    p = {"run_id": "r1", "trace_id": "a" * 32, "tasks": {}, "builds": {}, "parameters": plan.DEFAULT_PARAMETERS.copy()}
    monkeypatch.setattr(plan, "load_confirmed", lambda rd: p)
    monkeypatch.setattr(preflight, "check", lambda *a, **k: None)

    class _Summary:
        exit_code = 0

    class _FakeEngine:
        def __init__(self, *a, **k):
            pass

        def run(self):
            return _Summary()

    monkeypatch.setattr(engine, "Engine", _FakeEngine)
    monkeypatch.setattr(status, "build", lambda rd: object())
    monkeypatch.setattr(status, "text", lambda s: "")

    code, _, err = _bench(capsys, root, tmp_path, "--cells-root", str(tmp_path / "cells"),
                          "--tools-dir", str(tmp_path / "tools"), "run", "r1")
    assert code == 0, err
    (run_dir / "engine.log").unlink()  # only succeeds once cmd_run closed its handler
    assert not (run_dir / "engine.log").exists()


def test_run_refuses_a_run_that_already_started(capsys, root, tmp_path, base):
    make_run(root, tmp_path, {"a": GOOD})
    code, _, err = _bench(capsys, root, tmp_path, "--cells-root", str(base / "cells"), "--tools-dir", str(_fake_tree(tmp_path / "t")),
                          "run", "r1")
    assert code == 1 and err.startswith("HB-USR-002")


_PACK_APPLY_STUB = '''\
import argparse, json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("action")
p.add_argument("--source", required=True)
p.add_argument("--target", required=True)
p.add_argument("--install", action="store_true")
p.add_argument("--no-baselines", action="store_true")
p.add_argument("--json", action="store_true")
p.add_argument("--project", required=True)
args = p.parse_args()

(Path(args.target) / "PACK-MARKER.txt").write_text(args.project, encoding="utf-8")
print(json.dumps({"rows": [{"path": "PACK-MARKER.txt", "status": "ok", "action": "ADD"}]}))
'''


def _pack_repo(path, with_pack_apply=False):
    (path / "pack" / "adapters").mkdir(parents=True)
    (path / "pack" / "adapters" / "INSTALL.md").write_text("revision: 7\n", encoding="utf-8")
    if with_pack_apply:
        (path / "pack" / "scripts").mkdir(parents=True)
        (path / "pack" / "scripts" / "pack-apply.py").write_text(_PACK_APPLY_STUB, encoding="utf-8")
    for args in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "pack"]):
        gitsafe.git(args, cwd=path, timeout=60, identity=True)
    return gitsafe.git(["rev-parse", "HEAD"], cwd=path, timeout=60).stdout.strip()


def test_a_relative_tools_dir_resolves_absolute_and_the_pack_on_build_succeeds(root, tmp_path, monkeypatch):  # HB-CELL-113 (T8 defect 2)
    """Real E2E: `bench --tools-dir .tools/harness run ...` failed a pack-on cell with HB-CELL-113.
    install_pack's subprocess runs with cwd = the cell working copy, not the process cwd; a relative
    --tools-dir left the pack root (tools_dir.parent) relative, so pack-apply.py resolved under the
    workspace and was never found. cli.main resolves every path argument (--root, --runs, --cells-root,
    --tools-dir, --pack-source, --matrix) to absolute once, at parse time."""
    commit = _pack_repo(tmp_path / "ai-forward", with_pack_apply=True)
    parser = cli.build_parser()
    monkeypatch.chdir(tmp_path)
    args = parser.parse_args(["--root", str(root), "--tools-dir", "tools", "plan", "--pack-source", "ai-forward"])
    cli._resolve_paths(args)
    assert Path(args.tools_dir).is_absolute() and Path(args.pack_source).is_absolute()

    pack_root = Path(args.tools_dir).parent / "pack"
    p = {"pack": {"source": args.pack_source, "commit": commit}, "parameters": {"git_timeout": 60}}
    build = cli._workspace_builder(Path(args.root), p, tmp_path / "sources", pack_root)
    result = build({"task": "X1", "task_version": "v1", "pack": "on"}, tmp_path / "cells" / "c1")
    assert result == {"pack": "on", "pack_manifest": 1}
    assert (tmp_path / "cells" / "c1" / "ws" / "PACK-MARKER.txt").read_text(encoding="utf-8") == "X1"


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
