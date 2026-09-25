"""R-73: the scenario-6 `model_map` is per vendor. Keys are `<role>@<vendor>`; the vendor is a profile fact (never a
model-id prefix); one resolver gives a cell its own vendor's column; `bench validate` checks the map's grammar and
completeness; `bench plan` refuses a scenario-6 cell whose every role equals its pin (item 5)."""

import ast
import re
import shutil
from pathlib import Path

import pytest
import yaml

from harness_bench import config, plan, profiles
from harness_bench.errors import BenchError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "harness_bench"

# The F1 map as R-73 items 3 and 4 shape it (the OpenAI workhorse id is a placeholder of the right shape here; the
# Leader's stipulation lands in tasks/F1, which this slice does not touch).
PER_VENDOR = {"domain-model@anthropic": "claude-opus-5-5", "derived-quantities@anthropic": "claude-sonnet-5",
              "tests@anthropic": "claude-sonnet-5", "domain-model@openai": "gpt-6-sol",
              "derived-quantities@openai": "gpt-6-astra", "tests@openai": "gpt-6-astra"}
# The F1 draft map of w2-tasks-f1 (0f8cc9f, task.yaml:28-31): Anthropic ids, bare keys.
F1_DRAFT = {"domain-model": "claude-opus-5-5", "derived-quantities": "claude-sonnet-5", "tests": "claude-sonnet-5"}
VENDORS = {"anthropic": frozenset({"claude-haiku-4-5"}), "openai": frozenset()}


# --- item 1: the vendor is a profile fact -------------------------------------------------------------------------


def test_every_profile_declares_its_vendor():
    assert {h: profiles.load(ROOT, h).vendor for h in profiles.HARNESSES} == {
        "claude-code": "anthropic", "codex": "openai", "copilot": "openai"}


def test_a_profile_without_a_vendor_is_refused_never_inferred(tmp_path):
    shutil.copytree(ROOT / "bench" / "profiles", tmp_path / "bench" / "profiles")
    path = tmp_path / "bench" / "profiles" / "codex.yaml"
    text = path.read_text(encoding="utf-8")
    assert text.count("vendor: openai\n") == 1
    path.write_text(text.replace("vendor: openai\n", ""), encoding="utf-8")
    with pytest.raises(BenchError) as err:
        profiles.load(tmp_path, "codex")
    assert (err.value.code, err.value.message) == ("HB-USR-002", "codex: profile vendor must be a nonempty string (R-73 item 1)")


def test_the_plan_freezes_each_profile_vendor():  # views read the run's vendor, not today's profile file (US-26)
    assert {h: plan.profile_record(ROOT, h)["vendor"] for h in profiles.HARNESSES} == {
        "claude-code": "anthropic", "codex": "openai", "copilot": "openai"}


# --- item 2: one resolver ------------------------------------------------------------------------------------------


def _plan(model_map, vendors=(("claude-code", "anthropic"), ("codex", "openai"))) -> dict:
    return {"tasks": {"F1": {"scenario": 6, "model_map": model_map}},
            "profiles": {h: {"vendor": v} for h, v in vendors}}


def test_the_resolver_gives_a_codex_cell_exactly_the_openai_column():
    assert plan.resolved_model_map(_plan(PER_VENDOR), {"task": "F1", "harness": "codex"}) == {
        "domain-model": "gpt-6-sol", "derived-quantities": "gpt-6-astra", "tests": "gpt-6-astra"}


def test_the_resolver_gives_a_claude_code_cell_exactly_the_anthropic_column():
    assert plan.resolved_model_map(_plan(PER_VENDOR), {"task": "F1", "harness": "claude-code"}) == {
        "domain-model": "claude-opus-5-5", "derived-quantities": "claude-sonnet-5", "tests": "claude-sonnet-5"}


def test_the_resolver_reads_the_frozen_vendor_not_the_model_id():  # a profile fact, never a prefix rule
    frozen = _plan(PER_VENDOR, vendors=(("codex", "anthropic"),))
    assert plan.resolved_model_map(frozen, {"task": "F1", "harness": "codex"})["domain-model"] == "claude-opus-5-5"


def test_the_resolver_admits_no_bare_key_and_no_plan_without_a_frozen_vendor():
    assert plan.resolved_model_map(_plan(F1_DRAFT), {"task": "F1", "harness": "claude-code"}) == {}
    assert plan.resolved_model_map(_plan(PER_VENDOR, vendors=()), {"task": "F1", "harness": "codex"}) == {}
    assert plan.resolved_model_map({"tasks": {"X1": {"model_map": None}}, "profiles": {"codex": {"vendor": "openai"}}},
                                   {"task": "X1", "harness": "codex"}) == {}


def test_no_second_parser_of_the_vendor_key():  # R-73 c2: one definition of `<role>@<vendor>` (DM-A)
    parsers = set()
    for path in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("split", "rsplit", "partition", "rpartition", "index", "find")
                    and any(isinstance(a, ast.Constant) and a.value == "@" for a in node.args)):
                parsers.add(path.relative_to(SRC).as_posix())
    assert parsers == {"config.py"}


# --- condition 1: bench validate ----------------------------------------------------------------------------------


def test_a_complete_per_vendor_map_has_no_problem():
    assert config.model_map_problems(PER_VENDOR, VENDORS) == []


@pytest.mark.parametrize(("change", "expected"), [
    (lambda m: {**m, "reviewer": "gpt-6-sol"}, ["key 'reviewer' is not <role>@<vendor> (R-73)"]),
    (lambda m: {**m, "tests@google": "gemini-x"}, ["key 'tests@google' names vendor 'google', which no profile declares"]),
    (lambda m: {k: v for k, v in m.items() if k != "tests@openai"}, ["role 'tests' has no model for vendor 'openai'"]),
    (lambda m: {**m, "tests@anthropic": "claude-haiku-4-5"},
     ["tests@anthropic names claude-haiku-4-5, an auxiliary model of a anthropic harness"]),
    (lambda m: {**m, "tests@openai": ""}, ["tests@openai must name a model"]),
], ids=["bare key", "unknown vendor", "missing role", "auxiliary model", "empty value"])
def test_each_map_defect_is_named(change, expected):
    assert config.model_map_problems(change(dict(PER_VENDOR)), VENDORS) == expected


def test_the_f1_draft_map_is_refused_by_bench_validate(tmp_path):  # red first on 0f8cc9f task.yaml:28-31
    root = tmp_path / "root"
    shutil.copytree(ROOT / "bench", root / "bench")
    (root / "src" / "harness_bench").mkdir(parents=True)
    shutil.copytree(SRC / "grade", root / "src" / "harness_bench" / "grade")
    shutil.copytree(ROOT / "tasks" / "F1", root / "tasks" / "F1")
    task = root / "tasks" / "F1" / "task.yaml"
    data = yaml.safe_load(task.read_text(encoding="utf-8"))
    data.update(status="draft", model_map=F1_DRAFT)
    task.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    (root / "tasks" / "F1" / "prompt.md").write_text("three tracks", encoding="utf-8")
    (root / "bench" / "task-freeze.yaml").unlink()
    f1 = [i for i in config.validate_repo(root) if i.startswith("tasks/F1")]
    assert f1 == ["tasks/F1: model_map: key 'domain-model' is not <role>@<vendor> (R-73)",
                  "tasks/F1: model_map: key 'derived-quantities' is not <role>@<vendor> (R-73)",
                  "tasks/F1: model_map: key 'tests' is not <role>@<vendor> (R-73)"]
    data["model_map"] = PER_VENDOR
    task.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    assert [i for i in config.validate_repo(root) if i.startswith("tasks/F1")] == []


def test_a_stub_map_is_a_placeholder_and_the_plan_still_refuses_it():  # the stub gate; item 5 closes the path
    stub = config.load_yaml(ROOT / "tasks" / "F1" / "task.yaml")
    assert stub["status"] == "stub" and set(stub["model_map"].values()) == {"tbd"}
    assert [i for i in config.validate_repo(ROOT) if i.startswith("tasks/F1")] == []


# --- item 5: bench plan refuses a map that cannot distinguish routing from no routing -------------------------------


def _scenario6_root(tmp_path: Path, model_map: dict) -> tuple[Path, dict]:
    root = tmp_path / "root"
    shutil.copytree(ROOT / "tasks" / "X1", root / "tasks" / "X1")
    shutil.copytree(ROOT / "bench", root / "bench")
    task = root / "tasks" / "X1" / "task.yaml"
    text = task.read_text(encoding="utf-8")
    assert text.count("model_map: null") == 1
    task.write_text(text.replace("model_map: null", "model_map: " + yaml.safe_dump(model_map, default_flow_style=True).strip()),
                    encoding="utf-8")
    bom = config.load_yaml(root / "bench" / "bom.yaml")
    next(t for t in bom["tasks"] if t["id"] == "X1")["scenario"] = 6
    return root, bom


def _build(root: Path, bom: dict) -> dict:
    m = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")  # cc-sonnet (claude-sonnet-5), codex-sol (gpt-6-sol)
    builds = {"claude-code": {"version": "2.1.274", "sha256": "a" * 64}, "codex": {"version": "0.156.0", "sha256": "b" * 64}}
    return plan.build_plan(root, m, bom, "r1", builds, {"source": "../ai-forward", "commit": "c" * 40, "revision": 92})


def test_bench_plan_refuses_a_scenario6_cell_whose_every_role_is_its_pin(tmp_path):
    root, bom = _scenario6_root(tmp_path, {"a@anthropic": "claude-sonnet-5", "b@anthropic": "claude-opus-5-5",
                                           "a@openai": "gpt-6-sol", "b@openai": "gpt-6-sol"})
    with pytest.raises(BenchError) as err:
        _build(root, bom)
    assert err.value.code == "HB-USR-002"
    assert err.value.message == ("scenario 6: every role of X1's model_map for vendor openai equals the pin of "
                                 "X1.codex-sol.pack-on.r1 (gpt-6-sol), so routing cannot be told from no routing (R-73 item 5)")


def test_bench_plan_accepts_a_scenario6_map_with_one_role_off_the_pin(tmp_path):
    root, bom = _scenario6_root(tmp_path, {"a@anthropic": "claude-sonnet-5", "b@anthropic": "claude-opus-5-5",
                                           "a@openai": "gpt-6-sol", "b@openai": "gpt-6-astra"})
    p = _build(root, bom)
    assert {c["combo"] for c in p["cells"]} == {"cc-sonnet", "codex-sol"}
    codex = next(c for c in p["cells"] if c["combo"] == "codex-sol")
    assert plan.resolved_model_map(p, codex) == {"a": "gpt-6-sol", "b": "gpt-6-astra"}


def test_bench_plan_refuses_a_scenario6_cell_with_no_role_for_its_vendor(tmp_path):
    root, bom = _scenario6_root(tmp_path, {"a@anthropic": "claude-sonnet-5", "b@anthropic": "claude-opus-5-5"})
    with pytest.raises(BenchError) as err:
        _build(root, bom)
    assert re.fullmatch(r"scenario 6: X1's model_map names no role for vendor openai \(cell X1\.codex-sol\.pack-on\.r1\)"
                        r" \(R-73 item 5\)", err.value.message)
