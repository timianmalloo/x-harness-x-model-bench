"""R-CONTRACT-RUN (lean re-run, J0): the run-side seams in code, pinned before any wave-1 track builds on them.

Contract: the R-CONTRACT-RUN row of docs/coordination/coordination-lean-rerun.md; ADR-0024 s1-s3, ADR-0025 s1 and s8,
ADR-0028 s1-s3 and s7. Structural only: new names with defaults, placeholder expansion, the transport pick, stubs and
CLI seams. The hard requirement is no behaviour change for any existing run, so two tests pin it directly: the three
existing profiles' `profile_record` hashes, and every existing plan fixture's cell ids (RECID-A).
"""

import importlib
import inspect
import json
import sys
from dataclasses import fields
from pathlib import Path

import pytest

from harness_bench import cli, config, driver, engine, identity, plan, profiles, tools
from harness_bench.errors import BenchError


def _optional(name: str):
    """The new modules, imported so that their absence is an assertion failure in the test that needs them."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


stream_driver = _optional("harness_bench.stream_driver")
grok_reader = _optional("harness_bench.telemetry.grok")
agy_reader = _optional("harness_bench.telemetry.agy")
READERS = [("grok", grok_reader), ("agy", agy_reader)]

ROOT = Path(__file__).resolve().parents[1]
EXISTING = ("claude-code", "codex", "copilot")
# Measured on the J1a candidate (39a43852 + J1A-FIX): identity_hash(plan.profile_record(ROOT, h)), after R-SETTINGS froze
# `settings` (claude-code 32e06b14..7bca and codex 57701845..fe56, as it reported) and R-COPILOT-P changed copilot.
PROFILE_RECORD_HASHES = {
    "claude-code": "48a8adf21c80e74725c5c31e7821ef3d5c3ec7d11430ad6ee23e1f969cd439a0",  # PROBE-FIX-2 A: model_aliases
    # fix/codex-profile-0160, deliberate: codex.yaml now names the frozen 0.160.0 catalog (sha256-pinned, no collaboration
    # tools outside scenario 6), turns plugins and remote_plugin off, and declares no default context (was 5770184..fe56)
    "codex": "b3bca6d16523d366716c3c19d457b7aea3b3bafeea9aa37ad55d821156248e57",
    "copilot": "62a87c27b83a9c9ec291139e6b8301ee1f2528b5631ade7bec19138a47766eac",
}
# The new fields each existing profile now sets (R-SETTINGS: settings, Claude's session_meta; Ruling 120: copilot -p
# cannot answer a scripted user); every other new field is still at its default.
SET_BY_WAVE_1 = {"claude-code": {"settings", "session_meta", "model_aliases"}, "codex": {"settings"}, "copilot": {"settings", "scripted_user"}}
NEW_FIELDS = {"settings": {}, "transport": "acp", "session_meta": {}, "user_home_vars": (), "seed_files": {},
              "credential_home_env": None, "model_aliases": {}, "scripted_user": "supported"}
FIXTURE_PROFILE = """\
harness: codex
vendor: xai
home_env: GROK_HOME
credential: null
record_glob: "sessions/{session_id}/*.jsonl"
shutdown_grace_seconds: 5
transport: agy-stream
session_meta: {thinking: {display: summarized}}
user_home_vars: [HOME, USERPROFILE]
seed_files: {".grok/trusted_folders.toml": "x"}
credential_home_env: HB_GROK_CRED_HOME
model_aliases: {grok-4.7: [grok-4.7-build]}
scripted_user: unsupported
settings:
  effort: {values: [low, high], apply: placeholder, default_serves: medium}
  context: {values: [default, 922000], apply: placeholder, default_serves: 272000,
            args: {default: [], "922000": ["--context", "long_context"]}}
command: ["{python}", "{exe}", "--reasoning-effort", "{effort}", "{context_arg}", "--log-dir", "{home}/logs", "--model", "{model}"]
env: {EFFORT: "{effort}", WINDOW: "{context_tokens}", HOME: "{home}"}
files: {"config.toml": "effort = \\"{effort}\\"\\nwindow = {context_tokens}"}
"""


def _fixture_root(tmp_path: Path, text: str = FIXTURE_PROFILE) -> Path:
    (tmp_path / "bench" / "profiles").mkdir(parents=True)
    (tmp_path / "bench" / "profiles" / "codex.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def _build(tmp_path: Path) -> tools.Build:
    return tools.Build("grok", "1.0.41", tmp_path / "grok.exe", "0" * 64, None, None, None)


# --- profiles: names, defaults, and the three existing profiles unchanged ---------------------------------------

@pytest.mark.parametrize("harness", EXISTING)
def test_existing_profiles_parse_every_new_field_to_its_default(harness):
    p = profiles.load(ROOT, harness)
    still_default = {name: value for name, value in NEW_FIELDS.items() if name not in SET_BY_WAVE_1[harness]}
    assert {name: getattr(p, name) for name in still_default} == still_default
    assert all(getattr(p, name) != NEW_FIELDS[name] for name in SET_BY_WAVE_1[harness])


def test_profile_field_names_and_hand_built_defaults():
    names = [f.name for f in fields(profiles.Profile)]
    assert names[-len(NEW_FIELDS):] == list(NEW_FIELDS)
    p = profiles.Profile("h", "H_HOME", None, None, ("{exe}",))
    assert {name: getattr(p, name) for name in NEW_FIELDS} == NEW_FIELDS


@pytest.mark.parametrize("harness", EXISTING)
def test_existing_profile_record_hashes_are_unchanged(harness):
    assert identity.identity_hash(plan.profile_record(ROOT, harness)) == PROFILE_RECORD_HASHES[harness]


def test_a_settings_block_and_the_new_keys_parse(tmp_path):
    p = profiles.load(_fixture_root(tmp_path), "codex")
    assert p.transport == "agy-stream"
    assert p.session_meta == {"thinking": {"display": "summarized"}}
    assert p.user_home_vars == ("HOME", "USERPROFILE")
    assert p.seed_files == {".grok/trusted_folders.toml": "x"}
    assert p.credential_home_env == "HB_GROK_CRED_HOME"
    assert p.model_aliases == {"grok-4.7": ("grok-4.7-build",)}
    assert p.scripted_user == "unsupported"
    assert p.settings["effort"] == profiles.Setting(values=("low", "high"), apply="placeholder", default_serves="medium")
    assert p.settings["context"] == profiles.Setting(values=("default", "922000"), apply="placeholder",
                                                     default_serves=272000,
                                                     args={"default": (), "922000": ("--context", "long_context")})


@pytest.mark.parametrize(("key", "value"), [
    ("transport", "ws"), ("scripted_user", "maybe"), ("settings", "{speed: {values: [x], apply: none}}"),
    ("settings", "{effort: {values: [x], apply: argv}}"), ("user_home_vars", "HOME"),
])
def test_a_bad_new_key_is_refused(tmp_path, key, value):
    text = "\n".join(line for line in FIXTURE_PROFILE.splitlines()
                     if not line.startswith((f"{key}:", "  effort:", "  context:", "            args:"))) + f"\n{key}: {value}\n"
    with pytest.raises(BenchError) as err:
        profiles.load(_fixture_root(tmp_path, text), "codex")
    assert err.value.code == "HB-USR-002"


# --- placeholder expansion ---------------------------------------------------------------------------------------

def test_effort_high_reaches_argv_env_and_a_seeded_file(tmp_path):
    p = profiles.load(_fixture_root(tmp_path), "codex")
    home = tmp_path / "home"
    argv = p.argv(_build(tmp_path), "grok-4.7", effort="high", context="922000", home=home)
    assert argv == [sys.executable, str(tmp_path / "grok.exe"), "--reasoning-effort", "high", "--context", "long_context",
                    "--log-dir", f"{home}/logs", "--model", "grok-4.7"]
    env = p.cell_env({}, home, _build(tmp_path), "grok-4.7", "", effort="high", context="922000")
    assert (env["EFFORT"], env["WINDOW"], env["HOME"]) == ("high", "922000", str(home))
    p.seed_home(home, "grok-4.7", effort="high", context="922000")
    assert (home / "config.toml").read_text(encoding="utf-8") == 'effort = "high"\nwindow = 922000\n'


def test_context_arg_default_drops_its_argv_element(tmp_path):
    p = profiles.load(_fixture_root(tmp_path), "codex")
    argv = p.argv(_build(tmp_path), "m", effort="low", context="default", home=tmp_path)
    assert "{context_arg}" not in argv and "--context" not in argv
    assert argv[2:5] == ["--reasoning-effort", "low", "--log-dir"]


def test_context_arg_with_no_context_setting_drops_for_default(tmp_path):
    p = profiles.Profile("codex", "H", None, None, ("{exe}", "{context_arg}", "--x"))
    assert p.argv(_build(tmp_path)) == [str(tmp_path / "grok.exe"), "--x"]


def test_a_context_value_with_no_argv_mapping_is_refused(tmp_path):
    p = profiles.load(_fixture_root(tmp_path), "codex")
    with pytest.raises(BenchError) as err:
        p.argv(_build(tmp_path), "m", effort="low", context="128000", home=tmp_path)
    assert err.value.code == "HB-USR-002"


def test_default_never_leaks_a_literal_placeholder(tmp_path):
    """`default` expands nothing; a profile that still holds `{effort}` for a `default` cell is refused, never launched
    with the literal text (the plan-time refusal of an unsupported value is R-SETTINGS's)."""
    p = profiles.load(_fixture_root(tmp_path), "codex")
    with pytest.raises(BenchError) as err:
        p.argv(_build(tmp_path), "m", effort="default", context="default", home=tmp_path)
    assert err.value.code == "HB-USR-002"


def test_copilot_p_refuses_a_default_effort_never_launching_the_literal(tmp_path):
    """R-COPILOT-P (Ruling 120): copilot -p's command carries `{effort}`, so `default` is refused, never launched with
    the placeholder text; it is the one existing profile whose default launch changed."""
    p = profiles.load(ROOT, "copilot", credential_source=tmp_path / "absent")
    build = tools.Build("copilot", "1", tmp_path / "x.exe", "0" * 64, tmp_path / "adapter.js", "1", "0" * 64)
    with pytest.raises(BenchError) as err:
        p.argv(build, "model-x", scenario=6, effort="default", context="default", home=tmp_path)
    assert err.value.code == "HB-USR-002" and "{effort}" in err.value.message


@pytest.mark.parametrize("harness", ("claude-code", "codex"))
def test_default_changes_nothing_for_the_existing_profiles(tmp_path, harness):
    p = profiles.load(ROOT, harness, credential_source=tmp_path / "absent")
    build = tools.Build(harness, "1", tmp_path / "x.exe", "0" * 64, tmp_path / "adapter.js", "1", "0" * 64)
    base = {"PATH": "p", "CLAUDE_CODE_EFFORT_LEVEL": "x"}
    old_argv = p.argv(build, "model-x", scenario=6)
    assert p.argv(build, "model-x", scenario=6, effort="default", context="default", home=tmp_path) == old_argv
    assert p.cell_env(base, tmp_path, build, "model-x", "tp", effort="default", context="default") == \
        p.cell_env(base, tmp_path, build, "model-x", "tp")
    # fix/codex-profile-0160: a model the frozen codex catalog has; seed_home refuses one it lacks
    p.seed_home(tmp_path / "a", "gpt-6.1-sol", 6)
    p.seed_home(tmp_path / "b", "gpt-6.1-sol", 6, effort="default", context="default")
    assert {f.name: f.read_bytes() for f in (tmp_path / "a").iterdir()} == \
        {f.name: f.read_bytes() for f in (tmp_path / "b").iterdir()}


def test_profile_launcher_reads_the_cell_settings(tmp_path):
    p = profiles.load(_fixture_root(tmp_path), "codex")
    launcher = profiles.ProfileLauncher(p, tmp_path, {})
    launcher.build = _build(tmp_path)
    assert launcher.transport == "agy-stream"
    argv, env = launcher.argv_env({"model": "m", "effort": "high", "context": "922000"}, tmp_path / "h", "")
    assert "high" in argv and "long_context" in argv and env["EFFORT"] == "high"
    launcher.seed(tmp_path / "h", {"model": "m", "effort": "high", "context": "922000"})
    assert 'effort = "high"' in (tmp_path / "h" / "config.toml").read_text(encoding="utf-8")


# --- plan: Cell settings, cell ids, harness_parallelism ----------------------------------------------------------

def _cell(**kw):
    base = {"task": "X1", "task_version": "v1", "scenario": 5, "combo": "c", "harness": "codex", "model": "m",
            "arm": "on", "rep": 1, "budget_seconds": 300}
    return plan.Cell(**{**base, **kw})


def test_cell_settings_default_and_the_id_recipe():
    c = _cell()
    assert (c.effort, c.context) == ("default", "default")
    import hashlib

    from harness_bench.ledger import canonical
    old = hashlib.sha256(canonical({"task_version": "v1", "combo": "c", "pack": "on", "rep": 1})).hexdigest()[:16]
    assert c.id == old
    assert _cell(effort="high").id != old and _cell(context=922000).id != old
    assert _cell(effort="high").id != _cell(context="high").id
    assert _cell(effort="high").label == c.label


def test_expand_reads_combo_settings_and_a_v2_matrix_gives_default():
    bom = {"tasks": [{"id": "X1", "scenario": 5, "budget_minutes": 5}]}
    m2 = {"schema": "bench-matrix/2", "bom": {"subset": ["X1"]}, "repetitions": 1, "arms": [{"id": "off"}],
          "combos": [{"id": "c", "harness": "codex", "model": "m"}]}
    assert [(c.effort, c.context) for c in plan.expand(m2, bom)] == [("default", "default")]
    m3 = {**m2, "combos": [{"id": "c", "harness": "codex", "model": "m", "effort": "high", "context": 922000}]}
    assert [(c.effort, c.context) for c in plan.expand(m3, bom)] == [("high", 922000)]


@pytest.mark.parametrize("path", sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests" / "fixtures").rglob("*.json")
                                        if '"task_version"' in p.read_text(encoding="utf-8", errors="replace")
                                        and '"cell_id"' in p.read_text(encoding="utf-8", errors="replace")))
def test_every_existing_plan_fixture_keeps_its_cell_ids(path):
    """RECID-A: every committed plan fixture's real cell ids recompute unchanged (fixtures with placeholder ids such as
    "a" are skipped row by row: they never came from the recipe)."""
    body = json.loads((ROOT / path).read_text(encoding="utf-8"))
    rows = [r for r in body.get("cells", []) if len(r.get("cell_id", "")) == 16]
    for r in rows:
        arm = r.get("arm", r.get("pack"))
        assert _cell(task_version=r["task_version"], combo=r["combo"], arm=arm, rep=r["rep"]).id == r["cell_id"], r


def test_grid4_replan_carries_default_settings_and_an_empty_harness_cap(monkeypatch):
    fixture = json.loads((ROOT / "tests/fixtures/plans/grid4-cells.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(plan, "_probe_instructions", lambda root, cells, *args: (
        {(c.task, c.arm): 0 for c in cells if c.harness == "copilot"}, []))
    from test_plan import _grid4_scripted_user_as_planned

    _grid4_scripted_user_as_planned(monkeypatch)  # grid-4 predates copilot -p's scripted_user: unsupported
    body = plan.build_plan(ROOT, fixture["matrix"], config.load_yaml(ROOT / "bench/bom.yaml"), "grid4-replan",
                           fixture["builds"], fixture["pack"], task_versions=fixture["task_versions"])
    assert {r["cell_id"] for r in body["cells"]} == {r["cell_id"] for r in fixture["cells"]}
    assert {(r["effort"], r["context"]) for r in body["cells"]} == {("default", "default")}
    assert body["harness_parallelism"] == {}
    assert plan.harness_parallelism(body) == {}


def test_harness_parallelism_is_frozen_from_the_matrix_and_old_plans_read_empty():
    assert plan.harness_parallelism({}) == {}
    assert plan.frozen_harness_parallelism({"harness_parallelism": {"grok": 1}}) == {"grok": 1}
    assert plan.frozen_harness_parallelism({}) == {}
    for bad in ({"grok": 0}, {"grok": True}, {"nope": 1}, ["grok"]):
        with pytest.raises(BenchError):
            plan.frozen_harness_parallelism({"harness_parallelism": bad})


# --- engine: the transport pick, and the stubs -------------------------------------------------------------------

def test_attempt_picks_the_protocol_module_by_transport():
    assert stream_driver is not None and hasattr(engine, "protocol_module")

    class Fake:
        pass

    assert engine.protocol_module(Fake()) is driver
    for transport, module in (("acp", driver), ("agy-stream", stream_driver)):
        f = Fake()
        f.transport = transport
        assert engine.protocol_module(f) is module
    source = inspect.getsource(engine.Engine._attempt)
    assert "driver.open_session" not in source.replace("proto.open_session", "")
    assert "driver.send_turn" not in source.replace("proto.send_turn", "")


def test_stream_driver_stub_has_the_driver_signatures():
    assert stream_driver is not None
    for name in ("open_session", "send_turn"):
        assert list(inspect.signature(getattr(stream_driver, name)).parameters) == \
            list(inspect.signature(getattr(driver, name)).parameters)
    for module in (driver, stream_driver):  # R-TRANSPORT: the profile's session_meta on session/new (ADR-0025 s2)
        assert "session_meta" in inspect.signature(module.open_session).parameters


@pytest.mark.parametrize(("harness", "module"), READERS)
def test_the_new_readers_are_the_registered_ones(harness, module):  # R-READ-GROK and R-READ-AGY built the J0 stubs
    assert module is not None, harness
    assert profiles.READERS[harness] is module.read


# --- identity and the CLI seams ----------------------------------------------------------------------------------

def test_identity_classes_name_every_new_file():
    expected = {"stream_driver.py": "run", "telemetry/grok.py": "run", "telemetry/agy.py": "run"}
    assert {name: identity.CLASSES.get(name) for name in expected} == expected
    # R-CONTRACT-FACTS creates the four report modules: each is class grade once its file exists (J0 guard).
    report = ("report/cost_compare.py", "report/pack_cost.py", "report/tool_phases.py", "report/publish.py")
    assert identity.J0_GRADE_FILES == report
    src = ROOT / "src" / "harness_bench"
    assert {n: identity.CLASSES.get(n) for n in report} == {n: "grade" if (src / n).is_file() else None for n in report}


@pytest.mark.parametrize(("argv", "module", "entry"), [
    (["report", "--cost-compare", "r1", "r2", "--out", "o.html", "--open"], "harness_bench.report.cost_compare", "cli_main"),
    (["report", "--pack-cost", "r1", "--out", "o.html", "--analysis", "a.md"], "harness_bench.report.pack_cost", "cli_main"),
    (["tools", "install", "--vendored", "agy.exe"], "harness_bench.tools", "cli_main"),
])
def test_cli_seams_are_one_call_to_the_module_entry(monkeypatch, argv, module, entry):
    seen = []
    monkeypatch.setattr(cli, "_module_entry", lambda m, n="cli_main": (seen.append((m, n)), lambda args: (seen.append(args), 0)[1])[1])
    assert cli.main(argv) == 0
    assert seen[0] == (module, entry)
    args = seen[1]
    if "--out" in argv:
        assert Path(args.out).is_absolute()
    if "--cost-compare" in argv:
        assert (args.cost_compare, args.open) == (["r1", "r2"], True)
    if "--pack-cost" in argv:
        assert (args.pack_cost, args.open, Path(args.analysis).name) == (["r1"], False, "a.md")
    if "--vendored" in argv:
        assert Path(args.vendored).name == "agy.exe"


def test_report_without_a_run_id_or_a_seam_flag_is_still_an_argparse_error(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["report"])
    assert exc.value.code == 2
    assert "run_id" in capsys.readouterr().err


def test_a_missing_seam_module_is_not_implemented():
    with pytest.raises(NotImplementedError):
        cli._module_entry("harness_bench.report.no_such_module")


def test_the_console_window_guard_scans_bench_adapters(tmp_path):
    """tests/test_console_windows.py:14: R-COPILOT-P's adapter lives in bench/adapters/, outside tools/ and tests/."""
    from test_console_windows import _scan_offenders

    (tmp_path / "bench" / "adapters").mkdir(parents=True)
    (tmp_path / "bench" / "adapters" / "a.py").write_text("import subprocess\nsubprocess.Popen(['x'])\n", encoding="utf-8")
    assert _scan_offenders(tmp_path) == ["bench/adapters/a.py:2"]