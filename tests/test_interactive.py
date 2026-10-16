"""bench interactive: prepare -> an operator's session (played here by next.py calls and file writes) -> collect -> report.

The end-to-end test plays the fixture two-turn task's reference solution in one arm and its naive solution in the other,
through the real next.py, the real overlays, the real engine and the real grading pass, and requires the scores the
fixture declares for those two solutions (the values `bench discriminate` reproduces): interactive grading is the
headless grading, applied to the operator's folders.
"""

import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
from clean_parent import CLEAN_PARENT

from harness_bench import archive, gitsafe, interactive
from harness_bench.errors import BenchError
from harness_bench.telemetry import Extraction, ModelCall, ToolCall, agy

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("make_task", Path(__file__).parent / "fixtures" / "property_tasks" / "make_task.py")
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)  # type: ignore[union-attr]
TASK = "DISC-T"


def _next(arm: Path, *args: str) -> str:
    return subprocess.run([sys.executable, str(arm / ".bench" / "next.py"), *args], cwd=arm, capture_output=True,
                          text=True, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout


def _fake_pack(monkeypatch, tmp: Path) -> None:
    """The pack checkout and install are the engine's own (tested with the headless cells); here a stand-in writes one
    instruction file and commits it, so the arms differ as a pack-on and a pack-off arm do."""
    monkeypatch.setattr(interactive.workspace, "pack_checkout", lambda source, commit, root: tmp)
    monkeypatch.setattr(interactive.workspace, "pack_revision", lambda d: 0)

    def install(pack_dir, ws, project, timeout):
        (ws / "AGENTS.md").write_text("pack stand-in\n", encoding="utf-8")
        gitsafe.git(["add", "-A"], cwd=ws, timeout=60)
        gitsafe.git(["commit", "-q", "-m", "pack"], cwd=ws, timeout=60, identity=True)
        return ["AGENTS.md"]

    monkeypatch.setattr(interactive.workspace, "install_pack", install)


@pytest.mark.skipif(sys.platform != "win32", reason="the grader and its host are Windows-only (ADR-0018 s8)")
def test_interactive_arms_grade_as_the_fixture_declares(monkeypatch):
    base = CLEAN_PARENT / uuid.uuid4().hex  # cells cannot be built under the operator's profile (HB-PRE-002)
    base.mkdir(parents=True)
    try:
        root = mt.make_root(base)
        task_dir = mt.install(root, "disc_turns")
        _fake_pack(monkeypatch, base / "pack")
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(base / "no-records"))  # gather's search reads no operator record
        graded = base / "graded.txt"  # the stand-in grading command appends the arm it was started for
        stand_in = [sys.executable, "-c", f"import sys; open({str(graded)!r}, 'a').write(sys.argv[-2] + '\\n')"]
        manifest = interactive.prepare(root, "int-t", "claude-code", base / "out", [TASK], ("C:/pack", "0" * 40), base / "tools", stand_in)
        solutions = {"off": "reference", "on": "naive"}
        for arm, role in solutions.items():
            arm_dir = Path(manifest["arms"][arm]["path"])
            assert (arm_dir / "AGENTS.md").is_file() == (arm == "on")
            assert not (arm_dir / "tasks" / TASK / "tests").exists()  # hidden tests never reach the arm
            first = _next(arm_dir)
            assert f"TASK 1 of 2: {TASK} (turn 1 of 2)" in first and str(arm_dir / "tasks" / TASK) in first
            for turn in (1, 2):
                for rel, path in [(p.relative_to(s).as_posix(), p) for s in [task_dir / "oracle" / "solutions" / role / f"turn-{turn}"]
                                  for p in s.rglob("*") if p.is_file()]:
                    shutil.copyfile(path, arm_dir / "tasks" / TASK / rel)
                out = _next(arm_dir)
                assert ("TASK 2 of 2" in out) if turn == 1 else out.startswith("ALL DONE")
            assert (arm_dir / ".bench" / "snapshots" / TASK / "turn-1").is_dir()
            done = json.loads((arm_dir / ".bench" / "state.json").read_text(encoding="utf-8"))["done"]
            assert all(re.fullmatch(r"[0-9a-f]{40}", d["commit"]) for d in done), done  # graded below from the commits
            if arm == "on":
                (arm_dir / "notes.md").write_text("work outside the task folders\n", encoding="utf-8")
            summary = interactive.collect(root, base / "out" / "int-t", arm, "claude-code", base / "runs", base / "cells",
                                          base / "tools" / "upstream", records=[])
            expected = mt.TURNS_EXPECTED[role]
            got = {k: summary["scores"][TASK][k] for k in expected}
            assert got == expected, (arm, role, summary["warnings"])
            assert set(interactive.DRIFT_SCORES) <= set(summary["scores"][TASK]), summary["scores"][TASK]
            assert summary["outside_task_folders"] == (["notes.md"] if arm == "on" else [])
            assert set(summary["minutes"]) == {f"{TASK}|1", f"{TASK}|2"}
            local = interactive.report(base / "out" / "int-t", only=arm).read_text(encoding="utf-8")
            other = "on" if arm == "off" else "off"
            assert f"{arm}: property_check_pass" in local and f"{other}: property_check_pass" not in local
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and len(graded.read_text().split() if graded.is_file() else []) < 2:
            time.sleep(0.2)
        assert sorted(graded.read_text().split()) == ["off", "on"]  # one grading started per arm, at the last item
        state = lambda: json.loads((arm_dir / ".bench" / "state.json").read_text(encoding="utf-8"))["grading"]
        started = state()
        assert "pid" in started, started
        assert _next(arm_dir).startswith("ALL DONE") and state() == started  # a later ALL DONE starts no second grading
        rows = interactive.gather(base / "out")
        assert [r["arms"] for r in rows] == [{"off": "graded", "on": "graded"}]
        text = Path(rows[0]["report"]).read_text(encoding="utf-8")
        assert re.search(rf"\| {TASK} \| \S+ \| 1 \| [\d.]+ \| \S+ \| 0 \| [\d.]+ \|", text), text
    finally:
        shutil.rmtree(base, onexc=archive.make_writable)


def test_next_status_reprints_without_advancing_and_done_stays_done(tmp_path):
    bench = tmp_path / ".bench"
    bench.mkdir()
    shutil.copyfile(interactive.NEXT, bench / "next.py")
    (tmp_path / "tasks" / "A").mkdir(parents=True)
    (bench / "queue.json").write_text(json.dumps({"items": [{"task": "A", "turn": 1, "turns": 1, "prompt": "do A"}]}), encoding="utf-8")
    assert "No task is open" in _next(tmp_path, "--status")
    assert "do A" in _next(tmp_path)
    assert "do A" in _next(tmp_path, "--status")
    assert json.loads((bench / "state.json").read_text(encoding="utf-8"))["open"]["task"] == "A"
    assert _next(tmp_path).startswith("ALL DONE")
    assert _next(tmp_path).startswith("ALL DONE")
    assert len(json.loads((bench / "state.json").read_text(encoding="utf-8"))["done"]) == 1


def _operator_git(args: list[str], cwd: Path, autocrlf: str = "true") -> subprocess.CompletedProcess:
    """git as the session runs it: the operator's own git, here pinned to Git for Windows' system default (autocrlf=true),
    with no hooks or global config of the machine running the test."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")} | {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    return subprocess.run(["git", "-c", f"core.autocrlf={autocrlf}", "-c", "user.name=s", "-c", "user.email=s@x", *args],
                          cwd=cwd, env=env, capture_output=True, text=True, check=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def test_the_arms_check_out_the_same_bytes_whatever_line_ending_rule_the_pack_ships(monkeypatch):
    """Run 20261015T1529 (ARM-FAIR-A): the pack's .gitattributes (`eol=lf`) gave the on arm a line-ending rule the off arm did
    not have, so a session's `git stash pop` wrote CRLF in off and LF in on. Here the stand-in pack ships the opposite
    rule; the bench's own rule must still decide both arms."""
    base = CLEAN_PARENT / uuid.uuid4().hex
    base.mkdir(parents=True)
    try:
        root = mt.make_root(base)
        mt.install(root, "disc_turns")
        _fake_pack(monkeypatch, base / "pack")
        install = interactive.workspace.install_pack

        def install_with_attributes(pack_dir, ws, project, timeout):
            (ws / ".gitattributes").write_text("* text eol=crlf\n", encoding="utf-8")
            return install(pack_dir, ws, project, timeout)

        monkeypatch.setattr(interactive.workspace, "install_pack", install_with_attributes)
        manifest = interactive.prepare(root, "int-eol", "claude-code", base / "out", [TASK], ("C:/pack", "0" * 40), base / "tools")
        restored = {}
        for arm in interactive.ARMS:
            arm_dir = Path(manifest["arms"][arm]["path"])
            rel = next(p for p in _operator_git(["ls-files", f"tasks/{TASK}"], arm_dir).stdout.split() if p.endswith(".py"))
            (arm_dir / rel).write_text("changed\n", encoding="utf-8")
            _operator_git(["stash"], arm_dir)
            _operator_git(["stash", "pop"], arm_dir)
            restored[arm] = (arm_dir / rel).read_bytes()
        assert restored["off"] == restored["on"] == b"changed\n"
    finally:
        shutil.rmtree(base, onexc=archive.make_writable)


def test_prepare_refuses_arms_whose_task_trees_differ_in_line_endings(tmp_path):
    arms = {}
    for arm, text in (("off", b"a\r\n"), ("on", b"a\n")):
        arm_dir = tmp_path / arm
        (arm_dir / "tasks" / "A").mkdir(parents=True)
        (arm_dir / "tasks" / "A" / "f.py").write_bytes(text)
        _operator_git(["init", "-q"], arm_dir, autocrlf="false")
        _operator_git(["add", "-A"], arm_dir, autocrlf="false")
        arms[arm] = arm_dir
    with pytest.raises(BenchError, match=r"HB-PRE-013|tasks/A/f\.py"):
        interactive.check_arms_alike(arms["off"], arms["on"])


def _git_arm(tmp_path: Path, items: list[dict]) -> Path:
    bench = tmp_path / ".bench"
    bench.mkdir()
    shutil.copyfile(interactive.NEXT, bench / "next.py")
    (bench / "queue.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    for item in items:
        (tmp_path / "tasks" / item["task"]).mkdir(parents=True, exist_ok=True)
        (tmp_path / "tasks" / item["task"] / "base.py").write_text("base\n", encoding="utf-8")
    _operator_git(["init", "-q", "-b", "main"], tmp_path, autocrlf="false")
    _operator_git(["add", "-A"], tmp_path, autocrlf="false")
    _operator_git(["commit", "-q", "-m", "base"], tmp_path, autocrlf="false")
    return tmp_path


def test_next_commits_the_closed_task_folder_so_a_later_stash_cannot_take_it(tmp_path):
    """Run 20261015T1529 (TASK-ISO-A): the 11 tasks share one repository and nothing was committed between them, so a
    `git stash -u` in a later task would carry every earlier task's work away. Closing a task commits its folder, and only
    its folder: work outside it stays a visible, uncommitted change for collect's outside-the-task-folders check."""
    arm = _git_arm(tmp_path, [{"task": "A", "turn": 1, "turns": 1, "prompt": "do A"},
                              {"task": "B", "turn": 1, "turns": 1, "prompt": "do B"}])
    _next(arm)
    (arm / "tasks" / "A" / "new.py").write_text("A's work\n", encoding="utf-8")
    (arm / "tasks" / "A" / "base.py").write_text("A changed\n", encoding="utf-8")
    (arm / "notes.md").write_text("outside\n", encoding="utf-8")
    _next(arm)
    done = json.loads((arm / ".bench" / "state.json").read_text(encoding="utf-8"))["done"]
    assert re.fullmatch(r"[0-9a-f]{40}", done[0]["commit"]), done[0]
    shown = _operator_git(["show", "--name-only", "--format=", done[0]["commit"]], arm).stdout.split()
    assert sorted(shown) == ["tasks/A/base.py", "tasks/A/new.py"]
    _operator_git(["stash", "-u"], arm)  # B's session cleans the tree
    assert (arm / "tasks" / "A" / "new.py").read_text(encoding="utf-8") == "A's work\n"
    assert not (arm / "notes.md").exists()  # outside work was never committed: the stash took it, as before


def test_next_hands_out_the_next_task_when_the_commit_cannot_be_made(tmp_path):
    """No repository (or a lock the session holds): the hand-out never waits on the commit; state.json says why."""
    bench = tmp_path / ".bench"
    bench.mkdir()
    shutil.copyfile(interactive.NEXT, bench / "next.py")
    (tmp_path / "tasks" / "A").mkdir(parents=True)
    (bench / "queue.json").write_text(json.dumps({"items": [{"task": "A", "turn": 1, "turns": 1, "prompt": "do A"},
                                                            {"task": "B", "turn": 1, "turns": 1, "prompt": "do B"}]}), encoding="utf-8")
    _next(tmp_path)
    assert "do B" in _next(tmp_path)
    done = json.loads((bench / "state.json").read_text(encoding="utf-8"))["done"]
    assert "error" in done[0]["commit"], done[0]


def test_harness_list_takes_commas_spaces_and_the_claude_alias_and_refuses_an_unknown_name():
    assert interactive.harnesses(["claude,", "codex,", "copilot"]) == ["claude-code", "codex", "copilot"]
    assert interactive.harnesses(["claude,codex", "claude-code"]) == ["claude-code", "codex"]
    with pytest.raises(BenchError, match="gemini"):
        interactive.harnesses(["claude", "gemini"])


def test_gather_rereads_the_records_the_grading_found_and_searches_only_when_it_found_none(monkeypatch, tmp_path):
    run = tmp_path / "run"
    (run / "collect" / "on").mkdir(parents=True)
    (run / interactive.MANIFEST).write_text(json.dumps({"schema": interactive.SCHEMA, "harness": "codex"}), encoding="utf-8")
    known = tmp_path / "rollout-known.jsonl"
    known.write_text("", encoding="utf-8")
    read = []
    monkeypatch.setattr(interactive, "read_session", lambda manifest, arm, harness, records: (read.append(records), (None, []))[1])
    for session, expected in (({"records": [str(known)]}, [known]), (None, None)):
        (run / "collect" / "on" / "summary.json").write_text(json.dumps({"harness": "codex", "session": session}), encoding="utf-8")
        interactive.refresh_session(run, "on")
        assert read[-1] == expected  # None: read_session searches, as the grading did


def test_default_tasks_are_every_lean_task():
    assert interactive.default_tasks(REPO) == ["S1", "S2", "RS1", "RS2", "RW1", "RW2", "NG1", "NG2", "SM1", "SM2", "SV1"]


def _call(n: int, requests: int = 1) -> ModelCall:
    return ModelCall(n, "m", 10, 100, 1, 5, 2, requests=requests)


def test_split_attributes_by_the_next_calls_and_never_splits_a_summary():
    ex = Extraction(model_calls=[_call(1), _call(4), _call(6), _call(9)],
                    tool_calls=[ToolCall(3, "Bash", "shell", None, None, True), ToolCall(5, "Bash", "shell", None, None, True),
                                ToolCall(7, "Bash", "shell", None, None, False), ToolCall(8, "Bash", "shell", None, None, True)])
    segs = interactive.split(ex, [3, 5, 8], ["A", "B"])
    assert [segs[k]["model_calls"] for k in ("setup", "A", "B", "wrap-up")] == [1, 1, 1, 1]
    assert segs["B"]["tool_calls"] == 2 and segs["B"]["tool_failures"] == 1 and segs["B"]["output"] == 5
    assert segs["setup"]["tool_calls"] == 0  # the next.py call that hands out a task is counted in that task
    summary = interactive.split(Extraction(model_calls=[_call(9, requests=4)]), [3, 5], ["A", "B"])
    assert summary["A"]["output"] is None and summary["B"]["uncached_input"] is None  # not recorded, never 0


def test_pack_hooks_count_only_the_packs_own_and_are_not_recorded_where_the_record_cannot_tell():
    """Smoke 2026-10-14: the operator's own Stop hook (wtcli) fired in both Claude Code arms, and Copilot's pack-off
    record held four lifecycle hook rows; neither is a pack hook."""
    from harness_bench.telemetry import HarnessEvent

    user = HarnessEvent(1, "hook", "wtcli.exe agent-hook --event agent.stop", None, None, True, "Stop durationMs=93")
    pack = HarnessEvent(2, "hook", "sh aif-hook docs/ai-forward-pack/hooks/run-hook.sh dispatch.py", None, None, True, "Stop")
    ex = Extraction(harness_events=[user, pack])
    assert interactive._pack_hooks("claude-code", ex, 0) == 1
    assert interactive._pack_hooks("copilot", ex, 0) is None
    assert interactive._pack_hooks("codex", Extraction(harness_events="not recorded: x"), 0) is None


def test_a_record_without_next_calls_is_placed_in_tasks_by_time():
    """A sub-agent writes its own record (Claude Code: <session>/subagents/*.jsonl) with no next.py call in it."""
    from datetime import UTC, datetime

    windows = [("A", datetime(2026, 10, 14, 10, 0, tzinfo=UTC), datetime(2026, 10, 14, 10, 30, tzinfo=UTC)),
               ("B", datetime(2026, 10, 14, 10, 30, 1, tzinfo=UTC), None)]
    ex = Extraction(model_calls=[ModelCall(1, "m", 1, 2, 3, 4, None, "2026-10-14T10:05:00Z"),
                                 ModelCall(2, "m", 1, 2, 3, 4, None, "2026-10-14T11:00:00.000Z"),
                                 ModelCall(3, "m", 1, 2, 3, 4, None, None)])
    segs = interactive.split_by_time(ex, windows)
    assert {k: v["model_calls"] for k, v in segs.items()} == {"A": 1, "B": 1, "unattributed": 1}
    assert segs["A"]["reasoning"] is None  # a bucket the harness does not report stays not recorded


def test_next_call_detection_ignores_status_and_other_scripts():
    assert interactive._is_next(r"python C:\x\on\.bench\next.py")
    assert interactive._is_next("python .bench/next.py")
    assert not interactive._is_next("python .bench/next.py --status")
    assert not interactive._is_next("python tools/next.py")


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b, n = n & 0x7F, n >> 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _field(num: int, value) -> bytes:
    if isinstance(value, int):
        return _varint(num << 3) + _varint(value)
    return _varint(num << 3 | 2) + _varint(len(value)) + value


def test_agy_db_reader_reads_usage_and_tool_calls_from_the_mapped_fields(tmp_path):
    """The field map Verified on 1,542 paired requests (agy.py): steps.metadata 9.2 input, 9.3 output, 9.5 cache read,
    9.9 thinking, absent = 0; the planner's tool call at 20.7 (2 name, 3 JSON); the model name at gen_metadata 1.19."""
    db = tmp_path / "c0ffee.db"
    con = sqlite3.connect(db)
    con.execute("create table steps (idx, step_type, status, metadata, step_payload)")
    con.execute("create table gen_metadata (idx, data, size)")
    usage = _field(9, _field(2, 2651) + _field(3, 502) + _field(5, 27818) + _field(9, 290))
    call = _field(20, _field(7, _field(2, b"run_command") + _field(3, json.dumps({"CommandLine": "python .bench/next.py"}).encode())))
    con.execute("insert into steps values (1, 15, 3, ?, ?)", (usage, call))
    con.execute("insert into steps values (2, 15, 3, ?, NULL)", (_field(9, _field(2, 7) + _field(3, 1)),))
    con.execute("insert into steps values (3, 9, 3, NULL, NULL)")
    con.execute("insert into gen_metadata values (0, ?, 0)", (_field(1, _field(19, b"gemini-4-argon")),))
    con.commit()
    con.close()
    ex = agy.read_db(db)
    assert [(c.native_ordinal, c.uncached_input, c.cache_read, c.output, c.reasoning) for c in ex.model_calls] == \
        [(1, 2651, 27818, 502, 290), (2, 7, 0, 1, 0)]
    assert ex.served.model_served == "gemini-4-argon"
    trace = agy.tool_inputs_db(db)
    assert [(c.native_ordinal, c.name, c.command) for c in trace.calls] == [(1, "run_command", "python .bench/next.py")]


def test_the_prompt_page_shows_the_paste_verbatim_in_both_arms():
    import html

    page = (REPO / "docs" / "benchmarkpromps" / "interactive-benchmark-prompt.html").read_text(encoding="utf-8")
    blocks = re.findall(r'<pre id="paste(?:-on)?"[^>]*>(.*?)</pre>', page, re.DOTALL)
    assert len(blocks) == 2 and all(html.unescape(b).strip() == interactive.PASTE.strip() for b in blocks)
