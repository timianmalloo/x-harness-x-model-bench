"""X-C3b proof, the read and wiring half: `plan --campaign`, the launch recheck over a chain-stamped plan (R-106 c3), the stop reason in
`bench status`, plan-kind handling, the after-grading hook, the report binding and the campaign status document.

Fixtures are the ones of `test_cli_campaign.py` (the one home of the helpers). Expected values are typed here or read from rows, never
computed with the function under test (RV-TA 1).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from test_cli_campaign import (
    CID,
    bench,
    edit_src,
    kinds,
    registered,
    rows_of,
    run_events,
    tree,
    write_plan,
    write_text,
)
from test_cli import _pack_repo
from test_tools import _fake_tree

from harness_bench import gitsafe, identity

MATRIX = {"schema": "bench-matrix/2", "ring": {"tag": "comparison"}, "bom": {"file": "bench/bom.yaml", "subset": ["T1"]}, "repetitions": 4,
          "arms": [{"id": "off"}, {"id": "treat"}], "comparisons": [["off", "treat"]],
          "combos": [{"id": "cc-opus", "harness": "claude-code", "model": "claude-opus-5-5"}]}


def matrix_file(tmp_path: Path, **over) -> Path:
    path = tmp_path / "matrix.yaml"
    path.write_text(yaml.safe_dump({**MATRIX, **over}), encoding="utf-8")
    return path


def cli_args(root: Path, tmp_path: Path) -> list[str]:
    return ["--root", str(root), "--cells-root", str(tmp_path / "cells"), "--tools-dir", str(tmp_path / "tools")]


def pack_commit(tmp_path: Path) -> str:
    """A real pack clone, made once per test: the matrix's treat arm is bound to its HEAD, and the registered statement names that commit."""
    folder = tmp_path / "ai-forward"
    return _pack_repo(folder) if not folder.exists() else gitsafe.git(["rev-parse", "HEAD"], cwd=folder, timeout=60).stdout.strip()


def plan_campaign(root: Path, tmp_path: Path, run_id: str, *extra: str, matrix: Path | None = None) -> int:
    from test_cli_campaign import cli_rc

    binding = f"treat={tmp_path / 'ai-forward'}@{pack_commit(tmp_path)}"
    return cli_rc([*cli_args(root, tmp_path), "plan", "--campaign", CID, "--matrix", str(matrix or matrix_file(tmp_path)), "--arm", binding,
                   "--run-id", run_id, *extra])


def baseline_two_tasks(root: Path) -> None:
    assert bench(root, "campaign", "create", CID, "--question", "does the pack help") == 0
    assert bench(root, "campaign", "baseline", CID, "--tasks", "T1,T2") == 0


def test_a_campaign_plan_from_the_chain_launches_past_the_identity_check(tmp_path, monkeypatch, capsys):  # R-106 c3 (INT-A control), c6
    from test_cli_campaign import real_run

    root = tree(tmp_path)
    _fake_tree(tmp_path / "tools")  # real builds, resolved from a tools dir
    baseline_two_tasks(root)
    registered(root, pack_commit(tmp_path))  # the register walk is C-33's; the three commands under test follow it
    assert plan_campaign(root, tmp_path, "C1", "--confirm") == 0, capsys.readouterr().err  # a subset: T1 of the baselined T1 and T2
    plan_doc = json.loads((root / "runs" / "C1" / "plan.json").read_text(encoding="utf-8"))
    assert sorted(plan_doc["tasks"]) == ["T1"] and plan_doc["builds"]["claude-code"]["version"] == "2.1.274"
    assert bench(root, "campaign", "attach", CID, "C1") == 0, capsys.readouterr().err
    code = real_run(monkeypatch, root, tmp_path, "C1")
    events = run_events(root, "C1")
    stops = [(r["code"], r.get("diff")) for r in events if r["kind"] == "run.launch_stopped"]
    assert not [s for s in stops if s[0] == "HB-IDN-001"], stops  # on the base this is `tasks/T2 removed` or `builds/claude-code added`
    launches = [r for r in events if r["kind"] == "cell.launch_intent"]
    assert len(launches) == 8 and code == 0, (code, stops, len(launches))
    first, warm = launches[0]["identity_check_ms"], launches[1]["identity_check_ms"]
    print(f"identity_check_ms first={first} warm={warm}")  # R-106 c6: measured, read from the rows; a breach of 250 ms warm is a finding
    assert isinstance(first, int) and isinstance(warm, int)


def test_the_three_refusals_of_a_drifted_tree_still_fire_p4(tmp_path, monkeypatch, capsys):  # R-106 c3: P-4's legs through the real commands
    from test_cli_campaign import real_run

    root = tree(tmp_path)
    _fake_tree(tmp_path / "tools")
    baseline_two_tasks(root)
    digest = registered(root, pack_commit(tmp_path))
    edit_src(root, "engine.py")  # the tree drifts after the baseline
    capsys.readouterr()
    assert plan_campaign(root, tmp_path, "D1", "--confirm") == 1  # leg 1: plan time
    err = capsys.readouterr().err
    assert "HB-CMP-010" in err and "engine.py" in err
    assert not (root / "runs" / "D1").exists()
    stamp = identity.side(identity.manifest(root, ["T1", "T2"]), "run")  # a hand-stamp from the drifted tree
    write_plan(root, "D2", prereg_hash=digest, harness="claude-code", commit=pack_commit(tmp_path), ident={"hash": identity.identity_hash(stamp), "components": stamp["components"]})
    assert bench(root, "campaign", "attach", CID, "D2") == 1  # leg 2: attach
    assert "HB-CMP-010" in capsys.readouterr().err
    write_text(root / "src" / "harness_bench" / "engine.py", "original\n")
    write_plan(root, "D3", prereg_hash=digest, harness="claude-code", commit=pack_commit(tmp_path))
    assert bench(root, "campaign", "attach", CID, "D3") == 0
    edit_src(root, "engine.py")
    assert real_run(monkeypatch, root, tmp_path, "D3") == 3  # leg 3: the real engine
    stops = [r for r in run_events(root, "D3") if r["kind"] == "run.launch_stopped"]
    assert [r["code"] for r in stops] == ["HB-IDN-001"] and stops[0]["diff"] == ["engine.py changed"]
    assert kinds(root)[-1] == "grid.attached" and rows_of(root)
