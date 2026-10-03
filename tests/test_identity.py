"""D1 proof: W0 §9/§11, W1-D T-7, T-8, T-10/10b, T-12..12d, T-22.

G2 root: src/harness_bench/; recursion: yes; tokens: every file path except
under __pycache__/; allowlist: none (CLASSES is the classification table).
G2b root: run-class Python modules there; recursion: yes; tokens: every
resolved grade-class import; allowlist: RUN_IMPORTS_GRADE_ALLOWED; cli.py is
the composition root exemption. Both guards take fixture tables.

D1 verification map (confidence: Verified by observed assertions):
  W0 §11 -> test_every_e1_error_row_is_registered_with_w0_meaning:
    registry missing-row assertion observed red before all 34 E1 rows landed.
  W1-D T-8/T-10/T-10b/T-22 -> unclassed/stale, real-tree and W0 table tests:
    empty-table scaffold failed; disk fixtures cover py/json/js, ghost and landed keys.
  W1-D T-12..12d -> direction tests: assertion-red, placement ruling pending.
  W1-D T-7 -> catalog recipe tests: recipes agree; runner import ruling pending.
  W1-D T-33..35 -> architecture fixtures: alias bypasses, gateway imports and
    missing allowlist entries observed red before the corresponding guard fixes.
  Relative-import property -> deleting relative targets was killed by the named
    property test; its shrunk counterexample is retained as a regression test.
  Real readers -> architecture guards scan the source tree; BenchError accepts
    every new E1 code; the catalog tests call the real plan.tree_hash recipe.
  Data model -> one classification per source path; catalog digest is non-additive.
    No persistent schema, event field, client type or UI changes in D1.
  Residual -> this is a blocked red track, not a completed Proof Pack. D2's
    manifest/launch/telemetry surfaces and the external join review are deferred.
"""

import ast
import hashlib
import re
import shutil
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from import_graph import aliases, dotted, import_violations, imports, stale_allowed

from harness_bench import errors, identity, ledger, plan, profiles
from harness_bench.grade import runner

ROOT = Path(__file__).resolve().parents[1]
EXEMPT = frozenset({"cli.py"})


def write_source(root, name, source=""):
    path = root / "src" / "harness_bench" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def w0_modules(text):
    section = text.split("## 9. Planned new modules", 1)[1].split("## 10.", 1)[0]
    return {name: kind for name, kind in re.findall(
        r"\| `src/harness_bench/([^`]+)`[^|]*\| (run|grade)\b", section)}


def test_every_e1_error_row_is_registered_with_w0_meaning():
    text = (ROOT / "docs/design/eval-seam-contracts.md").read_text(encoding="utf-8")
    rows = [(parts[1].strip(), parts[2].strip()) for line in text.splitlines()
            if line.startswith("| HB-") and "E1" in line and "reserved, no E1 code path" not in line
            for parts in [line.split("|")]]
    expected = {"HB-LED-007", "HB-IDN-001", "HB-IDN-002", "HB-PWR-001", "HB-GRD-007"}
    expected |= {f"HB-PLN-{n:03d}" for n in (1, 2, 4, 5)}
    expected |= {f"HB-CHK-{n:03d}" for n in range(1, 5)}
    expected |= {f"HB-RDY-{n:03d}" for n in range(1, 12) if n != 9}
    expected |= {f"HB-CMP-{n:03d}" for n in range(1, 11)}

    assert {code for code, _ in rows} == expected
    assert {code: errors.RUN_CODES.get(code) for code, _ in rows} == dict(rows)
    for code in expected:
        assert errors.BenchError(code, "fixture").code == code


def test_unclassed_flags_each_new_file_kind(tmp_path):
    for name in ("new.py", "schemas/new.json", "assets/new.js", "__pycache__/ignored.pyc"):
        write_source(tmp_path, name)

    assert identity.unclassed(tmp_path, {}, frozenset({"future.py"})) == [
        "assets/new.js", "new.py", "schemas/new.json"]


def test_classed_files_and_missing_planned_files_are_silent(tmp_path):
    write_source(tmp_path, "known.json")

    assert identity.unclassed(tmp_path, {"known.json": "grade", "future.py": "run"},
                              frozenset({"future.py"})) == []


@pytest.mark.parametrize("landed", [False, True])
def test_stale_flags_ghost_and_landed_keys(tmp_path, landed):
    if landed:
        write_source(tmp_path, "future.py")
    classes = {"ghost.py": "run", "future.py": "grade"}

    assert identity.stale(tmp_path, classes, frozenset({"future.py"})) == (
        ["future.py", "ghost.py"] if landed else ["ghost.py"])


def test_every_src_file_has_a_class():
    assert len(identity.CLASSES) >= 69
    assert identity.unclassed(ROOT, identity.CLASSES, identity.PLANNED) == []
    assert identity.stale(ROOT, identity.CLASSES, identity.PLANNED) == []
    assert set(identity.CLASSES.values()) == {"run", "grade"}
    assert all(identity.CLASSES[name] == "run" for name in identity.CLASSES if name.startswith("telemetry/"))
    assert all(identity.CLASSES[name] == "grade" for name in identity.CLASSES if name.startswith("gateway/"))


def test_classes_match_w0_section_9():
    text = (ROOT / "docs/design/eval-seam-contracts.md").read_text(encoding="utf-8")
    expected = w0_modules(text)

    assert len(expected) == 18
    assert {name: identity.CLASSES.get(name) for name in expected} == expected
    assert identity.PLANNED == frozenset(name for name in expected
                                       if not (ROOT / "src/harness_bench" / name).is_file())
    wrong = text.replace("| `src/harness_bench/identity.py` | run |", "| `src/harness_bench/identity.py` | grade |", 1)
    assert {name: identity.CLASSES.get(name) for name in w0_modules(wrong)} != w0_modules(wrong)


@pytest.mark.parametrize("source", [
    "from harness_bench.grade.x import y\n",
    "def lazy():\n    from harness_bench.grade.x import y\n",
    "from ..grade.x import y\n",
    "import harness_bench.grade.x as g\n",
    "from harness_bench import grade\n",
    "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from harness_bench.grade.x import y\n",
])
def test_import_violations_red_fixtures(tmp_path, source):
    write_source(tmp_path, "telemetry/run.py", source)
    write_source(tmp_path, "grade/x.py")
    write_source(tmp_path, "grade/__init__.py")
    classes = {"telemetry/run.py": "run", "grade/x.py": "grade", "grade/__init__.py": "grade"}
    target = "grade/__init__.py" if source == "from harness_bench import grade\n" else "grade/x.py"

    assert import_violations(tmp_path, classes, {}, frozenset()) == [("telemetry/run.py", target)]


def test_allowed_pair_and_cli_are_silent(tmp_path):
    source = "from harness_bench.grade.x import y\n"
    for name in ("allowed.py", "other.py", "cli.py"):
        write_source(tmp_path, name, source)
    write_source(tmp_path, "grade/x.py")
    classes = {"allowed.py": "run", "other.py": "run", "cli.py": "run", "grade/x.py": "grade"}

    assert import_violations(tmp_path, classes, {("allowed.py", "grade/x.py"): "fixture"}, EXEMPT) == [
        ("other.py", "grade/x.py")]


def test_stale_allowed_pair_fails(tmp_path):
    write_source(tmp_path, "allowed.py")
    write_source(tmp_path, "grade/x.py")
    classes = {"allowed.py": "run", "grade/x.py": "grade"}
    allowed = {("allowed.py", "grade/x.py"): "fixture"}

    assert stale_allowed(tmp_path, classes, allowed) == [("allowed.py", "grade/x.py")]
    write_source(tmp_path, "allowed.py", "from harness_bench.grade.x import y\n")
    assert stale_allowed(tmp_path, classes, allowed) == []


def test_real_tree_edges_equal_the_allowlist():
    expected = {("config.py", "egress.py"), ("config.py", "gateway/backend.py"),
                ("config.py", "gateway/scrub.py")}

    assert set(identity.RUN_IMPORTS_GRADE_ALLOWED) == expected
    assert set(import_violations(ROOT, identity.CLASSES, {}, EXEMPT)) == expected
    assert import_violations(ROOT, identity.CLASSES, identity.RUN_IMPORTS_GRADE_ALLOWED, EXEMPT) == []
    assert stale_allowed(ROOT, identity.CLASSES, identity.RUN_IMPORTS_GRADE_ALLOWED) == []
    assert all("review 2027-10-03" in reason and "remove when" in reason
               for reason in identity.RUN_IMPORTS_GRADE_ALLOWED.values())


@settings(max_examples=40, deadline=None, derandomize=True)
@given(depth=st.integers(min_value=1, max_value=4), name=st.text(alphabet="abc", min_size=1, max_size=8))
def test_relative_and_absolute_imports_resolve_to_the_same_module(depth, name):
    rel = "src/harness_bench/" + "nested/" * depth + "caller.py"
    absolute = ast.parse(f"from harness_bench.grade.{name} import value as v")
    relative = ast.parse(f"from {'.' * (depth + 1)}grade.{name} import value as v")

    assert imports(rel, relative) == imports(rel, absolute) == {f"harness_bench.grade.{name}.value"}
    assert dotted(ast.parse("v()", mode="eval").body.func, aliases(rel, relative)) == f"harness_bench.grade.{name}.value"


def test_relative_import_keeps_the_parent_package_regression():
    # Shrunk counterexample from the observed relative-import deletion mutant.
    tree = ast.parse("from ..grade.a import value as v")

    assert imports("src/harness_bench/nested/caller.py", tree) == {"harness_bench.grade.a.value"}


def test_catalog_component_equals_runner_catalog_hash(tmp_path):
    bench = tmp_path / "bench"
    (bench / "rubrics/nested").mkdir(parents=True)
    (bench / "metrics.yaml").write_bytes(b"metrics:\r\n  - id: score\r\n")
    (bench / "rubrics/nested/score.md").write_bytes(b"rubric\r\n")
    files = [bench / "metrics.yaml", bench / "rubrics/nested/score.md"]

    assert identity.catalog_hash(tmp_path) == plan.tree_hash(bench, files)
    assert runner.catalog_hash is identity.catalog_hash
    before = identity.catalog_hash(tmp_path)
    (bench / "rubrics/nested/score.md").write_bytes(b"changed\n")
    assert identity.catalog_hash(tmp_path) != before
    assert identity.catalog_hash(ROOT) == runner.catalog_hash(ROOT)


def test_catalog_without_rubrics_uses_the_original_recipe(tmp_path):
    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "metrics.yaml").write_bytes(b"metrics: []\n")

    assert identity.catalog_hash(tmp_path) == plan.tree_hash(bench, [bench / "metrics.yaml"])


@pytest.fixture
def identity_root(tmp_path):
    """Real recipes, a small classed tree, and every committed harness profile."""
    root = tmp_path / "identity-root"
    for name in ("engine.py", "grade/formal.py", "telemetry/normalize.py", "report/assets/report.js"):
        write_source(root, name, "original\n")
    shutil.copytree(ROOT / "bench/profiles", root / "bench/profiles")
    for name in ("metrics.yaml", "prices.yaml", "bom.yaml"):
        (root / "bench" / name).write_text("version: 1\nmetrics: []\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    for task in ("t", "u"):
        folder = root / "tasks" / task
        folder.mkdir(parents=True)
        (folder / "prompt.md").write_text(f"task {task}\n", encoding="utf-8")
    return root


def frozen_plan(root, tasks=("t",), builds=None):
    m = identity.manifest(root, tasks, builds)
    run = identity.side(m, "run")
    return {"tasks": {task: {} for task in tasks}, "builds": builds or {},
            "campaign": {"identity": {"hash": identity.identity_hash(run), "components": run["components"]}}}


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_manifest_is_deterministic_and_line_ending_independent(identity_root):  # T-1
    path = identity_root / "src/harness_bench/engine.py"
    path.write_bytes(b"line1\r\nline2\r\n")
    before = identity.manifest(identity_root, ["t"])

    assert before["components"].get("src/harness_bench/engine.py") == plan.tree_hash(path.parent, [path])
    path.write_bytes(b"line1\nline2\n")
    assert identity.manifest(identity_root, ["t"]) == before
    assert identity.identity_hash(before) == hashlib.sha256(ledger.canonical(before)).hexdigest()


def test_side_partitions_every_component():  # T-2, real tree
    m = identity.manifest(ROOT, ["X1"], {"codex": {"version": "test"}})
    run, grade = identity.side(m, "run"), identity.side(m, "grade")

    assert run["components"] and grade["components"]
    assert set(run["components"]) | set(grade["components"]) == set(m["components"])
    assert not set(run["components"]) & set(grade["components"])
    assert run["schema"] == grade["schema"] == m["schema"]


def test_telemetry_edit_changes_the_run_side_only(identity_root):  # T-3, R-94
    before = identity.manifest(identity_root, ["t"])
    write_source(identity_root, "telemetry/normalize.py", "edited\n")
    after = identity.manifest(identity_root, ["t"])

    assert identity.identity_hash(identity.side(before, "run")) != identity.identity_hash(identity.side(after, "run"))
    assert identity.side(before, "grade") == identity.side(after, "grade")


def test_gateway_is_a_grade_component(identity_root):  # T-4, R-94
    before = identity.manifest(identity_root, ["t"])
    assert before["components"].get("gateway") == ""
    gateway = identity_root / "bench/gateway.yaml"
    gateway.write_text("model: test\n", encoding="utf-8")
    present = identity.manifest(identity_root, ["t"])
    assert present["components"].get("gateway") == plan.file_hash(gateway)
    assert identity.side(before, "run") == identity.side(present, "run")
    assert identity.side(before, "grade") != identity.side(present, "grade")
    gateway.write_text("model: other\n", encoding="utf-8")
    assert identity.side(present, "grade") != identity.side(identity.manifest(identity_root, ["t"]), "grade")


def test_diff_names_changed_added_removed():  # T-5, EV-20 exit copy
    a = {"schema": identity.SCHEMA, "components": {"src/harness_bench/grade/formal.py": "old", "y": "old"}}
    b = {"schema": identity.SCHEMA, "components": {"src/harness_bench/grade/formal.py": "new", "x": "new"}}

    assert identity.diff(a, b) == ["grade/formal.py changed", "x added", "y removed"]


def test_unrelated_files_do_not_change_the_hash(identity_root):  # T-6
    before = identity.manifest(identity_root, ["t"])
    for folder in ("docs", "tests", "tools"):
        (identity_root / folder).mkdir()
        (identity_root / folder / "ignored.txt").write_text("edit", encoding="utf-8")
    assert identity.manifest(identity_root, ["t"]) == before
    write_source(identity_root, "engine.py", "changed")
    assert identity.identity_hash(identity.manifest(identity_root, ["t"])) != identity.identity_hash(before)


def test_components_equal_the_existing_recipes(identity_root):  # T-7
    builds = {"codex": {"version": "test", "sha256": "binary"}}
    components = identity.manifest(identity_root, ["t"], builds)["components"]
    expected = {"catalog": runner.catalog_hash(identity_root), "prices": plan.file_hash(identity_root / "bench/prices.yaml"),
                "bom": plan.file_hash(identity_root / "bench/bom.yaml"), "uv.lock": plan.file_hash(identity_root / "uv.lock"),
                "tasks/t": plan.task_version_hash(identity_root / "tasks/t"), "platform": sys.platform,
                "python": ".".join(map(str, sys.version_info[:3])),
                "builds/codex": hashlib.sha256(ledger.canonical(builds["codex"])).hexdigest()}
    expected.update({f"profiles/{h}": hashlib.sha256(ledger.canonical(plan.profile_record(identity_root, h))).hexdigest()
                     for h in profiles.HARNESSES})

    assert {key: components.get(key) for key in expected} == expected


def test_for_task_drops_builds_and_other_tasks():  # W0 rev 5, skeleton must fail an assertion
    m = {"schema": identity.SCHEMA, "components": {"tasks/t": "t", "tasks/u": "u", "builds/codex": "b", "bom": "bom"}}
    selected = identity.for_task(m, "t")

    assert selected == {"schema": identity.SCHEMA, "components": {"tasks/t": "t", "bom": "bom"}}
    assert set(m["components"]) == {"tasks/t", "tasks/u", "builds/codex", "bom"}


def test_single_task_identity_equals_projected_campaign_identity(identity_root):  # SR-E1 3
    direct = identity.manifest(identity_root, ["t"], builds=None)
    baseline = identity.manifest(identity_root, ["u", "t"], builds={"codex": {"version": "test"}})

    assert not any(key.startswith("builds/") for key in direct["components"])
    assert {key for key in direct["components"] if key.startswith("profiles/")} == {f"profiles/{h}" for h in profiles.HARNESSES}
    assert "tasks/u" in baseline["components"] and "builds/codex" in baseline["components"]
    assert identity.identity_hash(direct) == identity.identity_hash(identity.for_task(baseline, "t"))


def test_unclassified_file_refused(identity_root):  # T-9 includes non-Python
    write_source(identity_root, "stray.json", "{}")

    with pytest.raises(errors.BenchError) as caught:
        identity.manifest(identity_root, ["t"])
    assert caught.value.code == "HB-IDN-002"
    assert "stray.json" in str(caught.value)


def test_manifest_leaks_no_environment_or_path(identity_root, monkeypatch):  # T-11
    sentinels = ["secret-user-sentinel", "secret-host-sentinel", "secret-home-sentinel", "secret-profile-sentinel"]
    for name, value in zip(("USERNAME", "COMPUTERNAME", "HOME", "USERPROFILE"), sentinels, strict=True):
        monkeypatch.setenv(name, value)
    m = identity.manifest(identity_root, ["t"])
    encoded = ledger.canonical(m).decode()

    assert m["components"].get("platform") == sys.platform
    assert all(value not in encoded for value in [*sentinels, str(identity_root), identity_root.as_posix()])


def test_non_campaign_plan_has_no_check(identity_root):  # T-18
    assert identity.launch_check(identity_root, {"tasks": {"t": {}}, "builds": {}}) is None


def test_run_edit_stops_launch_grade_edit_does_not(identity_root):  # T-17
    p = frozen_plan(identity_root)
    clock = FakeClock()
    check = identity.launch_check(identity_root, p, clock=clock, sleep=clock.sleep)
    write_source(identity_root, "grade/formal.py", "grade edit")
    assert check() == identity.CheckResult([], False)
    write_source(identity_root, "engine.py", "run edit")
    assert check() == identity.CheckResult(["engine.py changed"], False)


def test_a_torn_read_is_not_drift(identity_root):  # T-14
    p = frozen_plan(identity_root)
    path = identity_root / "src/harness_bench/engine.py"
    path.write_text("temporary", encoding="utf-8")
    clock = FakeClock()

    def restore(seconds):
        clock.sleep(seconds)
        path.write_text("original\n", encoding="utf-8")

    check = identity.launch_check(identity_root, p, clock=clock, sleep=restore)
    assert check() == identity.CheckResult([], True)
    assert clock.sleeps == [0.05]


def test_a_persistent_diff_survives_the_recheck(identity_root, monkeypatch):  # T-15, differing keys only
    p = frozen_plan(identity_root)
    path = identity_root / "src/harness_bench/engine.py"
    path.write_text("persistent", encoding="utf-8")
    clock = FakeClock()
    reads = []
    real_read = Path.read_bytes

    def read(file):
        reads.append(file)
        return real_read(file)

    monkeypatch.setattr(Path, "read_bytes", read)
    check = identity.launch_check(identity_root, p, clock=clock, sleep=clock.sleep)
    assert check() == identity.CheckResult(["engine.py changed"], False)
    assert clock.sleeps == [0.05]
    assert reads.count(path) == 2
    assert reads.count(identity_root / "uv.lock") == 1


def test_unreadable_component_is_named_after_retries(identity_root, monkeypatch):  # T-13
    p = frozen_plan(identity_root)
    path = identity_root / "src/harness_bench/engine.py"
    clock = FakeClock()
    real_read = Path.read_bytes
    attempts = []

    def locked(file):
        if file == path:
            attempts.append(file)
            raise PermissionError("locked")
        return real_read(file)

    monkeypatch.setattr(Path, "read_bytes", locked)
    check = identity.launch_check(identity_root, p, clock=clock, sleep=clock.sleep)
    assert check() == identity.CheckResult(["engine.py unreadable"], False)
    assert len(attempts) == 4
    assert clock.sleeps == [0.05] * 3


def test_check_stops_at_the_deadline(identity_root, monkeypatch):  # T-16
    p = frozen_plan(identity_root)
    clock = FakeClock()
    real_read = Path.read_bytes
    reads = []

    def slow(file):
        reads.append(file)
        clock.now += 3
        return real_read(file)

    monkeypatch.setattr(Path, "read_bytes", slow)
    check = identity.launch_check(identity_root, p, clock=clock, sleep=clock.sleep)
    result = check()

    assert result.diff and any(item.endswith("unreadable (deadline)") for item in result.diff)
    assert len(reads) == 1
    assert not clock.sleeps


def test_new_and_removed_run_components_stop_launch(identity_root):
    p = frozen_plan(identity_root)
    clock = FakeClock()
    check = identity.launch_check(identity_root, p, clock=clock, sleep=clock.sleep)
    (identity_root / "src/harness_bench/engine.py").unlink()
    write_source(identity_root, "driver.py", "new")

    assert check().diff == ["driver.py added", "engine.py removed"]


def test_stray_file_stops_launch(identity_root):
    p = frozen_plan(identity_root)
    write_source(identity_root, "stray.json", "{}")
    clock = FakeClock()

    result = identity.launch_check(identity_root, p, clock=clock, sleep=clock.sleep)()
    assert result.diff and "stray.json" in " ".join(result.diff)


@given(st.dictionaries(st.sampled_from(["tasks/t", "tasks/u", "builds/codex", "bom", "catalog"]), st.text(max_size=12)))
@settings(max_examples=30, deadline=None, derandomize=True)
def test_for_task_projection_is_idempotent_and_preserves_only_its_domain(components):
    m = {"schema": identity.SCHEMA, "components": components}
    selected = identity.for_task(m, "t")

    assert selected["components"] == {k: v for k, v in components.items()
                                      if not k.startswith("builds/") and (not k.startswith("tasks/") or k == "tasks/t")}
    assert identity.for_task(selected, "t") == selected


@pytest.fixture
def confirmed_campaign_run(identity_root, base, monkeypatch):
    """T-25: real confirmed plan, CLI, Engine, workspace and ledger; only preflight is stubbed.

    The cell uses a missing local base, so it ends at the real workspace boundary
    without a model call. Its outcome is deliberately outside this test's claim.
    """
    from harness_bench import preflight

    task_dir = identity_root / "tasks/t"
    (task_dir / "task.yaml").write_text("id: t\nscenario: 1\nsource:\n  kind: local\n  path: missing-base\n", encoding="utf-8")
    builds = {"codex": {"version": "fixture", "sha256": "fixture", "adapter_version": "fixture", "adapter_sha256": "fixture"}}
    c = plan.Cell("t", plan.task_version_hash(task_dir), 1, "codex", "codex", "fixture-model", "off", 1, 60)
    p = {"schema": "bench-plan/1", "run_id": "identity-cli", "trace_id": "a" * 32,
         "parameters": {**plan.DEFAULT_PARAMETERS, "parallelism": 1, "disk_floor_bytes": 1},
         "tasks": {"t": {"version_hash": c.task_version, "prompt": "fixture", "scenario": 1, "graders": []}},
         "cells": [{"cell_id": c.id, "label": c.label, **c.__dict__}], "builds": builds,
         "profiles": {"codex": plan.profile_record(identity_root, "codex")}, "pack": None,
         "platform": sys.platform, "price_list_hash": plan.file_hash(identity_root / "bench/prices.yaml")}
    p["campaign"] = frozen_plan(identity_root, builds=builds)["campaign"]
    p["plan_hash"] = plan.plan_hash(p)
    run_dir = base / "runs" / p["run_id"]
    plan.confirm(run_dir, p)
    monkeypatch.setattr(preflight, "check", lambda *args: None)
    return identity_root, base, run_dir


def _run_campaign_cli(fixture):
    from harness_bench import cli, views

    root, base, run_dir = fixture
    code = cli.main(["--root", str(root), "--runs", str(base / "runs"), "--cells-root", str(base / "cells"),
                     "--tools-dir", str(base / "tools"), "run", run_dir.name])
    return code, views.rows(run_dir, "events")


def test_bench_run_stops_on_a_drifted_run_side_file(confirmed_campaign_run):  # T-25, real wiring
    root, _, _ = confirmed_campaign_run
    write_source(root, "engine.py", "edited after confirmation")
    code, rows = _run_campaign_cli(confirmed_campaign_run)
    stops = [row for row in rows if row["kind"] == "run.launch_stopped"]

    assert code == 3
    assert stops and stops[-1]["code"] == "HB-IDN-001" and stops[-1]["diff"] == ["engine.py changed"]
    assert not any(row["kind"] == "cell.launch_intent" for row in rows)


def test_bench_run_without_drift_launches(confirmed_campaign_run):  # T-25b, own no-drift twin
    _, rows = _run_campaign_cli(confirmed_campaign_run)

    assert sum(row["kind"] == "cell.launch_intent" for row in rows) == 1
    assert not any(row["kind"] == "run.launch_stopped" and row["code"] == "HB-IDN-001" for row in rows)
