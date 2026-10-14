"""Prompt 1 (docs/benchmarkpromps/lean-benchmark-run-prompt.html) and the profiles it pins against (plan rows A2-A5).

The prompt is the operator's only entry point to a lean run, so the facts it states about the bench are checked here
against the bench: the pinned windows are values the profiles accept (a drift made the 2026-10-13 Codex cells serve 500k
and the session read "else default"), every repo command is absolute (the session starts in a folder without the pack),
the hand-off carries the session index and transcript, and the Copilot ACP control profile still loads.
"""
import html
import re
import shutil
from pathlib import Path

from harness_bench import profiles

ROOT = Path(__file__).resolve().parents[1]
PROMPT = html.unescape(re.search(r'<pre id="prompt">(.*?)</pre>',
                                 (ROOT / "docs/benchmarkpromps/lean-benchmark-run-prompt.html").read_text(encoding="utf-8"),
                                 re.S).group(1))


def test_pinned_windows_are_values_the_profiles_accept():
    line = next(l for l in PROMPT.splitlines() if l.strip().startswith("PINNED_CONTEXT"))
    pins = dict(re.findall(r"(\w+) (\d+)", line.split("=", 1)[1].split("(")[0]))
    assert set(pins) == {"codex", "copilot"}
    for harness, value in pins.items():
        assert value in profiles.load(ROOT, harness).settings["context"].values, harness


def test_every_repo_command_in_the_prompt_is_absolute_and_the_handoff_carries_the_session():
    commands = [m for l in PROMPT.splitlines() for m in re.findall(r"`([^`]+)`", l)]
    relative = [c for c in commands if re.match(r"(uv run|python docs/|git (pull|rev-parse|merge|worktree|branch)\b)", c)]
    assert relative == []
    for key in ('"session_index"', '"transcript"', '"launch_dir"', "SESSION: <RUN_ID>"):
        assert key in PROMPT, key


def test_the_copilot_acp_control_profile_loads_without_an_adapter(tmp_path):
    (tmp_path / "bench/profiles").mkdir(parents=True)
    shutil.copy(ROOT / "bench/profiles/controls/copilot-acp.yaml", tmp_path / "bench/profiles/copilot.yaml")
    control = profiles.load(tmp_path, "copilot")
    assert "{adapter}" not in control.command and control.settings["context"].values == ("default",)
