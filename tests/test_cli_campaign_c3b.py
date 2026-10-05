"""X-C3b proof, the read and wiring half: `plan --campaign`, the launch recheck over a chain-stamped plan (R-106 c3), the stop reason in
`bench status`, plan-kind handling, the after-grading hook, the report binding and the campaign status document.

Fixtures are the ones of `test_cli_campaign.py` (the one home of the helpers). Expected values are typed here or read from rows, never
computed with the function under test (RV-TA 1).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from test_campaign_register import stubs  # noqa: F401  (the pilot-gate stubs fixture)
from test_cli import _pack_repo
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
    capsys.readouterr()
    assert bench(root, "status", "D3") == 0  # item 34: the real stopped run shows why it stopped
    shown = capsys.readouterr().out
    assert "engine identity drift" in shown and "engine.py changed" in shown
    assert kinds(root)[-1] == "grid.attached" and rows_of(root)


# --- P-1, P-2, P-3b: `bench plan --campaign` ---------------------------------------------------------------------------------


def pilot_matrix(tmp_path):
    return matrix_file(tmp_path, ring={"tag": "pilot"}, arms=[{"id": "off"}, {"id": "treat"}])


def test_plan_with_campaign_stamps_the_chains_effective_run_side_p1(tmp_path, capsys):
    from test_campaign import fix_argv
    from test_cli_campaign import commit_all

    root = tree(tmp_path)
    baseline_two_tasks(root)
    before = json.loads(next((root / "bench" / "campaigns" / CID / "identity").glob("*.json")).read_text(encoding="utf-8"))["components"]
    edit_src(root, "engine.py", "fixed\n")
    commit_all(root, "fix engine")
    assert bench(root, *fix_argv(root, "src/harness_bench/engine.py")) == 0
    registered(root, pack_commit(tmp_path))
    _fake_tree(tmp_path / "tools")
    assert plan_campaign(root, tmp_path, "S1", "--confirm") == 0, capsys.readouterr().err
    block = json.loads((root / "runs" / "S1" / "plan.json").read_text(encoding="utf-8"))["campaign"]
    engine_key = "src/harness_bench/engine.py"
    assert block["campaign_id"] == CID and block["prereg_hash"] is not None
    assert block["identity"]["components"][engine_key] != before[engine_key]  # the recorded fix moved the stamp off the baseline
    assert {"tasks/T1", "tasks/T2"} <= set(block["identity"]["components"])  # a subset plan (T1) still carries every baselined task
    run_side = identity.side(identity.manifest(root, ["T1", "T2"]), "run")
    assert block["identity"] == {"hash": identity.identity_hash(run_side), "components": run_side["components"]}


def test_plan_refuses_a_drifted_tree_naming_the_component_p2(tmp_path, capsys):
    root = tree(tmp_path)
    baseline_two_tasks(root)
    registered(root, pack_commit(tmp_path))
    _fake_tree(tmp_path / "tools")
    edit_src(root, "engine.py")  # a run-side file: a grade-side edit does not stop a launch, so it is not drift here
    capsys.readouterr()
    assert plan_campaign(root, tmp_path, "S2", "--confirm") == 1
    err = capsys.readouterr().err
    assert err.startswith("HB-CMP-010") and "engine.py" in err
    assert not (root / "runs" / "S2").exists()


def test_plan_campaign_is_refused_for_a_pack_regression_ring_and_the_wrong_state(tmp_path, capsys):
    root = tree(tmp_path)
    baseline_two_tasks(root)
    _fake_tree(tmp_path / "tools")
    capsys.readouterr()
    assert plan_campaign(root, tmp_path, "S3") == 1  # a comparison ring needs `registered`; the campaign is only baselined
    assert "HB-CMP-002" in capsys.readouterr().err
    regression = matrix_file(tmp_path, ring={"tag": "pack-regression"})
    assert plan_campaign(root, tmp_path, "S4", matrix=regression) == 1
    err = capsys.readouterr().err
    assert "HB-CMP-010" in err and "pack-regression" in err


def test_bench_run_accepts_a_pilot_plan_via_ring_run_attached_p3b(tmp_path, monkeypatch, capsys):
    from test_cli_campaign import real_run

    root = tree(tmp_path)
    baseline_two_tasks(root)
    _fake_tree(tmp_path / "tools")
    assert plan_campaign(root, tmp_path, "PL", "--confirm", matrix=pilot_matrix(tmp_path)) == 0, capsys.readouterr().err
    assert json.loads((root / "runs" / "PL" / "plan.json").read_text(encoding="utf-8"))["campaign"]["prereg_hash"] is None
    assert bench(root, "campaign", "pilot", "attach", CID, "PL") == 0, capsys.readouterr().err
    real_run(monkeypatch, root, tmp_path, "PL")
    events = run_events(root, "PL")
    assert any(r["kind"] == "cell.launch_intent" for r in events), [(r["kind"], r.get("code")) for r in events]  # the launcher is reached


# --- plan kind handling (SR-E3 1; items 29 and 43), through the real `cli.main` -----------------------------------------------------


def test_bench_run_refuses_a_discrimination_plan_with_hb_pln_004_naming_the_kind(tmp_path, capsys):
    root = tree(tmp_path)
    write_plan(root, "K1", kind="discrimination", campaign_block=False, prereg_hash=None)
    capsys.readouterr()
    assert bench(root, "run", "K1") == 1
    err = capsys.readouterr().err
    assert err.startswith("HB-PLN-004") and "discrimination" in err
    assert not (root / "runs" / "K1" / "events").exists()  # refused before the engine started


def test_bench_status_labels_a_discrimination_run_and_does_not_refuse(tmp_path, capsys):
    root = tree(tmp_path)
    write_plan(root, "K1", kind="discrimination", campaign_block=False, prereg_hash=None)
    capsys.readouterr()
    assert bench(root, "status", "K1") == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "kind: discrimination"
    assert bench(root, "status", "K1", "--json") == 0
    assert json.loads(capsys.readouterr().out)["run_id"] == "K1"  # bench-status/1 gets no new field and no label


def test_bench_report_of_a_discrimination_run_is_still_hb_pln_004(tmp_path, capsys):
    root = tree(tmp_path)
    write_plan(root, "K1", kind="discrimination", campaign_block=False, prereg_hash=None)
    capsys.readouterr()
    assert bench(root, "report", "K1") == 1
    assert capsys.readouterr().err.startswith("HB-PLN-004")


def test_a_measurement_run_gets_no_kind_label(tmp_path, capsys):
    root = tree(tmp_path)
    write_plan(root, "K2", campaign_block=False, prereg_hash=None)
    capsys.readouterr()
    assert bench(root, "status", "K2") == 0
    assert not capsys.readouterr().out.startswith("kind:")


# --- L-10: the reads take no lock, probe nothing and write nothing ---------------------------------------------------------------


def test_status_verify_the_register_preview_and_plan_campaign_take_no_lock_l10(tmp_path, monkeypatch, capsys, stubs):  # noqa: F811
    from test_campaign_register import ready, stmt
    from test_cli_campaign import snapshot

    from harness_bench import oslock

    root = tree(tmp_path)
    ready(root, "admitted")
    path, _ = stmt(root)
    _fake_tree(tmp_path / "tools")
    preview = ["campaign", "register", CID, "--prereg", str(path)]
    before = snapshot(root)

    def never(*a, **k):
        raise AssertionError("a read took a lock")

    monkeypatch.setattr(oslock.RunLock, "acquire", never)
    for argv in (["campaign", "status", CID], ["campaign", "verify", CID], preview):
        capsys.readouterr()
        assert bench(root, *argv) == 0, (argv, capsys.readouterr().err)
    assert snapshot(root) == before
    assert plan_campaign(root, tmp_path, "L1", matrix=pilot_matrix(tmp_path)) == 0, capsys.readouterr().err  # not confirmed: nothing written
    assert not (root / "runs" / "L1").exists()


# --- the `bench report` binding to X-H2's CampaignInput (swap points 1-4) --------------------------------------------------------


POWER_BODY = {"schema": "bench-power-inputs/1", "alpha": "0.05", "power": "0.8", "correction": {"method": "bonferroni", "m": 2}, "pairing_unit": "unpaired",
              "slots": 2, "harnesses": ["codex"], "comparisons": [["off", "treat"]], "mean_wall_per_cell_s": 600, "mean_tokens_per_cell": 100000,
              "properties": {"security": {"mde": "0.3", "tasks": ["X1"]}}}
PREREG_BODY = {"schema": "bench-prereg/1", "question": "does the pack help", "arms": {"treat": {"commit": "f" * 40, "revision": "r1"}},
               "mde": {"security": "0.3"}, "alpha": "0.05", "power": "0.8", "correction": {"method": "bonferroni", "m": 2},
               "pairing_unit": "unpaired", "min_pairs": 3}


def graded_run(tmp_path, *, campaign_rows: bool, power: bool = True) -> tuple[Path, Path]:
    """A graded archived run (real grading pass) whose plan carries a campaign block, over a hand-built ledger."""
    from archived_runs import GOOD, make_root, make_run
    from test_cli_campaign import IDENT, defaults, put, raw_rows

    from harness_bench import plan as plan_mod
    from harness_bench.grade import runner

    root = make_root(tmp_path)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    doc = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    if campaign_rows:
        prereg = put(root, PREREG_BODY, "prereg")
        rows = [("campaign.created", {}), ("baseline.recorded", {"identity_hash": put(root, IDENT, "identity")}), ("pilot.passed", {})]
        if power:
            rows.append(("power.recorded", {"role": "final", "input_hash": put(root, POWER_BODY, "power")}))
        rows += [("registered", {"prereg_hash": prereg}), ("grid.attached", {"run_id": "r1", "plan_hash": "x" * 64})]
        raw_rows(root, [(kind, {**defaults(kind), **fields}) for kind, fields in rows])
        doc["campaign"] = {"campaign_id": CID, "prereg_hash": prereg, "identity": {"hash": "h" * 64, "components": {}}}
        doc["plan_hash"] = plan_mod.plan_hash(doc)
        (run_dir / "plan.json").write_text(json.dumps(doc), encoding="utf-8")
    return root, run_dir


def report(root, tmp_path, monkeypatch, capsys):
    from test_cli_campaign import cli_rc

    from harness_bench import cli

    seen = {}
    real = cli.html.write

    def spy(*a, **k):
        seen.update(k)
        return real(*a, **k)

    monkeypatch.setattr(cli.html, "write", spy)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "fake-home"))
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    capsys.readouterr()
    rc = cli_rc(["--root", str(root), "--runs", str(tmp_path / "runs"), "report", "r1"])
    return rc, seen, capsys.readouterr()


def test_a_campaign_runs_report_binds_the_campaign_and_renders_section_3(tmp_path, monkeypatch, capsys):
    from decimal import Decimal

    root, run_dir = graded_run(tmp_path, campaign_rows=True)
    rc, seen, out = report(root, tmp_path, monkeypatch, capsys)
    assert rc == 0, out.err
    bound = seen.get("campaign_obj")
    assert bound is not None, "html.write received no campaign_obj"
    assert bound.prereg == PREREG_BODY and bound.power_inputs == POWER_BODY and bound.state.state == "measuring"
    assert set(bound.expected_na) == {"X1"} and callable(bound.read_disagreements)  # readiness.expected_na, not the fixture constant
    assert bound.power_result and all(type(v).__name__ == "PowerResult" for v in bound.power_result.values())
    assert Decimal(str(bound.prereg["mde"]["security"])) == Decimal("0.3")
    html_text = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "does the pack help" in html_text and "security 0.3" in html_text  # section 3 header: the registered mde


def test_a_non_campaign_runs_report_binds_nothing(tmp_path, monkeypatch, capsys):
    root, _ = graded_run(tmp_path, campaign_rows=False)
    rc, seen, out = report(root, tmp_path, monkeypatch, capsys)
    assert rc == 0, out.err
    assert seen.get("campaign_obj") is None


def test_a_campaign_run_with_no_power_inputs_binds_nothing_and_says_so(tmp_path, monkeypatch, capsys):
    root, _ = graded_run(tmp_path, campaign_rows=True, power=False)
    rc, seen, out = report(root, tmp_path, monkeypatch, capsys)
    assert rc == 0, out.err
    assert seen.get("campaign_obj") is None
    assert "campaign section: no power inputs recorded (run bench campaign power)." in out.out


def test_the_power_inputs_decimal_strings_reach_analyse_as_decimal_seam_type(tmp_path, monkeypatch, capsys):
    from decimal import Decimal

    from harness_bench import power

    root, _ = graded_run(tmp_path, campaign_rows=True)
    got = []
    real = power.analyse
    monkeypatch.setattr(power, "analyse", lambda inputs: got.append(inputs) or real(inputs))
    rc, _, out = report(root, tmp_path, monkeypatch, capsys)
    assert rc == 0, out.err
    assert got and isinstance(got[0]["alpha"], Decimal) and isinstance(got[0]["properties"]["security"]["mde"], Decimal)
