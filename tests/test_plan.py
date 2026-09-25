import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness_bench import cli, config, gitsafe, plan, profiles, tools, workspace
from harness_bench.errors import BenchError
from harness_bench.ledger import canonical

ROOT = Path(__file__).resolve().parents[1]


def test_wave1_matrix_parses_and_walking_skeleton_selects_it():
    matrix_path = ROOT / "bench" / "matrix.wave1.yaml"
    matrix = config.load_yaml(matrix_path)
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    problems = config.Problems()
    config.validate_matrix(matrix, bom, problems, str(matrix_path))
    assert problems.items == []
    assert matrix["schema"] == "bench-matrix/1"
    assert matrix["bom"]["subset"] == ["X1"]
    assert matrix["repetitions"] == 1 and matrix["packs"] == ["on", "off"]
    assert [(c["id"], c["harness"], c["model"]) for c in matrix["combos"]] == [
        ("copilot-sol", "copilot", "gpt-6-sol"),
        ("codex-sol", "codex", "gpt-6-sol"),
        ("cc-opus", "claude-code", "claude-opus-5-5"),
    ]
    assert len(plan.expand(matrix, bom)) == 6

    spec = importlib.util.spec_from_file_location("walking_skeleton_selection", ROOT / "tests" / "e2e" / "test_walking_skeleton.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    marker = next(mark for mark in module.test_the_walking_skeleton_runs_end_to_end.pytestmark if mark.name == "parametrize")
    assert marker.kwargs["ids"] == ["phase1", "wave1"]
    assert marker.args[1] == [("phase1", "bench/matrix.phase1.yaml"), ("wave1", "bench/matrix.wave1.yaml")]
    assert {mark.name for mark in module.pytestmark} == {"native", "credentials"}


def _inputs(subset):
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    m = config.load_yaml(ROOT / "bench" / "matrix.example.yaml")
    m["bom"]["subset"] = subset
    return m, bom


def test_full_grid_matches_proposal_run_count():
    # Proposal: 24 tasks x 4 combos x pack on/off x 3 reps = 576 runs. Fixture tasks are never in it.
    m, bom = _inputs("full")
    assert len(plan.expand(m, bom)) == 576


def test_smoke_grid_is_one_task_per_scenario():
    m, bom = _inputs("smoke")
    cells = plan.expand(m, bom)
    assert sorted({c.scenario for c in cells}) == [1, 2, 3, 4, 5, 6]
    assert len(cells) == 6 * 4 * 2 * 3


def test_cell_ids_are_unique():
    m, bom = _inputs("full")
    ids = [c.id for c in plan.expand(m, bom)]
    assert len(ids) == len(set(ids))


def test_combos_are_interleaved_innermost():
    m, bom = _inputs("smoke")
    cells = plan.expand(m, bom)
    n = len(m["combos"])
    assert [c.combo for c in cells[:n]] == [c["id"] for c in m["combos"]]
    assert len({(c.task, c.pack, c.rep) for c in cells[:n]}) == 1


def test_fixture_task_is_selectable_by_id_only():
    m, bom = _inputs(["X1"])
    cells = plan.expand(m, bom)
    assert {c.task for c in cells} == {"X1"}
    assert all(c.task != "X1" for c in plan.expand(*_inputs("full")))


# cell identity (ADR-0006) -------------------------------------------------------------------

def test_cell_id_is_a_deterministic_hash_of_its_ingredients():
    a = plan.Cell("X1", "v1", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "on", 1, 300)
    b = plan.Cell("X1", "v1", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "on", 1, 300)
    assert a.id == b.id and len(a.id) == 16
    for changed in (plan.Cell("X1", "v2", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "on", 1, 300),
                    plan.Cell("X1", "v1", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "off", 1, 300),
                    plan.Cell("X1", "v1", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "on", 2, 300)):
        assert changed.id != a.id


def test_task_version_hash_changes_with_any_task_file(tmp_path):
    task = tmp_path / "X9"
    shutil.copytree(ROOT / "tasks" / "X1", task)
    before = plan.task_version_hash(task)
    assert plan.task_version_hash(task) == before
    (task / "tests" / "extra.txt").write_text("x", encoding="utf-8")
    assert plan.task_version_hash(task) != before


# envelope, plan hash, confirmation (US-6) -----------------------------------------------------

def test_envelope_is_budget_sum_over_parallelism_plus_the_largest_budget():
    cells = [plan.Cell("T", "v", 5, f"c{i}", "codex", "m", "on", 1, s) for i, s in enumerate((300, 300, 600))]
    assert plan.envelope_seconds(cells, parallelism=2) == 600 + 600  # ceil(1200 / 2) + max(600)
    assert plan.envelope_seconds([], parallelism=2) == 0


def _phase1_plan(**over):
    m = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    builds = {"claude-code": {"version": "2.1.274", "sha256": "a" * 64}, "codex": {"version": "0.156.0", "sha256": "b" * 64}}
    pack = {"source": "../ai-forward", "commit": "c" * 40, "revision": 92}
    args = {"root": ROOT, "matrix": m, "bom": bom, "run_id": "r1", "builds": builds, "pack": pack, "parallelism": 2}
    args.update(over)
    return plan.build_plan(**args)


def test_phase1_plan_has_four_cells_and_every_recorded_field():
    p = _phase1_plan()
    assert len(p["cells"]) == 4
    assert {(c["combo"], c["pack"]) for c in p["cells"]} == {("cc-sonnet", "on"), ("cc-sonnet", "off"), ("codex-sol", "on"), ("codex-sol", "off")}
    for key in ("schema", "run_id", "plan_hash", "trace_id", "matrix_hash", "tasks", "builds", "pack", "parameters",
                "price_list_hash", "envelope_seconds"):
        assert key in p, key
    assert len(p["trace_id"]) == 32 and int(p["trace_id"], 16)
    assert p["parameters"]["parallelism"] == 2


def test_plan_records_each_profiles_shutdown_grace():  # PR-3
    p = _phase1_plan()
    assert {h: record["shutdown_grace_seconds"] for h, record in p["profiles"].items()} == {
        "claude-code": "10", "codex": "10"}


def test_stop_parameters_are_frozen_with_the_ruling_units():  # P-1
    p = _phase1_plan()
    assert p["parameters"]["decision_timeout"] == 1800
    assert p["parameters"]["spend_cap_tokens"] is None
    assert _phase1_plan(parameters={"decision_timeout": 120, "spend_cap_tokens": 1000})["parameters"]["spend_cap_tokens"] == 1000


def test_stop_parameters_refuse_non_positive_values():
    for parameters in ({"decision_timeout": 0}, {"decision_timeout": -1}, {"spend_cap_tokens": 0},
                       {"spend_cap_tokens": -1}, {"spend_cap_tokens": True}):
        with pytest.raises(BenchError) as error:
            _phase1_plan(parameters=parameters)
        assert error.value.code == "HB-USR-002"


def test_plan_freezes_the_builds_unrecorded_self_report_reason():  # R-47 condition 3, null path
    builds = {"claude-code": {"agent_version": None, "agent_version_reason": "ACP initialize requires a live handshake"},
              "codex": {"agent_version": None, "agent_version_reason": "ACP initialize requires a live handshake"}}
    p = _phase1_plan(builds=builds)
    assert p["builds"] == builds


def test_an_old_confirmed_plan_missing_a_parameter_is_refused(tmp_path):  # P-2
    p = _phase1_plan()
    p["parameters"].pop("git_timeout")
    p["plan_hash"] = plan.plan_hash(p)
    plan.confirm(tmp_path / "runs" / "old", p)
    with pytest.raises(BenchError) as error:
        plan.require_run_parameters(plan.load_confirmed(tmp_path / "runs" / "old"))
    assert error.value.code == "HB-USR-002"
    assert "git_timeout" in error.value.message


def test_row15_supports_parallelism_four_and_refuses_five():  # R-38 condition 2
    assert plan.PHASE1_MAX_PARALLELISM == 4
    assert _phase1_plan(parallelism=4)["parameters"]["parallelism"] == 4
    with pytest.raises(BenchError):
        _phase1_plan(parallelism=5)


def test_the_plan_freezes_each_task_prompt_verbatim_with_its_hash():  # US-10: the prompt the agent receives
    p = _phase1_plan()
    raw = (ROOT / "tasks" / "X1" / "prompt.md").read_bytes().decode("utf-8")
    assert p["tasks"]["X1"]["prompt"] == raw
    assert p["tasks"]["X1"]["prompt_sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_the_plan_freezes_each_task_model_map(tmp_path):  # seam S3: views read the run, not today's task.yaml (US-11)
    assert _phase1_plan()["tasks"]["X1"]["model_map"] is None  # X1 declares none
    root = tmp_path / "root"
    shutil.copytree(ROOT / "tasks" / "X1", root / "tasks" / "X1")
    shutil.copytree(ROOT / "bench", root / "bench")
    task_yaml = root / "tasks" / "X1" / "task.yaml"
    task_yaml.write_text(task_yaml.read_text(encoding="utf-8").replace("model_map: null", "model_map:\n  implement: gpt-6-sol"),
                         encoding="utf-8")
    assert _phase1_plan(root=root)["tasks"]["X1"]["model_map"] == {"implement": "gpt-6-sol"}


def test_the_plan_freezes_each_task_graders_list(tmp_path):  # seam S-1: the pass reads the run's list, not today's task.yaml
    assert _phase1_plan()["tasks"]["X1"]["graders"] == ["correctness", "cost"]  # X1's task.yaml, verbatim
    root = tmp_path / "root"
    shutil.copytree(ROOT / "tasks" / "X1", root / "tasks" / "X1")
    shutil.copytree(ROOT / "bench", root / "bench")
    task_yaml = root / "tasks" / "X1" / "task.yaml"
    task_yaml.write_text(task_yaml.read_text(encoding="utf-8").replace("  - cost\n", "  - cost\n  - process\n"), encoding="utf-8")
    assert _phase1_plan(root=root)["tasks"]["X1"]["graders"] == ["correctness", "cost", "process"]


def test_tree_hash_is_the_one_recipe_path_nul_lf_bytes_nul_in_sorted_path_order(tmp_path):  # seam S-2 (R-59 c1)
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "y.md").write_bytes(b"one\r\ntwo\n")
    (tmp_path / "a.yaml").write_bytes(b"k: v\n")
    expected = hashlib.sha256(b"a.yaml\0k: v\n\0" b"b/y.md\0one\ntwo\n\0").hexdigest()
    assert plan.tree_hash(tmp_path, [tmp_path / "b" / "y.md", tmp_path / "a.yaml"]) == expected  # any order in, sorted out
    assert plan.tree_hash(tmp_path, []) == hashlib.sha256(b"").hexdigest()


def test_task_version_hash_is_tree_hash_over_every_task_file(monkeypatch):  # seam S-2: one recipe, one definition
    task = ROOT / "tasks" / "X1"
    files = sorted(p for p in task.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    assert plan.task_version_hash(task) == plan.tree_hash(task, files)
    seen = []
    monkeypatch.setattr(plan, "tree_hash", lambda base, fs: seen.append((base, sorted(fs))) or "spy")
    assert (plan.task_version_hash(task), seen) == ("spy", [(task, files)])


def test_cmd_plan_refuses_a_changed_frozen_task_before_building_a_plan(monkeypatch, tmp_path, capsys):  # seam S-3 (R-59 c5)
    root = tmp_path / "root"
    shutil.copytree(ROOT / "bench", root / "bench")
    shutil.copytree(ROOT / "tasks" / "X1", root / "tasks" / "X1")
    (root / "bench" / "task-freeze.yaml").write_text(f"schema: bench-task-freeze/1\ntasks: {{X1: '{'0' * 64}'}}\n", encoding="utf-8")
    actual = plan.task_version_hash(root / "tasks" / "X1")
    monkeypatch.setattr(cli.tools, "resolve", lambda path: {})
    monkeypatch.setattr(cli, "_pack", lambda *args: {"source": "pack", "commit": "c" * 40, "revision": 1})
    monkeypatch.setattr(cli.plan, "build_plan", lambda *a, **k: pytest.fail("a plan was built over a changed frozen task"))
    args = SimpleNamespace(root=str(root), matrix=str(root / "bench" / "matrix.phase1.yaml"), tools_dir=str(tmp_path / "t"),
                           cells_root=str(tmp_path / "c"), pack_source=str(tmp_path / "p"), run_id="p", parallelism=2,
                           json=False, confirm=False, decision_timeout_minutes=30, spend_cap_tokens=None)
    assert cli.cmd_plan(args) == cli.INVALID
    assert capsys.readouterr().err == f"x tasks/X1 changed while frozen (R-59 c5): {actual} != {'0' * 64}\n"


def test_the_plan_records_each_harness_profile_it_uses():  # grading and views read the run, not today's files (US-26)
    p = _phase1_plan()
    assert p["profiles"] == {
        "claude-code": {"profile_hash": plan.file_hash(ROOT / "bench" / "profiles" / "claude-code.yaml"),
                        "vendor": "anthropic", "usage_source": "acp_turn", "auxiliary_models": ["claude-haiku-4-5"],
                            "record_glob": "projects/**/{session_id}.jsonl", "shutdown_grace_seconds": "10",
                        "subagent_glob": "projects/**/{session_id}/subagents/agent-*.jsonl"},
        "codex": {"profile_hash": plan.file_hash(ROOT / "bench" / "profiles" / "codex.yaml"),
                  "vendor": "openai", "usage_source": "native_record", "auxiliary_models": [],
                      "record_glob": "sessions/**/rollout-*-{session_id}.jsonl", "shutdown_grace_seconds": "10",
                  "subagent_glob": ""},
    }


def test_plan_hash_covers_every_field():
    p = _phase1_plan()
    assert plan.plan_hash(p) == p["plan_hash"]
    tampered = json.loads(json.dumps(p))
    tampered["cells"][0]["model"] = "other"
    assert plan.plan_hash(tampered) != p["plan_hash"]


def test_confirm_freezes_the_plan_and_refuses_a_second_write(tmp_path):
    p = _phase1_plan()
    path = plan.confirm(tmp_path / "runs" / "r1", p)
    assert json.loads(path.read_text(encoding="utf-8"))["plan_hash"] == p["plan_hash"]
    with pytest.raises(BenchError) as e:
        plan.confirm(tmp_path / "runs" / "r1", p)
    assert e.value.code == "HB-USR-002"
    assert plan.load_confirmed(tmp_path / "runs" / "r1")["plan_hash"] == p["plan_hash"]


def test_load_confirmed_detects_an_edited_plan(tmp_path):
    p = _phase1_plan()
    path = plan.confirm(tmp_path / "runs" / "r1", p)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["parameters"]["parallelism"] = 9
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BenchError) as e:
        plan.load_confirmed(tmp_path / "runs" / "r1")
    assert e.value.code == "HB-LED-002"


def test_load_confirmed_without_a_plan_is_unknown_run(tmp_path):
    with pytest.raises(BenchError) as e:
        plan.load_confirmed(tmp_path / "runs" / "missing")
    assert e.value.code == "HB-USR-001"


def test_parallelism_above_the_phase1_cap_is_refused():
    with pytest.raises(BenchError):
        _phase1_plan(parallelism=5)


def test_a_combo_id_that_breaks_the_status_label_regex_is_refused_at_plan_time():  # T4-5
    m = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    m["combos"][0]["id"] = "cc sonnet"  # a space is not in the status label pattern
    with pytest.raises(BenchError) as e:
        _phase1_plan(matrix=m)
    assert e.value.code == "HB-USR-002"


def test_instruction_list_uses_the_given_fake_exe_workspace_and_environment(monkeypatch, tmp_path):
    calls = []
    fake_exe = tmp_path / "fake-copilot.exe"
    ws = tmp_path / "workspace"
    env = {"COPILOT_HOME": str(tmp_path / "home")}

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, timed_out=False, stdout='[{"label":"AGENTS.md"}]', stderr="")

    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=fake_run), raising=False)
    assert plan.instruction_list(fake_exe, ws, env) == [{"label": "AGENTS.md"}]
    assert calls == [([str(fake_exe), "instruction", "list", "--json"],
                      {"cwd": str(ws), "env": env, "timeout": 120})]


def test_instruction_list_refuses_a_non_list_result_from_the_fake_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: SimpleNamespace(
        returncode=0, timed_out=False, stdout='{"instructions":[]}', stderr="")), raising=False)
    with pytest.raises(BenchError) as e:
        plan.instruction_list(tmp_path / "fake-copilot.exe", tmp_path, {})
    assert e.value.code == "HB-PRE-008"


def test_instruction_list_reports_nonzero_exit(monkeypatch, tmp_path):
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: SimpleNamespace(
        returncode=7, timed_out=False, stdout="", stderr="instruction error")), raising=False)
    with pytest.raises(BenchError) as error:
        plan.instruction_list(tmp_path / "copilot.exe", tmp_path, {})
    assert error.value.code == "HB-PRE-008"
    assert "instruction error" in str(error.value)


def test_instruction_list_reports_invalid_json(monkeypatch, tmp_path):
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: SimpleNamespace(
        returncode=0, timed_out=False, stdout="not json", stderr="")), raising=False)
    with pytest.raises(BenchError) as error:
        plan.instruction_list(tmp_path / "copilot.exe", tmp_path, {})
    assert error.value.code == "HB-PRE-008"
    assert "did not return JSON" in str(error.value)


def test_instruction_list_reports_timeout(monkeypatch, tmp_path):
    result = SimpleNamespace(returncode=1, timed_out=True, stdout="", stderr="")
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: result), raising=False)
    with pytest.raises(BenchError) as error:
        plan.instruction_list(tmp_path / "copilot.exe", tmp_path, {})
    assert error.value.code == "HB-PRE-008"
    assert "timed out after 120 s" in str(error.value)


def test_instruction_list_reports_truncated_stdout(monkeypatch, tmp_path):
    result = SimpleNamespace(returncode=0, timed_out=False, stdout='[{"label":', stderr="")
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: result), raising=False)
    with pytest.raises(BenchError) as error:
        plan.instruction_list(tmp_path / "copilot.exe", tmp_path, {})
    assert error.value.code == "HB-PRE-008"
    assert "truncated" in str(error.value)


def _fake_copilot_plan(monkeypatch, tmp_path, listing):
    from harness_bench import workspace

    m = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    m["combos"] = [{"id": "copilot-sol", "harness": "copilot", "model": "gpt-6-sol"}]
    m["repetitions"] = 2
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    build = SimpleNamespace(exe=tmp_path / "fake-copilot.exe")
    resolved_dirs = []

    def resolve(tools_dir):
        resolved_dirs.append(tools_dir)
        return {"copilot": build}

    monkeypatch.setattr(plan, "tools", SimpleNamespace(resolve=resolve, check_build=lambda *_: None), raising=False)
    monkeypatch.setattr(plan, "profile_record", lambda *_: {"profile_hash": "fake"})
    monkeypatch.setattr(plan.profiles, "load", lambda *_: SimpleNamespace(cell_env=lambda base, home, build, model, traceparent: {
        "COPILOT_HOME": str(home)}))
    monkeypatch.setattr(workspace, "check_cells_root", lambda *_: None)
    monkeypatch.setattr(workspace, "task_source", lambda *_: tmp_path / "source")

    def copy(_source, dest):
        dest.mkdir(parents=True)
        return dest

    monkeypatch.setattr(workspace, "cell_working_copy", copy)
    monkeypatch.setattr(workspace, "pack_checkout", lambda *_: tmp_path / "pack")
    def install_pack(_pack_dir, ws, **_kwargs):
        (ws / "AGENTS.md").write_text("installed", encoding="utf-8")
        return []

    monkeypatch.setattr(workspace, "install_pack", install_pack)
    calls = []

    def fake_list(exe, ws, env):
        calls.append((exe, ws, env))
        return listing(ws)

    monkeypatch.setattr(plan, "instruction_list", fake_list, raising=False)
    args = {"root": ROOT, "matrix": m, "bom": bom, "run_id": "copilot-plan", "builds": {"copilot": {
        "version": "1.0.89-1", "sha256": "a" * 64}}, "pack": {"source": str(tmp_path / "pack-source"),
        "commit": "c" * 40, "revision": 95}}
    args["tools_dir"] = tmp_path / "custom-tools"
    args["cells_root"] = tmp_path / "cells-root"
    return args, calls, resolved_dirs


def test_copilot_plan_lists_once_per_task_pack_build_and_freezes_counts(monkeypatch, tmp_path):
    args, calls, resolved_dirs = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [
        {"label": "AGENTS.md"}, {"label": "CLAUDE.md"}] if (ws / "AGENTS.md").is_file() else [])
    p = plan.build_plan(**args)
    assert len(calls) == 2
    assert resolved_dirs == [args["tools_dir"]]
    assert all(ws.is_relative_to(args["cells_root"]) for _, ws, _ in calls)
    assert not list(args["cells_root"].glob("bench-plan-*"))
    assert {(c["pack"], c["instruction_count"]) for c in p["cells"]} == {("off", 0), ("on", 2)}
    assert len(p["instruction_lists"]) == 2
    assert all(c["build_sha256"] == "a" * 64 for c in p["instruction_lists"])
    assert {(c["pack"], c["count"]) for c in p["instruction_lists"]} == {("off", 0), ("on", 2)}
    assert next(c for c in p["instruction_lists"] if c["pack"] == "off")["instructions"] == []


def test_copilot_plan_projects_instructions_to_string_identity_fields_and_keeps_canonical(monkeypatch, tmp_path):
    """A boolean field in the exe's instruction rows (defaultDisabled) must not break the ledger's
    canonical encoder (no bools) once the plan is frozen (defect: slice-5 worker)."""
    raw = [{"id": 3, "label": "AGENTS.md", "location": "repository", "type": True,
            "sourcePath": "AGENTS.md", "defaultDisabled": False}]
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: raw if (ws / "AGENTS.md").is_file() else [])
    p = plan.build_plan(**args)
    on_list = next(c for c in p["instruction_lists"] if c["pack"] == "on")
    assert on_list["count"] == 1
    assert on_list["instructions"] == [{"label": "AGENTS.md", "location": "repository", "sourcePath": "AGENTS.md"}]
    canonical(p)  # ledger canonical forbids bool; build_plan already calls plan_hash internally


def test_copilot_plan_refuses_a_nonempty_pack_off_instruction_list(monkeypatch, tmp_path):
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [{"label": "leaked"}])
    with pytest.raises(BenchError) as e:
        plan.build_plan(**args)
    assert e.value.code == "HB-PRE-008"


def test_copilot_plan_installs_pack_before_listing_instructions(monkeypatch, tmp_path):
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [
        {"label": "AGENTS.md"}] if (ws / "AGENTS.md").is_file() else [])
    p = plan.build_plan(**args)
    assert next(item for item in p["instruction_lists"] if item["pack"] == "on")["count"] == 1


def test_copilot_plan_removes_probe_after_instruction_error(monkeypatch, tmp_path):
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [{"label": "leaked"}])
    with pytest.raises(BenchError, match="HB-PRE-008"):
        plan.build_plan(**args)
    assert not list(args["cells_root"].glob("bench-plan-*"))


def test_copilot_plan_logs_failed_cleanup_without_masking_instruction_error(monkeypatch, tmp_path, caplog):
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [{"label": "leaked"}])
    original_rmtree = plan.shutil.rmtree

    def fail_probe_cleanup(path, **kwargs):
        if path.name.startswith("bench-plan-"):
            raise OSError("locked probe")
        return original_rmtree(path, **kwargs)

    monkeypatch.setattr(plan.shutil, "rmtree", fail_probe_cleanup)
    with pytest.raises(BenchError, match="HB-PRE-008"):
        plan.build_plan(**args)
    leftover = next(args["cells_root"].glob("bench-plan-*"))
    assert str(leftover) in caplog.text
    monkeypatch.setattr(plan.shutil, "rmtree", original_rmtree)
    original_rmtree(leftover)


def test_cmd_plan_passes_configured_tools_and_cells_roots_to_probe(monkeypatch, tmp_path):
    matrix = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    real = config.load_yaml  # bench/task-freeze.yaml is read for real (seam S-3)
    monkeypatch.setattr(cli.config, "load_yaml", lambda path: {"bom.yaml": bom, "matrix.phase1.yaml": matrix}.get(Path(path).name)
                        or real(path))
    monkeypatch.setattr(cli.config, "validate_matrix", lambda *args: None)
    monkeypatch.setattr(cli.tools, "resolve", lambda path: {})
    monkeypatch.setattr(cli, "_pack", lambda *args: {"source": "pack", "commit": "c" * 40, "revision": 1})
    received = {}

    def fake_build_plan(*args, **kwargs):
        received.update(kwargs)
        return {"cells": [], "builds": {}, "pack": {"revision": 1, "commit": "c" * 40},
                "parameters": {"parallelism": 2, **kwargs["parameters"]}, "envelope_seconds": 0, "price_list_hash": ""}

    monkeypatch.setattr(cli.plan, "build_plan", fake_build_plan)
    args = SimpleNamespace(root=str(ROOT), matrix=str(ROOT / "bench" / "matrix.phase1.yaml"),
                           tools_dir=str(tmp_path / "custom-tools"), cells_root=str(tmp_path / "cells-root"),
                           pack_source=str(tmp_path / "pack"), run_id="p", parallelism=2, json=False, confirm=False,
                           decision_timeout_minutes=30, spend_cap_tokens=None)
    assert cli.cmd_plan(args) == 0
    assert received["tools_dir"] == Path(args.tools_dir)
    assert received["cells_root"] == Path(args.cells_root)


@pytest.mark.native
def test_pinned_copilot_instruction_list_repeats_for_both_real_working_copies(base):
    tools_dir = ROOT / ".tools" / "harness"
    if not tools_dir.exists():  # a coordination worktree shares the installed build in the primary checkout
        tools_dir = ROOT.parent / "x-harness-x-model-bench" / ".tools" / "harness"
    exe = tools.resolve(tools_dir)["copilot"].exe
    pack_source = ROOT.parent / "ai-forward"
    commit = gitsafe.git(["rev-parse", "HEAD"], cwd=pack_source, timeout=60).stdout.strip()
    source = workspace.task_source(ROOT / "tasks" / "X1", plan.task_version_hash(ROOT / "tasks" / "X1"), base / "sources")
    results = {}
    for arm in ("off", "on"):
        ws = workspace.cell_working_copy(source, base / "cells" / arm / "ws")
        if arm == "on":
            pack_dir = workspace.pack_checkout(pack_source, commit, base / "pack")
            workspace.install_pack(pack_dir, ws, project="X1", timeout=300)
        home = base / "homes" / arm
        home.mkdir(parents=True)
        env = profiles.load(ROOT, "copilot").cell_env(dict(os.environ), home, tools.resolve(tools_dir)["copilot"],
                                                       "gpt-6-sol", "")
        results[arm] = [plan.instruction_list(exe, ws, env) for _ in range(2)]
    assert results["off"] == [[], []]
    assert results["on"][0] == results["on"][1]
    assert any(row.get("sourcePath") == "AGENTS.md" for row in results["on"][0])
