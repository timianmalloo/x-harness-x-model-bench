"""PROBE-FIX-2: four Leader rulings on the dev-probe re-grade (devprobe-rerun-1, 2026-10-12).

A. The Claude Code `[1m]` pin: an exact alias so the API id the transcript records passes HB-VAL-002.
B. agy effort from the served `init.model` suffix (DR option a).
C. Grok grants the in-profile tool classes in its own config, so it never asks (the driver cancels every request).
D. (Leader ruling on the item-D decision request: option a) Claude's served context is the adapter's authoritative
   window only, the size on the usage_update sent after the turn's result; the in-turn sizes are its seed. Two different
   authoritative sizes are still HB-VAL-010.

Fixtures `fixtures/claude/timelines/<run>-<cell>.jsonl`: the driver's acp-timeline.jsonl of each Claude cell of
devprobe-rerun-1 and ccprobe-rerun-1 (2026-10-12, all pinned claude-opus-5-5[1m] / 1000000), copied as archived. The
driver keeps kinds, counts and numbers only, never content (driver.py `_Timeline`).
"""

import json
import shutil
import tomllib
from pathlib import Path

import pytest
from test_profiles_new import _launch

from harness_bench import plan, profiles, views
from harness_bench.telemetry import agy, claude_code, is_not_recorded, normalize

ROOT = Path(__file__).resolve().parents[1]
CACHED = Path(__file__).parent / "fixtures" / "agy" / "reader" / "cached" / "agy-stream.ndjson"
CLAUDE = Path(__file__).parent / "fixtures" / "claude"
TIMELINES = sorted((CLAUDE / "timelines").glob("*.jsonl"))
# the authoritative usage_update's line in each timeline (the line before the session/prompt response)
AUTHORITATIVE_LINE = {"ccprobe-rerun-1-064f07e54d32cf90": 43, "ccprobe-rerun-1-1e22622c83b99ea9": 44,
                      "ccprobe-rerun-1-30a7033cfebb7f1d": 45, "ccprobe-rerun-1-f9764703fecf87bf": 37,
                      "devprobe-rerun-1-064f07e54d32cf90": 41, "devprobe-rerun-1-30a7033cfebb7f1d": 41}
CC_PIN, CC_API = "claude-opus-5-5[1m]", "claude-opus-5-5"


# --- A. the Claude Code [1m] pin -------------------------------------------------------------------------------------

def test_the_claude_code_profile_allows_the_api_id_of_the_1m_pin_exactly():
    p = profiles.load(ROOT, "claude-code")
    assert profiles.model_allowed(CC_API, CC_PIN, p.auxiliary_models, p.model_aliases)
    assert not profiles.model_allowed("claude-opus-5-5-fast", CC_PIN, p.auxiliary_models, p.model_aliases)
    assert not profiles.model_allowed(CC_API, "claude-opus-5-6[1m]", p.auxiliary_models, p.model_aliases)


def test_the_plan_freezes_the_claude_code_alias():
    assert plan.profile_record(ROOT, "claude-code")["model_aliases"] == {CC_PIN: [CC_API]}


# --- B. agy effort from the served model id --------------------------------------------------------------------------

def test_agy_effort_is_the_served_init_model_suffix():
    ex = agy.read(CACHED)  # the probe's agy-off stream: init.model gemini-3.8-flash-high
    assert ex.served.effort == "high"
    assert ex.served.sources["effort"] == "agy-stream.ndjson init.model suffix"


@pytest.mark.parametrize("model, effort", [("gemini-3.8-flash-low", "low"), ("gemini-3.8-flash-medium", "medium"),
                                           ("gemini-3.8-flash-high", "high"), ("gemini-3.8-flash", None),
                                           ("gemini-3.8-flash-highest", None)])
def test_agy_effort_reads_only_an_exact_level_suffix(tmp_path, model, effort):
    stream = tmp_path / "agy-stream.ndjson"
    stream.write_text(CACHED.read_text(encoding="utf-8").replace("gemini-3.8-flash-high", model), encoding="utf-8")
    served = agy.read(stream).served
    if effort is None:
        assert is_not_recorded(served.effort) and "effort" not in served.sources
    else:
        assert (served.effort, served.sources["effort"]) == (effort, "agy-stream.ndjson init.model suffix")


# --- C. Grok grants the in-profile classes and denies the rest -------------------------------------------------------

def test_grok_config_allows_the_profile_classes_and_denies_web_and_mcp(tmp_path):
    _, _, home, _, _ = _launch("grok", tmp_path)
    config = tomllib.loads((home / ".grok" / "config.toml").read_text(encoding="utf-8"))
    assert config["cli"]["auto_update"] is False
    assert sorted(config["permission"]["allow"]) == ["Bash", "Edit", "Glob", "Grep", "Read", "Write"]
    assert sorted(config["permission"]["deny"]) == ["MCPTool", "WebFetch", "WebSearch"]


# --- D. Claude's served window is the adapter's authoritative (post-result) size -------------------------------------

def _cell_home(tmp_path: Path, timeline_lines: list[str]) -> Path:
    """A cell home as the engine leaves it: home/projects/<slug>/<session>.jsonl, the driver's timeline at home."""
    record = tmp_path / "home" / "projects" / "C--cells-a-ws" / "s.jsonl"
    record.parent.mkdir(parents=True)
    shutil.copyfile(CLAUDE / "rerun-1m-settings.jsonl", record)
    (tmp_path / "home" / "acp-timeline.jsonl").write_text("".join(f"{line}\n" for line in timeline_lines),
                                                         encoding="utf-8")
    return record


def _context_rows(record: Path) -> list[dict]:
    return [r for r in normalize.served_rows("run", "a", "s", claude_code.read(record), "x")
            if r["field"] == "context_tokens"]


def _judge(rows: list[dict]):
    # effort "default": Claude declares no default_serves, so only the context is judged here
    cell = {"cell_id": "a", "harness": "claude-code", "model": CC_PIN, "effort": "default", "context": "1000000"}
    prof = plan.profile_record(ROOT, "claude-code")
    rows = rows +[{"field": "model_served", "value": CC_API, "not_recorded": None, "source": "transcript"}]
    mismatch, unrecorded = views._served_settings(cell, prof, rows)
    got = views._validity(cell, prof, {"outcome": "completed", "cause": None}, "completed", {CC_API},
                          settings=mismatch, model_served=views._model_served(rows))
    return got, mismatch, [w.code for w in unrecorded]


@pytest.mark.parametrize("timeline", TIMELINES, ids=[t.stem for t in TIMELINES])
def test_the_probes_claude_window_is_the_authoritative_1000000_only(tmp_path, timeline):
    rows = _context_rows(_cell_home(tmp_path, timeline.read_text(encoding="utf-8").splitlines()))
    assert [(r["value"], r["source"]) for r in rows if r["not_recorded"] is None] == [
        (1_000_000, f"acp-timeline.jsonl:usage_update.size@{AUTHORITATIVE_LINE[timeline.stem]}")]


@pytest.mark.parametrize("timeline", TIMELINES, ids=[t.stem for t in TIMELINES])
def test_the_probes_claude_cells_are_valid_under_the_1m_pin(tmp_path, timeline):
    rows = _context_rows(_cell_home(tmp_path, timeline.read_text(encoding="utf-8").splitlines()))
    assert _judge(rows)[0] == ("valid", None)


def _line(kind: str, method: str = "session/update", size: int | None = None) -> str:
    row = {"first_mono_ns": 1, "last_mono_ns": 1, "count": 1, "method": method, "update_kind": kind, "tool_call_id": None}
    return json.dumps(row | ({"used": 900, "size": size} if size is not None else {}))


PROMPT, RESPONSE = _line("sent", "session/prompt"), _line("response", "session/prompt")


def test_a_turn_with_only_seed_sizes_records_no_window(tmp_path):
    # the turn's last update before the response is a message chunk: no post-result usage_update reached the client
    lines = [PROMPT, _line("usage_update", size=200_000), _line("agent_message_chunk"), RESPONSE]
    rows = _context_rows(_cell_home(tmp_path, lines))
    assert [(r["value"], r["not_recorded"]) for r in rows] == [
        (None, "not recorded: no authoritative window (adapter seed only)")]
    assert _judge(rows)[2] == ["HB-VAL-011"]


def test_a_turn_that_never_ends_records_no_window(tmp_path):
    rows = _context_rows(_cell_home(tmp_path, [PROMPT, _line("usage_update", size=1_000_000)]))
    assert [(r["value"], r["not_recorded"]) for r in rows] == [
        (None, "not recorded: no authoritative window (adapter seed only)")]


def test_two_different_authoritative_sizes_are_hb_val_010(tmp_path):
    # two turns, each closed by its post-result update: a genuine disagreement, so the 200000 one is HB-VAL-010
    lines = [PROMPT, _line("usage_update", size=200_000), RESPONSE,
             PROMPT, _line("usage_update", size=1_000_000), RESPONSE]
    rows = _context_rows(_cell_home(tmp_path, lines))
    assert [(r["value"], r["source"]) for r in rows if r["not_recorded"] is None] == [
        (200_000, "acp-timeline.jsonl:usage_update.size@2"), (1_000_000, "acp-timeline.jsonl:usage_update.size@5")]
    got, mismatch, _ = _judge(rows)
    assert got == ("invalid (setting mismatch)", "HB-VAL-010")
    assert mismatch.message == "context served 200000, expected 1000000 (pinned) from acp-timeline.jsonl:usage_update.size@2"
