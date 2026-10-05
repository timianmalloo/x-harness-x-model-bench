import shutil
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from harness_bench import config

ROOT = Path(__file__).resolve().parents[1]


def _arms_matrix(tmp_path):
    return {"schema": "bench-matrix/2", "repetitions": 3, "bom": {"subset": ["X1"]},
            "arms": [{"id": "off"}, {"id": "candidate", "pack": {
                "source": str(tmp_path.resolve()), "commit": "c" * 40}}],
            "combos": [{"id": "cc-opus", "harness": "claude-code", "model": "claude-opus-5-5"}]}


def test_matrix2_pinned_arms_and_ring_roles_are_valid(tmp_path):
    matrix = _arms_matrix(tmp_path)
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    for data in (matrix, {**matrix, "ring": {"tag": "pilot"}, "arms": [{"id": "off"}, {"id": "candidate"}]}):
        problems = config.Problems()
        config.validate_matrix(data, bom, problems, "matrix")
        assert problems.items == []


@pytest.mark.parametrize("field,value,fragment", [
    ("schema", "bench-matrix/3", "schema"),
    ("packs", ["on", "off"], "packs"),
    ("arms", [], "at least 2"),
    ("arms", [{"id": "off"}], "at least 2"),
    ("arms", [{"id": "off"}, {"id": "off"}], "duplicate"),
    ("arms", [{"id": False}, {"id": "candidate"}], "quote"),
    ("arms", [{"id": "bad.id"}, {"id": "candidate"}], "id"),
    ("arms", [{"id": "off", "pack": {}}, {"id": "candidate"}], "off"),
    ("arms", [{"id": "off"}, {"id": "candidate"}], "ring"),
    ("ring", {"tag": "unknown"}, "ring"),
    ("comparisons", [[False, "candidate"]], "quote"),
    ("comparisons", [["off", "missing"]], "declared"),
    ("comparisons", [["candidate", "candidate"]], "different"),
    ("comparisons", [["off", "candidate"], ["off", "candidate"]], "duplicate"),
    ("comparisons", [["off"]], "pair"),
    ("repetitions", True, "integer"),
])
def test_matrix2_refuses_each_invalid_shape(tmp_path, field, value, fragment):
    matrix = _arms_matrix(tmp_path)
    matrix[field] = deepcopy(value)
    problems = config.Problems()
    config.validate_matrix(matrix, config.load_yaml(ROOT / "bench" / "bom.yaml"), problems, "matrix")
    assert any(fragment in item for item in problems.items), problems.items


@pytest.mark.parametrize("source,commit", [("relative", "c" * 40), ("", "c" * 40),
                                          (None, "c" * 40), ("absolute", "HEAD"),
                                          ("absolute", "C" * 40), ("absolute", "c" * 39)])
def test_matrix2_pack_requires_absolute_source_and_hex_commit(tmp_path, source, commit):
    matrix = _arms_matrix(tmp_path)
    matrix["arms"][1]["pack"] = {"source": str(tmp_path) if source == "absolute" else source, "commit": commit}
    problems = config.Problems()
    config.validate_matrix(matrix, config.load_yaml(ROOT / "bench" / "bom.yaml"), problems, "matrix")
    assert any("source" in item or "commit" in item for item in problems.items), problems.items


def test_matrix2_three_arms_require_comparisons(tmp_path):
    matrix = _arms_matrix(tmp_path)
    matrix["arms"].append({"id": "incumbent", "pack": deepcopy(matrix["arms"][1]["pack"])})
    problems = config.Problems()
    config.validate_matrix(matrix, config.load_yaml(ROOT / "bench" / "bom.yaml"), problems, "matrix")
    assert any("comparisons" in item for item in problems.items)
    matrix["comparisons"] = [["off", "candidate"], ["incumbent", "candidate"]]
    problems = config.Problems()
    config.validate_matrix(matrix, config.load_yaml(ROOT / "bench" / "bom.yaml"), problems, "matrix")
    assert problems.items == []


@pytest.mark.parametrize("field", ["arms", "comparisons", "ring"])
def test_matrix1_refuses_matrix2_fields(field):
    matrix = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    matrix[field] = []
    problems = config.Problems()
    config.validate_matrix(matrix, config.load_yaml(ROOT / "bench" / "bom.yaml"), problems, "matrix")
    assert any(field in item for item in problems.items)


def test_check_properties_are_declared_property_names():
    assert config.PROPERTY_NAMES == ("security", "resilience", "rework", "no-guessing", "simplicity")
    assert config.CHECK_PROPERTIES == frozenset({"security", "resilience"})
    assert config.CHECK_PROPERTIES <= set(config.PROPERTY_NAMES)


def test_synthetic_is_never_a_valid_file_matrix_harness(tmp_path):
    matrix = _arms_matrix(tmp_path)
    matrix["combos"][0]["harness"] = "synthetic"
    problems = config.Problems()
    config.validate_matrix(matrix, config.load_yaml(ROOT / "bench" / "bom.yaml"), problems, "matrix")
    assert any("harness" in item for item in problems.items)
    assert "synthetic" not in config.HARNESSES


def test_repo_inputs_are_valid():
    assert config.validate_repo(ROOT) == []


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
    (d / "prompt.md").write_text("line one\n" r"Run from C:\Users\malla\projects\bench" "\n", encoding="utf-8")  # machine-path-ok: detector input
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
    (d / "workspace" / "vendor" / "Upstream.cs").write_text(r"C:\Users\someone\AppData", encoding="utf-8")  # machine-path-ok: detector input
    (d / "workspace" / "Local.cs").write_text(r"C:\Users\someone\AppData", encoding="utf-8")  # machine-path-ok: detector input
    (d / "oracle").mkdir()
    (d / "oracle" / "README.md").write_text(r"C:\Users\someone\AppData", encoding="utf-8")  # machine-path-ok: detector input
    p = config.Problems()
    entry = {"id": "X6", "scenario": 5, "budget_minutes": 45}
    config.validate_task(d, entry, p, config.grader_modules(ROOT), config.pack_marker_bytes(ROOT))
    assert not any("workspace/vendor/Upstream.cs" in i for i in p.items)
    assert "tasks/X6: workspace/Local.cs:1 hardcodes an absolute user-profile path" in p.items
    assert "tasks/X6: oracle/README.md:1 hardcodes an absolute user-profile path" in p.items


# --- rubrics live in the catalog (R-59 DR-5, R-64; design: Catalog-version rule 5; seam V-3) -----------------------


def _rubric_root(tmp_path: Path) -> Path:
    """A root with the real bench/ and tasks/C1; problems about the other BOM task folders are not these tests' subject."""
    root = tmp_path / "root"
    shutil.copytree(ROOT / "bench", root / "bench")
    shutil.copytree(ROOT / "tasks" / "C1", root / "tasks" / "C1")
    return root


def _rubric_problems(root: Path) -> list[str]:
    return [p for p in config.validate_repo(root) if "rubric" in p]


def test_the_catalog_rubric_must_equal_c1s_rubric_byte_for_byte(tmp_path):
    root = _rubric_root(tmp_path)
    (root / "bench" / "rubrics").mkdir(exist_ok=True)
    copy = root / "bench" / "rubrics" / "adr_quality.md"
    copy.write_bytes((ROOT / "tasks" / "C1" / "oracle" / "rubric.md").read_bytes())
    assert _rubric_problems(root) == []
    copy.write_bytes(copy.read_bytes().replace(b"\n", b"\r\n", 1))  # one line end differs: not the same bytes
    assert _rubric_problems(root) == ["bench/rubrics/adr_quality.md: differs from tasks/C1/oracle/rubric.md (R-59 DR-5: byte for byte)"]


def test_each_rubrics_value_must_name_an_existing_file(tmp_path):
    root = _rubric_root(tmp_path)
    path = root / "bench" / "metrics.yaml"
    area = next(a for a, v in config.load_yaml(path)["areas"].items() if any(m["id"] == "adr_quality" for m in v["metrics"]))
    text = path.read_text(encoding="utf-8")
    old = "rubrics: { C1: adr_quality.md }"  # the catalog entry since W3-GW-I slice 5 (design section 13)
    assert text.count(old) == 1
    path.write_text(text.replace(old, "rubrics: { C1: missing.md }"), encoding="utf-8")
    assert _rubric_problems(root) == [(f"bench/metrics.yaml: {area}.adr_quality: rubrics C1 names bench/rubrics/missing.md, "
                                       "which does not exist")]


# --- metric anchor and weight validations (R-78 condition 2, R-79 DR-C1; seam Z-4) -----------------


def test_weighted_score_metric_without_anchor_is_refused():
    metrics = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    m = next(m for a in metrics["areas"].values() for m in a["metrics"] if m.get("kind") == "score" and m.get("weight", 0) > 0 and "anchor" in m)
    del m["anchor"]
    p = config.Problems()
    config.validate_metrics(metrics, p, config.grader_modules(ROOT), root=ROOT)
    assert any("weighted kind: score metric has no anchor" in i for i in p.items)


def test_anchor_worst_equals_best_is_refused():
    metrics = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    m = next(m for a in metrics["areas"].values() for m in a["metrics"] if "anchor" in m)
    m["anchor"] = [1.0, 1.0]
    p = config.Problems()
    config.validate_metrics(metrics, p, config.grader_modules(ROOT), root=ROOT)
    assert any("anchor worst == best" in i for i in p.items)


def test_anchor_direction_contradicting_better_is_refused():
    metrics = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    m = next(m for a in metrics["areas"].values() for m in a["metrics"] if m.get("better") == "higher" and "anchor" in m)
    m["anchor"] = [10.0, 0.0]
    p = config.Problems()
    config.validate_metrics(metrics, p, config.grader_modules(ROOT), root=ROOT)
    assert any("anchor direction contradicts better" in i for i in p.items)


def test_derived_metric_with_positive_weight_is_refused():
    metrics = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    m = next(m for a in metrics["areas"].values() for m in a["metrics"] if m.get("kind") == "derived")
    m["weight"] = 1
    p = config.Problems()
    config.validate_metrics(metrics, p, config.grader_modules(ROOT), root=ROOT)
    assert any("kind: derived metric cannot have weight > 0" in i for i in p.items)


def test_judged_metric_with_rubric_and_wrong_anchor_span_is_refused():
    metrics = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    m = next(m for a in metrics["areas"].values() for m in a["metrics"] if m.get("grader") == "judge" and m.get("rubrics"))
    m["anchor"] = [0.0, 10.0]  # adr_quality has 7 items, so span must be 14
    p = config.Problems()
    config.validate_metrics(metrics, p, config.grader_modules(ROOT), root=ROOT)
    assert any("|best - worst| != 2 x rubric item count" in i for i in p.items)


def test_better_lower_judged_rubric_must_define_2_as_worst_per_item_is_refused():
    metrics = config.load_yaml(ROOT / "bench" / "metrics.yaml")
    m = next(m for a in metrics["areas"].values() for m in a["metrics"] if m.get("grader") == "judge" and m.get("rubrics"))
    m["better"] = "lower"
    m["anchor"] = [28.0, 14.0]  # span is 14 (2 x 7), but worst is 28, not 2 x 7
    p = config.Problems()
    config.validate_metrics(metrics, p, config.grader_modules(ROOT), root=ROOT)
    assert any("a better: lower judged rubric must define 2 as worst per item" in i for i in p.items)
