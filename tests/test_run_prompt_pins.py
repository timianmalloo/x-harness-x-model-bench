"""Prompt 1 (docs/benchmarkpromps/lean-benchmark-run-prompt.html) and the profiles it pins against (plan rows A2-A5).

The prompt is the operator's only entry point to a lean run, so the facts it states about the bench are checked here
against the bench: the pinned windows are values the profiles accept (a drift made the 2026-10-13 Codex cells serve 500k
and the session read "else default"), every repo command is absolute (the session starts in a folder without the pack),
the hand-off carries the session index and transcript, and the Copilot transport control's combos still plan.
"""
import html
import re
from pathlib import Path

import yaml

from harness_bench import config, plan, profiles

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "docs/benchmarkpromps/lean-benchmark-run-prompt.html").read_text(encoding="utf-8")
PROMPT = html.unescape(re.search(r'<pre id="prompt">(.*?)</pre>', PAGE, re.DOTALL).group(1))


RAW_TAG = re.compile(r"<[A-Za-z/!]")  # in a <pre> the browser reads this as markup and "Copy prompt" drops it


def raw_tags_in_pre(page: str) -> list[str]:
    return [m.group(0) + body[m.end():m.end() + 30] for body in re.findall(r"<pre[^>]*>(.*?)</pre>", page, re.DOTALL)
            for m in RAW_TAG.finditer(body)]


def test_no_prompt_holds_a_raw_tag_inside_its_pre_blocks():
    """2026-10-14: a raw `<absolute script>` in Prompt 1's <pre> was eaten by the browser, so the copy read `python `."""
    pages = sorted((ROOT / "docs/benchmarkpromps").glob("*.html"))
    assert len(pages) >= 3  # the headless pair and the interactive page
    for page in pages:
        assert raw_tags_in_pre(page.read_text(encoding="utf-8")) == [], page.name


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


def test_the_copilot_transport_control_combos_validate_and_plan():
    """Plan row A3: the page's control pair (`-p` and `transport: acp`, both at context default) is a matrix the bench
    accepts, so the operator never edits a profile or builds.yaml to run it."""
    control = yaml.safe_load(html.unescape(re.search(r'<pre id="control"[^>]*>(.*?)</pre>', PAGE, re.DOTALL).group(1)))
    m = {"schema": "bench-matrix/3", "ring": {"tag": "lean"}, "bom": {"file": "bench/bom.yaml", "subset": ["S1"]},
         "repetitions": 1, "arms": [{"id": "off"}, {"id": "on"}], "comparisons": [["off", "on"]], **control}
    bom, problems = config.load_yaml(ROOT / "bench/bom.yaml"), config.Problems()
    config.validate_matrix(m, bom, problems, "control")
    assert problems.items == []
    plan.require_combo_settings(ROOT, m, plan.select_tasks(bom, ["S1"]))
    assert sorted(c.get("transport") or "-p" for c in m["combos"]) == ["-p", "acp"]
