"""R-92 condition 1: the served model is read from the response rows, never from the summary or from text.

Fixtures under tests/fixtures/grok_sessions are synthetic copies of the real session-store shapes
(chat_history.jsonl `assistant` rows carry `model_id`; usage.json `session.modelUsage` keys; summary.json
`current_model_id`). Each test runs the tool as a subprocess, the way README section 3 runs it.
"""

import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "grok_served_model.py"
FIX = Path(__file__).resolve().parent / "fixtures" / "grok_sessions"
SID = "00000000-0000-4000-8000-000000000001"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, timeout=30, check=False)


def _case(name: str) -> str:
    return str(FIX / name / SID)


def test_all_served_47_exits_0_and_counts_ids():
    r = _run(_case("all_47"))
    assert r.returncode == 0, r.stderr
    assert "grok-4.7-build" in r.stdout and "4" in r.stdout


def test_text_mentioning_46_in_user_and_tool_rows_is_not_a_served_id():
    r = _run(_case("all_47"))
    assert r.returncode == 0
    assert "grok-4.6" not in r.stdout


def test_one_46_row_exits_1_and_names_it():
    r = _run(_case("one_46"))
    assert r.returncode == 1
    assert "grok-4.6-build" in r.stdout


def test_summary_alone_saying_47_does_not_clear_a_46_response():
    r = _run(_case("summary_only_47"))
    assert r.returncode == 1
    assert "grok-4.6-build" in r.stdout


def test_empty_history_exits_2():
    assert _run(_case("empty_history")).returncode == 2


def test_missing_usage_file_exits_2():
    assert _run(_case("missing_usage")).returncode == 2


def test_missing_directory_exits_2():
    assert _run(str(FIX / "nope")).returncode == 2


def test_response_row_without_model_id_exits_1():
    r = _run(_case("no_model_id"))
    assert r.returncode == 1
    assert "(none)" in r.stdout


def test_pin_flag_changes_the_prefix():
    assert _run(_case("one_46"), "--pin", "grok-4.").returncode == 0
    assert _run(_case("all_47"), "--pin", "grok-4.6").returncode == 1


def test_output_carries_usage_and_summary_ids():
    r = _run(_case("all_47"))
    assert "usage.json" in r.stdout and "summary.json" in r.stdout


def test_tree_and_session_resolve_the_url_encoded_folder(tmp_path):
    tree = r"C:\Projects\some-tree"
    d = tmp_path / quote(tree, safe="") / SID
    d.parent.mkdir(parents=True)
    src = FIX / "all_47" / SID
    d.mkdir()
    for f in src.iterdir():
        (d / f.name).write_bytes(f.read_bytes())
    r = _run("--tree", tree, "--session", SID, "--root", str(tmp_path))
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("args", [[], ["--tree", "x"]])
def test_bad_invocation_exits_2(args):
    assert _run(*args).returncode == 2
