"""R-92 condition 1: the served model is read from the response rows, never from the summary or from text.

Fixtures under tests/fixtures/grok_sessions are synthetic copies of the real session-store shapes
(chat_history.jsonl `assistant` rows carry `model_id`; usage.json `session.modelUsage` keys; summary.json
`current_model_id`). Each test runs the tool as a subprocess, the way README section 3 runs it.
"""

import json
import subprocess
import sys
import threading
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


def test_missing_usage_file_reads_the_responses_and_exits_0():
    """TOOL-GSM-B: usage.json is absent on a deadline-killed session; the response rows decide."""
    r = _run(_case("missing_usage"))
    assert r.returncode == 0, r.stderr
    assert "source=chat_history (usage.json absent)" in r.stdout


def test_only_chat_history_exits_0_and_names_its_source():
    r = _run(_case("only_chat_history"))
    assert r.returncode == 0, r.stderr
    assert "source=chat_history" in r.stdout
    assert "grok-4.7-build x3" in r.stdout
    assert "usage.json models: (absent)" in r.stdout
    assert "summary.json current_model_id: (absent)" in r.stdout


def test_only_chat_history_with_a_46_response_exits_1_and_names_it():
    r = _run(_case("only_chat_history_mixed"))
    assert r.returncode == 1
    assert "grok-4.6-build x1" in r.stdout


def test_summary_alone_saying_47_does_not_clear_a_46_response_when_usage_is_absent():
    r = _run(_case("no_usage_summary_47_response_46"))
    assert r.returncode == 1
    assert "grok-4.6-build x1" in r.stdout


def test_no_chat_history_and_no_usage_exits_2_not_recorded():
    r = _run(_case("neither"))
    assert r.returncode == 2
    assert r.stdout.startswith("not recorded")


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


@pytest.mark.parametrize("args", [[], ["--tree", "x", "--root", "no-such-grok-sessions-root"]])
def test_bad_invocation_exits_2(args):
    assert _run(*args).returncode == 2


# TOOL-GSM-FIRST (R-103 condition 3): --first reads only the first assistant row.


def test_first_46_response_exits_1_and_names_it():
    r = _run("--first", _case("first_46_first"))
    assert r.returncode == 1
    assert "grok-4.6-build" in r.stdout and "FAIL" in r.stdout


def test_first_reads_only_the_first_row_while_join_mode_still_fails():
    r = _run("--first", _case("first_47_then_46"))
    assert r.returncode == 0, r.stdout
    assert r.stdout.startswith("first response: grok-4.7-build (row 2;")
    assert _run(_case("first_47_then_46")).returncode == 1


def test_first_with_no_assistant_row_exits_2():
    assert _run("--first", _case("first_user_only")).returncode == 2


def test_first_missing_file_exits_2():
    assert _run("--first", _case("neither")).returncode == 2


def test_first_row_without_model_id_exits_1():
    assert _run("--first", _case("first_no_id")).returncode == 1


def test_wait_returns_when_the_assistant_row_appears(tmp_path):
    d = tmp_path / SID
    d.mkdir()
    history = d / "chat_history.jsonl"
    history.write_text('{"type": "user", "content": "go"}\n', encoding="utf-8")

    def append_row():
        with history.open("a", encoding="utf-8") as fh:
            fh.write('{"type": "assistant", "model_id": "grok-4.7-build"}\n')

    # The row lands 1.5 s after the tool starts, so a tool that does not poll exits 2 first.
    threading.Timer(1.5, append_row).start()
    r = _run("--first", "--wait", "30", str(d))
    assert r.returncode == 0, r.stdout


def test_wait_with_nothing_arriving_ends_with_2():
    assert _run("--first", "--wait", "1", _case("first_user_only")).returncode == 2


# STORE-A: the key is the tree path with backslashes, URL-encoded, written here as a
# literal. The tool's quote() must not build this fixture.


def test_observed_layout_is_found_by_tree(tmp_path):
    tree = "C:/Projects/gsm-demo"
    cwd = "C:\\Projects\\gsm-demo"
    key = "C%3A%5CProjects%5Cgsm-demo"
    older = "11111111-1111-4111-8111-111111111111"
    newer = "22222222-2222-4222-8222-222222222222"
    key_dir = tmp_path / key
    key_dir.mkdir()
    (key_dir / "prompt_history.jsonl").write_text("", encoding="utf-8")

    def write_session(uuid: str, updated_at: str, model: str) -> None:
        folder = key_dir / uuid
        folder.mkdir()
        summary = {
            "info": {"id": uuid, "cwd": cwd},
            "created_at": "2026-10-08T00:00:00Z",
            "updated_at": updated_at,
        }
        (folder / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        row = {"type": "assistant", "content": "", "model_id": model}
        (folder / "chat_history.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    write_session(older, "2026-10-08T00:00:00Z", "grok-4.7-older")
    write_session(newer, "2026-10-08T01:00:00Z", "grok-4.7-newer")

    newest = _run("--tree", tree, "--root", str(tmp_path))
    assert newest.returncode == 0, newest.stdout + newest.stderr
    assert "grok-4.7-newer" in newest.stdout
    assert "grok-4.7-older" not in newest.stdout

    picked = _run("--tree", tree, "--session", older, "--root", str(tmp_path))
    assert picked.returncode == 0, picked.stdout + picked.stderr
    assert "grok-4.7-older" in picked.stdout
    assert "grok-4.7-newer" not in picked.stdout

    fallback = _run("--tree", tree, "--session", "xgsm-fin", "--root", str(tmp_path))
    assert fallback.returncode == 0, fallback.stdout + fallback.stderr
    assert "grok-4.7-newer" in fallback.stdout
    assert "grok-4.7-older" not in fallback.stdout

    missing = _run("--tree", "C:/Projects/gsm-none", "--root", str(tmp_path))
    assert missing.returncode == 2
    assert "not recorded" in missing.stdout
