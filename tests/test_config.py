from pathlib import Path

import yaml

from harness_bench import config

ROOT = Path(__file__).resolve().parents[1]


def test_repo_inputs_are_valid():
    # D1 vendors ai-de's pinned tree byte-for-byte (R-42); a parallel track is removing the
    # operator's hardcoded profile path from its non-vendored files. Until that lands, D1 is
    # the one expected exception to the new profile-path check (W2-VALIDATE); every other task,
    # and every other kind of D1 problem, must still be clean.
    unexpected = [i for i in config.validate_repo(ROOT) if not (i.startswith("tasks/D1:") and "user-profile path" in i)]
    assert unexpected == []


def test_every_metric_grader_has_a_module():
    graders = config.grader_modules(ROOT)
    metrics = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    owners = {m["grader"] for a in metrics["areas"].values() for m in a["metrics"]}
    assert owners <= graders


def _write_task(root: Path, tid: str, **overrides) -> Path:
    t = config.load_yaml(ROOT / "tasks" / "_template" / "task.yaml")
    t.update({"id": tid, **overrides})
    d = root / tid
    d.mkdir()
    (d / "task.yaml").write_text(yaml.safe_dump(t), encoding="utf-8")
    return d


def test_ready_task_without_oracle_or_pinned_source_is_rejected(tmp_path):
    d = _write_task(tmp_path, "X0", status="ready")
    (d / "prompt.md").write_text("do it", encoding="utf-8")
    (d / "tests").mkdir()
    (d / "tests" / "README.md").write_text("placeholder", encoding="utf-8")
    p = config.Problems()
    entry = {"id": "X0", "scenario": 5, "budget_minutes": 45}
    config.validate_task(d, entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    msgs = " ".join(p.items)
    assert "hidden tests or an oracle" in msgs
    assert "workspace/" in msgs


def test_budget_above_coord_runner_deadline_is_rejected():
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    bom["tasks"][0]["budget_minutes"] = 61
    p = config.Problems()
    config.validate_bom(bom, p)
    assert any("budget_minutes" in i for i in p.items)


def test_formal_task_without_tool_or_formal_grader_is_rejected(tmp_path):
    d = _write_task(tmp_path, "X7", scenario=7, formal=None, graders=["cost"])
    p = config.Problems()
    entry = {"id": "X7", "scenario": 7, "budget_minutes": 45}
    config.validate_task(d, entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    msgs = " ".join(p.items)
    assert "formal.tool" in msgs
    assert "formal grader" in msgs


def test_scenario_7_is_optional_in_smoke_but_at_most_one():
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    p = config.Problems()
    config.validate_bom(bom, p)
    assert p.items == []
    for t in bom["tasks"]:
        if t["scenario"] == 7:
            t["smoke"] = True
    config.validate_bom(bom, p)
    assert any("at most one task for scenario 7" in i for i in p.items)


def test_unquoted_on_off_packs_are_rejected():
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    m = yaml.safe_load("schema: bench-matrix/1\nrepetitions: 1\npacks: [on, off]\n"
                       "bom: {subset: smoke}\ncombos: [{id: a, harness: codex, model: m}]\n")
    p = config.Problems()
    config.validate_matrix(m, bom, p, "matrix")
    assert any("quote them" in i for i in p.items)


def test_unpinned_model_is_rejected():
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    m = config.load_yaml(ROOT / "bench" / "matrix.example.yaml")
    m["combos"][0]["model"] = "auto"
    p = config.Problems()
    config.validate_matrix(m, bom, p, "matrix")
    assert any("pinned" in i for i in p.items)


def _ready_task(tmp_path: Path, tid: str, **overrides) -> Path:
    """A ready task with the minimum content for the ready checks unrelated to R-42/US-2 to pass,
    so a test's own assertion is the only thing that can fail it."""
    d = _write_task(tmp_path, tid, status="ready", **overrides)
    (d / "prompt.md").write_text("do it", encoding="utf-8")
    (d / "tests").mkdir()
    (d / "tests" / "test_x.py").write_text("def test_x(): assert True", encoding="utf-8")
    (d / "workspace").mkdir()
    (d / "workspace" / "README.md").write_text("base", encoding="utf-8")
    return d


def test_ready_task_with_pack_marker_in_workspace_is_rejected(tmp_path):  # R-42 condition 2
    d = _ready_task(tmp_path, "X2", scenario=5)
    (d / "workspace" / "NOTES.md").write_text("See the AI-Forward Pack for guidance.", encoding="utf-8")
    p = config.Problems()
    entry = {"id": "X2", "scenario": 5, "budget_minutes": 45}
    config.validate_task(d, entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    assert "tasks/X2: workspace/NOTES.md contains pack material (bench/pack-markers.txt)" in p.items


def test_ready_task_with_generated_folder_in_workspace_is_rejected(tmp_path):  # R-42 condition 4
    d = _ready_task(tmp_path, "X3", scenario=5)
    (d / "workspace" / "obj").mkdir()
    (d / "workspace" / "obj" / "Debug.cache").write_text("generated", encoding="utf-8")
    p = config.Problems()
    entry = {"id": "X3", "scenario": 5, "budget_minutes": 45}
    config.validate_task(d, entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    assert "tasks/X3: workspace/obj/ is a generated or cache folder and must not be vendored" in p.items


def test_ready_scenario1_task_without_clarifications_is_rejected(tmp_path):  # US-2
    d = _ready_task(tmp_path, "X1", scenario=1, scripted_user=True)
    p = config.Problems()
    entry = {"id": "X1", "scenario": 1, "budget_minutes": 45}
    config.validate_task(d, entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    assert "tasks/X1: status ready requires oracle/clarifications.yaml for scenario 1" in p.items


def test_task_folder_with_operator_profile_path_is_rejected(tmp_path):
    d = _write_task(tmp_path, "X4", status="draft", scenario=5)
    (d / "prompt.md").write_text("line one\n" r"Run from C:\Users\malla\projects\bench" "\n", encoding="utf-8")
    p = config.Problems()
    entry = {"id": "X4", "scenario": 5, "budget_minutes": 45}
    config.validate_task(d, entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    assert "tasks/X4: prompt.md:2 hardcodes an absolute user-profile path" in p.items


def test_task_folder_with_placeholder_home_vars_is_not_rejected(tmp_path):
    d = _write_task(tmp_path, "X5", status="draft", scenario=5)
    (d / "prompt.md").write_text("use %USERPROFILE%\\bench or $HOME/bench\n", encoding="utf-8")
    p = config.Problems()
    entry = {"id": "X5", "scenario": 5, "budget_minutes": 45}
    config.validate_task(d, entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    assert not any("user-profile path" in i for i in p.items)


def test_vendored_workspace_content_is_exempt_from_the_profile_path_scan_but_oracle_is_not(tmp_path):
    # R-42 condition 3: a workspace file pinned in source.vendored_paths must match the upstream
    # archive byte for byte, so the profile-path scan must not force an edit there. "oracle" is
    # listed too, on purpose: vendored_paths only ever pins workspace/ content, so an oracle file
    # of the same name must still be scanned -- this guards the exemption staying workspace-scoped.
    d = _write_task(tmp_path, "X6", status="draft", scenario=5,
                     source={"kind": "authored", "upstream": "x", "repo": "x", "commit": "x",
                             "vendored_paths": ["vendor/", "oracle"]})
    (d / "workspace" / "vendor").mkdir(parents=True)
    (d / "workspace" / "vendor" / "Upstream.cs").write_text(r"C:\Users\someone\AppData", encoding="utf-8")
    (d / "workspace" / "Local.cs").write_text(r"C:\Users\someone\AppData", encoding="utf-8")
    (d / "oracle").mkdir()
    (d / "oracle" / "README.md").write_text(r"C:\Users\someone\AppData", encoding="utf-8")
    p = config.Problems()
    entry = {"id": "X6", "scenario": 5, "budget_minutes": 45}
    config.validate_task(d, entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    assert not any("workspace/vendor/Upstream.cs" in i for i in p.items)
    assert "tasks/X6: workspace/Local.cs:1 hardcodes an absolute user-profile path" in p.items
    assert "tasks/X6: oracle/README.md:1 hardcodes an absolute user-profile path" in p.items
