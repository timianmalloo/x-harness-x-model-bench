"""US-13: the operator's user-level configuration is not an unmeasured treatment in a cell (spec US-13; finding N5).

Per harness, two turns with the same prompt, which names no canary:
- the probe is a real cell: the seeded per-cell home and the cell environment, exactly as the engine runs it;
- the control adds the operator's user-level configuration: copies of the user instruction file and user skills in
  its home, and the operator's real USERPROFILE/HOME.
The canaries are the operator's own user-level skill names and the first line of the user instruction file. Each is
searched for in the turn's native record (which holds the reply). A canary the control shows must not appear in the
probe; a class the control does not show is void for that harness and is reported. Nothing is written to the
operator's profile: the control's home is a copy, under a folder outside the profile.
"""

import os
import shutil
from pathlib import Path

import pytest

from harness_bench import driver, procs, profiles, tools

pytestmark = [pytest.mark.native, pytest.mark.credentials]
ROOT = Path(__file__).resolve().parents[2]
USER = Path.home()
PROMPT = ("List the name of every skill available to you, one per line. Then quote verbatim the first line of every "
          "instruction file you were given, at user or project level. Write NONE for a part you have nothing for. "
          "Do not run any tool and do not read any file.")
MODELS = {"claude-code": "claude-sonnet-5", "codex": "gpt-6-sol"}


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


def _turn(harness: str, folder: Path, control: bool) -> str:
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
    cell = procs.spawn(p.argv(build), cwd=str(ws), env=env)
    try:
        result = driver.run_turn(cell, cwd=ws, prompt=PROMPT, mode=p.mode, handshake_timeout=60, before_send=lambda sid: None)
    finally:
        cell.close()  # the job is closed: kill on close
        p.clean_home(home)
    assert result.stop_reason == "end_turn", (harness, control, result.cause, result.detail)
    records = p.native_records(home, result.session_id or "")
    assert records, f"{harness}: no native record"
    return "\n".join(r.read_text(encoding="utf-8", errors="replace") for r in records)


class Leaked(AssertionError):
    """The one failure the N5 xfail may absorb. Any other error on the Codex path fails the test (Test Architect N2)."""


N5 = pytest.mark.xfail(strict=True, raises=Leaked, reason="N5 open (docs/notes/spike-n5-codex-skill-roots.md): Codex 0.156 still reads "
                                           "~/.agents/skills into a cell. Tried and confirmed ineffective by a real canary "
                                           "run: a per-cell USERPROFILE/HOME (reverted before this spike), and "
                                           "features.skip_host_skill_discovery=true in the per-cell config.toml (this spike, "
                                           "2026-09-24); a third party independently reports the same flag plus "
                                           "--ignore-user-config/--ignore-rules/project_doc_max_bytes=0 also fail on 0.154.0. "
                                           "strict, so a real fix turns this red until the mark is removed")


@pytest.mark.parametrize("harness", ["claude-code", pytest.param("codex", marks=N5)])
def test_user_level_configuration_does_not_reach_a_cell(harness, base, capsys):
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
