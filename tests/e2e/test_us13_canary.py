"""US-13: the operator's user-level configuration is not an unmeasured treatment in a cell (spec US-13; finding N5).

Per harness, two turns with the same prompt, which names no canary:
- the probe is a real cell: the seeded per-cell home and the cell environment, exactly as the engine runs it;
- the Claude Code and Codex controls copy the operator's user-level files and restore USERPROFILE/HOME;
- Copilot uses a FAKE operator profile under the test folder, `<turn>/profile`, whose `.copilot` holds four
  deterministic classes: instructions, skill, hook (writes a marker file), settings model. Every Copilot turn sees
  that profile as USERPROFILE/HOME. The control drops COPILOT_HOME, so Copilot reads the profile's `.copilot` as its
  user level; the probe keeps the engine's COPILOT_HOME, so a class that still arrives came through the profile.
  The un-isolated variant (the probe with COPILOT_HOME dropped) is the probe's observed red.
The native record and the hook marker show which classes reached the control. A class the control does not show is
void and reported; none may appear in the probe. Nothing is written to the operator's profile (~/.copilot, ~/.claude,
~/.agents are only read, by the Claude Code and Codex controls).
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from harness_bench import driver, procs, profiles, tools
from harness_bench.telemetry import Extraction
from harness_bench.telemetry import rows as native_rows

pytestmark = [pytest.mark.native, pytest.mark.credentials]
ROOT = Path(__file__).resolve().parents[2]
USER = Path.home()
PROMPT = ("List the name of every skill available to you, one per line. Then quote verbatim the first line of every "
          "instruction file you were given, at user or project level. Write NONE for a part you have nothing for. "
          "Do not run any tool and do not read any file.")
MODELS = {"claude-code": "claude-sonnet-5", "codex": "gpt-6-sol", "copilot": "gpt-6-sol"}
COPILOT_INSTRUCTION = "HB-US13-COPILOT-INSTRUCTION"
COPILOT_SKILL = "hb-us13-copilot-skill"
COPILOT_HOOK = "HB-US13-COPILOT-HOOK"
COPILOT_HOOK_FILE = "us13-hook-marker.txt"
# The settings canary: advertised by Copilot 1.0.89-1 (tests/fixtures/native/copilot/provenance.json available_model_ids),
# not the pin gpt-6-sol. assume: it is not the unpinned default of a fresh COPILOT_HOME; confirmed by the probe's served
# models, which the test prints; if false, the probe reports a "settings model" leak (a false red, never a false green).
COPILOT_SETTINGS_MODEL = "gpt-6-astra"


def _seed_copilot_control(dot: Path) -> None:
    """Four user-level canaries in `dot`, a fake profile's `.copilot`. The hook writes its marker by absolute path, so it
    fires the same whether Copilot reached `dot` as COPILOT_HOME or through USERPROFILE/HOME."""
    (dot / "copilot-instructions.md").write_text(f"{COPILOT_INSTRUCTION}\n", encoding="utf-8")
    skill = dot / "skills" / COPILOT_SKILL / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(f"---\nname: {COPILOT_SKILL}\ndescription: US-13 isolation canary\n---\n", encoding="utf-8")
    hooks = dot / "hooks"
    hooks.mkdir()
    marker = dot / COPILOT_HOOK_FILE
    (hooks / "us13-canary.json").write_text(json.dumps({"version": 1, "hooks": {"sessionStart": [{
        "type": "command",
        "bash": f"printf '{COPILOT_HOOK}' > '{marker.as_posix()}'",
        "powershell": f"Set-Content -LiteralPath '{marker}' -Value '{COPILOT_HOOK}'",
        "timeoutSec": 10,
    }]}}, indent=2), encoding="utf-8")
    (dot / "settings.json").write_text(json.dumps({"model": COPILOT_SETTINGS_MODEL}), encoding="utf-8")


def _fake_profile(folder: Path) -> Path:
    """`<folder>/profile`, a fake operator profile whose `.copilot` holds the four canaries. Never the operator's own."""
    profile = folder / "profile"
    real = {(USER / name).resolve() for name in ("", ".copilot", ".claude", ".agents")}
    if profile.resolve() in real or (profile / ".copilot").resolve() in real:
        raise AssertionError(f"US-13 would write to the operator's profile: {profile}")
    (profile / ".copilot").mkdir(parents=True)
    _seed_copilot_control(profile / ".copilot")
    return profile


def _copilot_env(p: profiles.Profile, home: Path, build, profile: Path, isolated: bool) -> dict[str, str]:
    """The engine's own cell environment, with USERPROFILE/HOME at the fake profile so a leak through it is visible.
    isolated=False drops COPILOT_HOME (the control, and the probe's red): Copilot then reads `<profile>/.copilot`."""
    env = p.cell_env(dict(os.environ), home, build, MODELS["copilot"], "")
    env.update({"USERPROFILE": str(profile), "HOME": str(profile)})
    if not isolated:
        del env[p.home_env]
    return env


def _copilot_shown(record: str, models: set[str], dot: Path) -> dict[str, bool]:
    marker = dot / COPILOT_HOOK_FILE
    return {
        "instruction": COPILOT_INSTRUCTION in record,
        "skill": COPILOT_SKILL in record,
        "hook": marker.is_file() and marker.read_text(encoding="utf-8-sig").strip() == COPILOT_HOOK,
        "settings model": COPILOT_SETTINGS_MODEL in models,
    }


def _copilot_models(records: list[Path]) -> set[str]:
    """Use the model on each native assistant message; shutdown may not be written before the job closes."""
    models = set()
    for record in records:
        for _, row in native_rows(record, Extraction()):
            data = row.get("data")
            if row.get("type") == "assistant.message" and isinstance(data, dict) and isinstance(data.get("model"), str):
                models.add(data["model"])
    return models


def _user_config(harness: str) -> tuple[list[tuple[Path, str]], dict[str, str]]:
    """(files and folders to copy into the control's home, canary -> class) from the operator's user level."""
    copies, canaries = [], {}
    if harness == "claude-code":
        memory = USER / ".claude" / "CLAUDE.md"
        if memory.is_file():
            copies.append((memory, "CLAUDE.md"))
            first = next((line.strip("# ").strip() for line in memory.read_text(encoding="utf-8").splitlines() if line.strip()), "")
            if first:
                canaries[first] = "instruction file"
        for skill in sorted((USER / ".claude" / "skills").glob("*")):
            if skill.is_dir() and skill.name != "synced":  # synced = account-level skills (R1.4), not a file-level class
                copies.append((skill, f"skills/{skill.name}"))
                canaries[skill.name] = "skill"
    else:
        memory = USER / ".codex" / "AGENTS.md"
        if memory.is_file():
            copies.append((memory, "AGENTS.md"))
    for skill in sorted((USER / ".agents" / "skills").glob("*")):  # N5: a user skills root outside the harness home
        if skill.is_dir():
            canaries[skill.name] = "skill (~/.agents/skills, via USERPROFILE)"
    return copies, canaries


def _run(p: profiles.Profile, argv: list[str], ws: Path, env: dict[str, str], home: Path, records_home: Path,
         label: str) -> list[Path]:
    """One real turn; the native records of its session, found in `records_home`."""
    cell = procs.spawn(argv, cwd=str(ws), env=env)
    try:
        result = driver.run_turn(cell, cwd=ws, prompt=PROMPT, mode=p.mode, handshake_timeout=60, before_send=lambda sid: None)
    finally:
        cell.close()  # the job is closed: kill on close
        p.clean_home(home)
    assert result.stop_reason == "end_turn", (p.harness, label, result.cause, result.detail)
    records = p.native_records(records_home, result.session_id or "")
    assert records, f"{p.harness} {label}: no native record"
    return records


def _text(records: list[Path]) -> str:
    return "\n".join(r.read_text(encoding="utf-8", errors="replace") for r in records)


def _turn(harness: str, folder: Path, control: bool) -> str:
    """A Claude Code or Codex turn; the control copies the operator's user-level files and restores USERPROFILE/HOME."""
    p = profiles.load(ROOT, harness)
    build = tools.resolve(ROOT / ".tools" / "harness")[harness]
    home, ws = folder / "home", folder / "ws"
    ws.mkdir(parents=True)
    p.seed_home(home, MODELS[harness])
    env = p.cell_env(dict(os.environ), home, build, MODELS[harness], "")
    if control:
        for src, rel in _user_config(harness)[0]:
            dest = home / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest) if src.is_dir() else shutil.copyfile(src, dest)
        env.update({k: os.environ[k] for k in ("USERPROFILE", "HOME") if k in os.environ})
    return _text(_run(p, p.argv(build, MODELS[harness]), ws, env, home, home, "control" if control else "probe"))


def _copilot_turn(folder: Path, isolated: bool) -> tuple[dict[str, bool], set[str]]:
    """A Copilot turn under a fake operator profile: (canary class -> shown, served models)."""
    p = profiles.load(ROOT, "copilot")
    build = tools.resolve(ROOT / ".tools" / "harness")["copilot"]
    profile = _fake_profile(folder)
    home, ws = folder / "home", folder / "ws"
    ws.mkdir(parents=True)
    p.seed_home(home, MODELS["copilot"])
    env = _copilot_env(p, home, build, profile, isolated)
    argv = p.argv(build, MODELS["copilot"])
    # Expose the settings model: the normal --model pin has higher precedence than settings.json.
    at = argv.index("--model")
    del argv[at:at + 2]
    records = _run(p, argv, ws, env, home, home if isolated else profile / ".copilot", folder.name)
    models = _copilot_models(records)
    return _copilot_shown(_text(records), models, profile / ".copilot"), models


def _assert_isolated(shown: dict[str, bool], models: set[str]) -> None:
    """The probe's check. A served model must be recorded, or the settings-model class passes vacuously."""
    assert models, "Copilot probe: no served model recorded, so the settings-model canary proves nothing"
    leaked = [name for name, present in shown.items() if present]
    if leaked:
        raise Leaked(f"user-level Copilot configuration reached an isolated cell: {leaked}; served models {sorted(models)} "
                     f"(settings canary {COPILOT_SETTINGS_MODEL})")


class Leaked(AssertionError):
    """The one failure the N5 xfail may absorb. Any other error on the Codex path fails the test (Test Architect N2)."""


N5 = pytest.mark.xfail(strict=True, raises=Leaked, reason="N5 open (docs/notes/spike-n5-codex-skill-roots.md): Codex 0.156 still reads "
                                           "~/.agents/skills into a cell. Tried and confirmed ineffective by a real canary "
                                           "run: a per-cell USERPROFILE/HOME (reverted before this spike), and "
                                           "features.skip_host_skill_discovery=true in the per-cell config.toml (this spike, "
                                           "2026-09-24); a third party independently reports the same flag plus "
                                           "--ignore-user-config/--ignore-rules/project_doc_max_bytes=0 also fail on 0.154.0. "
                                           "strict, so a real fix turns this red until the mark is removed")


@pytest.mark.parametrize("harness", ["claude-code", pytest.param("codex", marks=N5), "copilot"])
def test_user_level_configuration_does_not_reach_a_cell(harness, base, capsys):
    if harness == "copilot":
        canaries, control_models = _copilot_turn(base / "control", isolated=False)
        probe, probe_models = _copilot_turn(base / "probe", isolated=True)
        void = [name for name, shown in canaries.items() if not shown]
        with capsys.disabled():
            print(f"\nUS-13 copilot: shown by the control {sorted(name for name in canaries if name not in void)}; "
                  f"void (control did not show) {void}; leaked into the probe {[n for n, s in probe.items() if s]}; "
                  f"served models: control {sorted(control_models)}, probe {sorted(probe_models)}")
        assert not void, f"Copilot canary classes void because the control did not show them: {void}"
        _assert_isolated(probe, probe_models)
        return

    _, canaries = _user_config(harness)
    if not canaries:
        pytest.skip(f"no user-level canary exists for {harness} on this host")
    control = _turn(harness, base / "control", control=True)
    probe = _turn(harness, base / "probe", control=False)
    shown = {c: cls for c, cls in canaries.items() if c in control}
    void = {c: cls for c, cls in canaries.items() if c not in control}
    leaked = {c: cls for c, cls in shown.items() if c in probe}
    with capsys.disabled():
        print(f"\nUS-13 {harness}: shown by the control {sorted(shown.values())}; void (control did not show) {sorted(void.values())}; "
              f"leaked into the probe {sorted(leaked.values())}; leaked items {sorted(leaked)}")  # items: ruling R-6 condition 3
    # the positive control: a probe that shows nothing proves nothing unless the control showed a canary (spec US-13)
    assert shown, f"{harness}: the control showed no canary, so the probe's result is void"
    if leaked:
        raise Leaked(f"user-level configuration reached a {harness} cell: {sorted(leaked.items())}")


def test_copilot_probe_without_copilot_home_goes_red(base, capsys):
    """The probe's observed red (Test Architect, W1-COP-I join): the engine's cell environment with only COPILOT_HOME
    dropped. Copilot then reads the fake profile, and the probe's own check must raise Leaked naming every class.
    If it does not, the probe cannot fail, and its green in the test above proves nothing."""
    shown, models = _copilot_turn(base / "unisolated", isolated=False)
    with pytest.raises(Leaked) as red:
        _assert_isolated(shown, models)
    with capsys.disabled():
        print(f"\nUS-13 copilot, COPILOT_HOME dropped (the probe's red): {red.value}")
    assert all(shown.values()), f"the un-isolated probe did not show every class: {shown}"
