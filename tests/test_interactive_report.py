"""The interactive report's own rules, on stored summaries (no replay): token buckets apart with an on ÷ off ratio
(TOK-BUCKET-A), a stale-grade flag (STALE-GRADE-A), and the files behind a scope_creep count (DRIFT-EVIDENCE-A)."""

import json
from pathlib import Path

from harness_bench import interactive

TASKS = ["NG1", "RS2"]
CURRENT = {"bench_commit": "a" * 40, "dirty": False, "task_versions": {"NG1": "v1", "RS2": "v2"}}


def _segment(uncached, read, write, output, tools):
    return {"uncached_input": uncached, "cache_read": read, "cache_write": write, "output": output, "reasoning": 0,
            "model_calls": 1, "tool_calls": tools, "tool_failures": 0, "tool_failures_exit": 0}


def _summary(arm: str, *, uncached: int, read: int, graded_with: dict | None, drift_files: dict) -> dict:
    total = _segment(uncached, read, 10, 100, 4)
    return {"schema": "bench-interactive-summary/1", "run_id": "int-t", "arm": arm, "harness": "claude-code",
            "collected_at": "t", "replay_run": f"r-{arm}", "minutes": {"NG1|1": 1.0, "RS2|1": 2.0},
            "scores": {"NG1": {"pass_at_1": 1, "property_check_pass": 1, "scope_creep": 5, "drift_task_implied_lines": 0,
                               "drift_machine_lines": 0},
                       "RS2": {"pass_at_1": 1, "property_check_pass": 0, "scope_creep": 0, "drift_task_implied_lines": 0,
                               "drift_machine_lines": 0}},
            "drift_files": drift_files, "outside_task_folders": [], "session_warnings": [], "warnings": [],
            "session": {"records": [], "total": total, "per_item": {"NG1": _segment(uncached, read, 10, 60, 2),
                                                                    "RS2": _segment(0, 0, 0, 40, 2)},
                        "served": [], "cli_versions": [], "pack_hook_events": 0, "hook_events": 0, "hook_ms": None,
                        "hook_ms_reason": "x", "model_ms": None, "model_ms_reason": "x", "tool_ms": 5000,
                        "tool_ms_reason": None, "queue_reads": 0, "notes": []},
            "pack_hook_time": {"dispatches": 0, "ms": 0, "reason": None},
            **({"graded_with": graded_with} if graded_with is not None else {})}


def _run(tmp_path: Path, off: dict, on: dict) -> Path:
    run = tmp_path / "int-t"
    for arm, s in (("off", off), ("on", on)):
        (run / "collect" / arm).mkdir(parents=True)
        (run / "collect" / arm / "summary.json").write_text(json.dumps(s), encoding="utf-8")
    (run / interactive.MANIFEST).write_text(json.dumps({
        "schema": interactive.SCHEMA, "run_id": "int-t", "harness": "claude-code", "created_at": "t", "tasks": TASKS,
        "task_versions": CURRENT["task_versions"], "pack_pin": {"source": "s", "commit": "0" * 40, "revision": 110},
        "arms": {a: {"path": str(run / a), "base": "0" * 40, "pack_files": 0} for a in ("off", "on")}}), encoding="utf-8")
    return run


def test_token_buckets_are_reported_apart_with_an_on_over_off_ratio_per_bucket(tmp_path):
    """TOK-BUCKET-A: one number per bucket per arm, and the ratio per bucket; never one input+cache sum."""
    run = _run(tmp_path, _summary("off", uncached=1000, read=90000, graded_with=CURRENT, drift_files={}),
               _summary("on", uncached=3000, read=99000, graded_with=CURRENT, drift_files={}))
    text = interactive.report(run, current=CURRENT).read_text(encoding="utf-8")
    assert "| uncached_input tokens (the prefix and new text each request pays for) | 1,000 | 3,000 | ×3.00 |" in text
    assert "| cache_read tokens (context re-read from the cache) | 90,000 | 99,000 | ×1.10 |" in text
    assert "| output tokens | 100 | 100 | ×1.00 |" in text
    assert "| wall minutes (sum of tasks) | 3.0 | 3.0 | - |" in text  # no ratio for a non-count
    assert "| NG1 | 1,000 | 90,000 | 10 | 60 | 2 | 3,000 | 99,000 | 10 | 60 | 2 |" in text  # per task, per bucket
    assert "input+cache" not in text
    assert "Stale scores" not in text


def test_a_grade_from_another_bench_commit_or_task_version_or_no_record_is_flagged_stale(tmp_path):
    """STALE-GRADE-A: the report names what moved and the collect to re-run; a summary without `graded_with` is stale."""
    then = {**CURRENT, "bench_commit": "b" * 40}
    run = _run(tmp_path, _summary("off", uncached=1, read=1, graded_with=then, drift_files={}),
               _summary("on", uncached=1, read=1, graded_with=None, drift_files={}))
    text = interactive.report(run, current=CURRENT).read_text(encoding="utf-8")
    assert "**Stale scores.** off: STALE (graded at bench commit bbbbbbbbbbbb, this bench is aaaaaaaaaaaa); re-run " \
           "`bench interactive collect --arm off` on: graded before the grader build was recorded" in text
    moved = {**CURRENT, "task_versions": {"NG1": "v1", "RS2": "old"}}
    assert interactive.stale_grades({"on": {"graded_with": moved}}, CURRENT) == \
        ["on: STALE (task version moved: RS2); re-run `bench interactive collect --arm on`"]
    dirty = {**CURRENT, "dirty": True}
    assert interactive.stale_grades({"on": {"graded_with": dirty}}, CURRENT) == \
        ["on: STALE (the bench tree was dirty then); re-run `bench interactive collect --arm on`"]
    assert interactive.stale_grades({"on": {"graded_with": CURRENT}}, CURRENT) == []
    assert interactive.stale_grades({"on": {}}, None) == []  # no bench to compare against: no claim


def test_the_files_behind_a_scope_creep_count_are_listed_largest_first(tmp_path):
    """DRIFT-EVIDENCE-A: a reader sees `.test-deps/...` or one pyproject edit, not a bare line count."""
    log = tmp_path / "drift.log"
    log.write_text("modified\tsrc/a.py\tinside\t+3 -1\t\n"
                   "added\t.test-deps/x.py\toutside\t+900 -0\t\tdiscretionary\n"
                   "added\ttests/test_b.py\toutside\t+20 -0\t\ttask-implied\n"
                   "modified\tpyproject.toml\toutside\t+4 -1\t\tdiscretionary\n"
                   "ignored\t.venv/lib\n", encoding="utf-8")
    found = interactive.drift_files(log)
    assert found == [{"path": ".test-deps/x.py", "lines": 900}, {"path": "pyproject.toml", "lines": 5}]
    assert interactive.drift_files(tmp_path / "missing.log") == []
    big = "".join(f"added\tf{n}.py\toutside\t+{n} -0\t\tdiscretionary\n" for n in range(9))
    log.write_text(big, encoding="utf-8")
    assert [f["lines"] for f in interactive.drift_files(log)] == [8, 7, 6, 5, 4]  # at most DRIFT_FILES_SHOWN, largest first
    run = _run(tmp_path, _summary("off", uncached=1, read=1, graded_with=CURRENT, drift_files={"NG1": [], "RS2": []}),
               _summary("on", uncached=1, read=1, graded_with=CURRENT, drift_files={"NG1": found, "RS2": []}))
    text = interactive.report(run, current=CURRENT).read_text(encoding="utf-8")
    assert "- NG1 on: `.test-deps/x.py` (900 lines), `pyproject.toml` (5 lines)" in text
    assert "- NG1 off" not in text and "RS2 on:" not in text


def test_compare_pairs_every_session_per_task_and_says_how_many_more_a_verdict_needs(tmp_path):
    """The answer to "do we need more cells": sessions are the repetitions; per task the passes per arm over n, the
    sessions where the arms disagreed, and median tokens per bucket. Below SESSIONS_FOR_VERDICT the heading says so."""
    off1 = _summary("off", uncached=1000, read=90000, graded_with=CURRENT, drift_files={})
    on1 = _summary("on", uncached=3000, read=99000, graded_with=CURRENT, drift_files={})
    on2 = _summary("on", uncached=5000, read=99000, graded_with=CURRENT, drift_files={})
    on1["scores"]["NG1"]["property_check_pass"] = 0  # session 1: the on arm fails NG1, the off arm passes (o > n)
    on2["scores"]["RS2"]["property_check_pass"] = 1  # session 2: the on arm passes RS2, the off arm does not (o < n)
    on2["minutes"] = {"NG1|1": 3.0, "RS2|1": 2.0}
    for name, off, on in (("int-claude-code-1", off1, on1), ("int-claude-code-2", off1, on2)):
        _run(tmp_path, off, on).rename(tmp_path / name)
    (tmp_path / "int-codex-1").mkdir()  # an unprepared folder is ignored; a run with one arm graded does not count
    half = _run(tmp_path, off1, on1)
    (half / "collect" / "on" / "summary.json").unlink()
    half.rename(tmp_path / "int-codex-2")
    text = interactive.compare(tmp_path, current=CURRENT).read_text(encoding="utf-8")
    assert "## claude-code: 2 session(s) per arm (needs 1 more for a per-task verdict)" in text
    assert "Runs: `int-claude-code-1`, `int-claude-code-2`." in text
    assert "| NG1 | 2 | 2 | 1 | 1 | 1,000 | 90,000 | 10 | 60 | 1.0 | 4,000 | 99,000 | 10 | 60 | 2.0 |" in text
    assert "| RS2 | 2 | 0 | 1 | 1 | 0 | 0 | 0 | 40 | 2.0 | 0 | 0 | 0 | 40 | 2.0 |" in text
    assert "codex" not in text and "Stale scores" not in text
    assert (tmp_path / "interactive-compare.md").is_file()
    (tmp_path / "nothing-here").mkdir()
    empty = interactive.compare(tmp_path / "nothing-here")
    assert "No run under this folder has both arms graded." in empty.read_text(encoding="utf-8")
