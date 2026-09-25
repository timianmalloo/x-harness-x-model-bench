"""US-13: the operator's user-level configuration is not an unmeasured treatment in a cell (spec US-13; finding N5).

Per harness, two turns with the same prompt, which names no canary:
- the probe is a real cell: the seeded per-cell home and the cell environment, exactly as the engine runs it;
- the Claude Code and Codex controls copy the operator's user-level files and restore USERPROFILE/HOME;
- the Copilot control seeds four deterministic classes under COPILOT_HOME: instructions, skill, hook, model setting.
The native record and the hook marker show which classes reached the control. A class the control does not show is
void and reported; none may appear in the probe. Nothing is written to the operator's profile.
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


def _seed_copilot_control(home: Path) -> None:
    """Four user-level canaries under COPILOT_HOME; no operator profile is changed."""
    (home / "copilot-instructions.md").write_text(f"{COPILOT_INSTRUCTION}\n", encoding="utf-8")
    skill = home / "skills" / COPILOT_SKILL / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(f"---\nname: {COPILOT_SKILL}\ndescription: US-13 isolation canary\n---\n", encoding="utf-8")
    hooks = home / "hooks"
    hooks.mkdir()
    (hooks / "us13-canary.json").write_text(json.dumps({"version": 1, "hooks": {"sessionStart": [{
        "type": "command",
        "bash": f"printf '{COPILOT_HOOK}' > \"$COPILOT_HOME/{COPILOT_HOOK_FILE}\"",
        "powershell": f"Set-Content -LiteralPath (Join-Path $env:COPILOT_HOME '{COPILOT_HOOK_FILE}') "
                      f"-Value '{COPILOT_HOOK}'",
        "timeoutSec": 10,
    }]}}, indent=2), encoding="utf-8")
    (home / "settings.json").write_text(json.dumps({"model": MODELS["copilot"]}), encoding="utf-8")


def _copilot_shown(record: str, models: set[str], home: Path) -> dict[str, bool]:
    marker = home / COPILOT_HOOK_FILE
    return {
        "instruction": COPILOT_INSTRUCTION in record,
        "skill": COPILOT_SKILL in record,
        "hook": marker.is_file() and marker.read_text(encoding="utf-8").strip() == COPILOT_HOOK,
        "settings model": MODELS["copilot"] in models,
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


def _turn(harness: str, folder: Path, control: bool) -> tuple[str, set[str]]:
    p = profiles.load(ROOT, harness)
    build = tools.resolve(ROOT / ".tools" / "harness")[harness]
    home, ws = folder / "home", folder / "ws"
    ws.mkdir(parents=True)
    p.seed_home(home, MODELS[harness])
    env = p.cell_env(dict(os.environ), home, build, MODELS[harness], "")
    if control:
        if harness == "copilot":
            _seed_copilot_control(home)
        else:
            for src, rel in _user_config(harness)[0]:
                dest = home / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dest) if src.is_dir() else shutil.copyfile(src, dest)
            env.update({k: os.environ[k] for k in ("USERPROFILE", "HOME") if k in os.environ})
    argv = p.argv(build, MODELS[harness])
    if harness == "copilot":
        # Expose the settings model: the normal --model pin has higher precedence than settings.json.
        at = argv.index("--model")
        del argv[at:at + 2]
    cell = procs.spawn(argv, cwd=str(ws), env=env)
    try:
        result = driver.run_turn(cell, cwd=ws, prompt=PROMPT, mode=p.mode, handshake_timeout=60, before_send=lambda sid: None)
    finally:
        cell.close()  # the job is closed: kill on close
        p.clean_home(home)
    assert result.stop_reason == "end_turn", (harness, control, result.cause, result.detail)
    records = p.native_records(home, result.session_id or "")
    assert records, f"{harness}: no native record"
    text = "\n".join(r.read_text(encoding="utf-8", errors="replace") for r in records)
    models = _copilot_models(records) if harness == "copilot" else set()
    return text, models


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
        control, control_models = _turn(harness, base / "control", control=True)
        probe, probe_models = _turn(harness, base / "probe", control=False)
        canaries = _copilot_shown(control, control_models, base / "control" / "home")
        void = [name for name, shown in canaries.items() if not shown]
        leaked = [name for name, present in _copilot_shown(probe, probe_models, base / "probe" / "home").items() if present]
        with capsys.disabled():
            print(f"\nUS-13 copilot: shown by the control {sorted(name for name in canaries if name not in void)}; "
                  f"void (control did not show) {void}; leaked into the probe {leaked}")
        assert not void, f"Copilot canary classes void because the control did not show them: {void}"
        if leaked:
            raise Leaked(f"user-level Copilot configuration reached an isolated cell: {leaked}")
        return

    _, canaries = _user_config(harness)
    if not canaries:
        pytest.skip(f"no user-level canary exists for {harness} on this host")
    control, _ = _turn(harness, base / "control", control=True)
    probe, _ = _turn(harness, base / "probe", control=False)
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
