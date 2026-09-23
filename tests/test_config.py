from pathlib import Path

import yaml

from harness_bench import config

ROOT = Path(__file__).resolve().parents[1]


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
    config.validate_task(d, entry, p, config.grader_modules(ROOT))
    msgs = " ".join(p.items)
    assert "hidden tests or an oracle" in msgs
    assert "workspace/" in msgs


def test_budget_above_coord_runner_deadline_is_rejected():
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    bom["tasks"][0]["budget_minutes"] = 61
    p = config.Problems()
    config.validate_bom(bom, p)
    assert any("budget_minutes" in i for i in p.items)


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
