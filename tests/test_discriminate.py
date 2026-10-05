"""bench discriminate through the real engine, archiver and grading pass (W1-E; R-98). Nothing of the path is faked.

Each trial is one run of the real `engine.Engine` with the real `SyntheticLauncher` (a real agent process), the real
working-copy builder and the real `runner.run_pass`. Fixtures come from `tests/fixtures/property_tasks/make_task.py`.
"""

import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

from harness_bench import discriminate, oslock, readiness
from harness_bench.errors import BenchError
from harness_bench.grade import _env

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the grader and its host are Windows-only (ADR-0018 s8)")
_spec = importlib.util.spec_from_file_location("make_task", Path(__file__).parent / "fixtures" / "property_tasks" / "make_task.py")
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)  # type: ignore[union-attr]
TASK = "DISC-C"


def trial(base: Path, root: Path, task: str = TASK) -> discriminate.Result:
    return discriminate.run(root, task, runs=base / "runs", cells_root=base / "cells")


def new_root(base: Path, name: str = "disc_c", **tweak) -> Path:
    root = mt.make_root(base)
    mt.install(root, name, **tweak)
    return root


def run_folders(base: Path) -> set[str]:
    runs = base / "runs"
    return {p.name for p in runs.iterdir() if p.is_dir()} if runs.is_dir() else set()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def got(first):
    """The shared trial's outcome, asserted first so a red run fails on this line and not on a missing attribute."""
    base, root, result = first
    assert result.outcome == "written", result
    return base, root, result


@pytest.fixture(scope="module")
def first(tmp_path_factory):
    """One real trial of disc_c, shared by the tests that only read its outcome."""
    base = tmp_path_factory.mktemp("disc-c")
    root = new_root(base)
    return base, root, trial(base, root)


def test_a_check_less_property_task_discriminates_without_a_host(first):
    """T-E1c: the real engine and grader; no `probe` key for a check-less property; readiness raises no item."""
    _base, root, result = got(first)
    assert result.record_path.exists()
    body = json.loads(result.record_path.read_text(encoding="utf-8"))
    assert "probe" not in body
    assert body["scores"]["reference"]["pass_at_1"] == 1
    assert body["scores"]["naive"]["pass_at_1"] == 0
    assert readiness.problems(root) == []


def test_synthetic_environment_and_record_leak_scan(first, monkeypatch, tmp_path):
    """R2-3 (T-E1a's allowlist, canary and leak assertions, moved here by name; only the `exists()` assertion retired)."""
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GH_TOKEN", "HB_CLAUDE_OAUTH_TOKEN", "HB_TEST_UNLISTED_SECRET"):
        monkeypatch.setenv(name, "BENCHCANARY-secret")
    launcher = discriminate.SyntheticLauncher({"synthetic-reference": tmp_path / "ov"})
    _argv, env = launcher.argv_env({"combo": "synthetic-reference"}, tmp_path / "home", "00-trace-00")
    assert set(env) == set(_env.grading_env()) | {"HB_SYNTH_OVERLAY", "TRACEPARENT"}
    assert not {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GH_TOKEN", "HB_CLAUDE_OAUTH_TOKEN", "HB_TEST_UNLISTED_SECRET"} & set(env)
    base, _root, result = got(first)
    texts = [result.record_path.read_text(encoding="utf-8")]
    texts += [p.read_text(encoding="utf-8") for p in (base / "runs").rglob("discrimination-link.json")]
    assert len(texts) == 2, "the trial wrote one record and one link"
    user = os.environ.get("USERNAME", "")
    for text in texts:
        assert "BENCHCANARY-" not in text
        assert not re.search(r"[A-Za-z]:[\\/]", text), "no absolute path"
        assert not user or user.lower() not in text.lower()


def test_overlay_lands_in_the_engine_built_working_copy_and_deletes_nothing(first):
    """T-E2: the archived tree is the engine-built working copy (keep.txt from the base) with the overlay on top."""
    base, _root, result = got(first)
    archives = list((base / "runs" / result.run_id / "archive").glob("*/attempt-1/ws"))
    assert len(archives) == 2
    contents = sorted((ws / "app.py").read_text(encoding="utf-8") for ws in archives)
    assert contents == sorted([mt.DOUBLE_REF, mt.DOUBLE_NAIVE])
    assert all((ws / "keep.txt").read_text(encoding="utf-8") == "keep me\n" for ws in archives)


def test_record_body_is_a_pure_function_of_its_key(first):
    """Acceptance 5: the key set, and no clock, duration, pid, path, run id or grading id anywhere in key or value."""
    base, _root, result = got(first)
    body = json.loads(result.record_path.read_text(encoding="utf-8"))
    assert set(body) == {"schema", "task", "task_version", "identity_hash", "platform", "scores", "expected", "readiness_failures"}
    flat = json.dumps(body)
    assert result.run_id not in flat and "grading-" not in flat and "duration" not in flat
    link = json.loads(next((base / "runs" / result.run_id).glob("discrimination-link.json")).read_text(encoding="utf-8"))
    assert link["run_id"] == result.run_id
    assert link["record_sha256"] == digest(result.record_path)
    assert link["record_stem"] == result.record_path.stem


def test_retry_at_an_unchanged_key_is_a_confirmation(tmp_path):
    """T-E4 / acceptance 4: a second trial in another run folder writes equal bytes and is `confirmed`, never HB-LED-007."""
    root = new_root(tmp_path)
    one = trial(tmp_path, root)
    assert one.outcome == "written"
    before = digest(one.record_path)
    two = trial(tmp_path, root)
    assert (one.outcome, two.outcome) == ("written", "confirmed")
    assert two.record_path == one.record_path and digest(two.record_path) == before
    assert two.run_id != one.run_id
    assert len(list((tmp_path / "runs").glob("*/discrimination-link.json"))) == 2


def test_no_link_after_hb_rdy_010(tmp_path):
    """T-E5a/b (R-98 conditions 1 and 2): a differing re-run raises HB-RDY-010 naming the first differing path and both
    values, leaves the stored bytes alone, and the failed run folder holds no link."""
    root = new_root(tmp_path, "disc_flaky", counter=str(tmp_path / "counter.txt"))
    one = trial(tmp_path, root, "DISC-FLAKY")
    assert one.outcome == "written"
    before = digest(one.record_path)
    seen = run_folders(tmp_path)
    with pytest.raises(BenchError) as err:
        trial(tmp_path, root, "DISC-FLAKY")
    assert err.value.code == "HB-RDY-010"
    assert re.search(r"scores\.reference\.\w+", str(err.value))
    assert digest(one.record_path) == before
    (failed,) = run_folders(tmp_path) - seen
    assert not (tmp_path / "runs" / failed / "discrimination-link.json").exists()


def test_two_discriminate_calls_exactly_one_proceeds(tmp_path):
    """T-E20: the test holds the task's lock itself; the call is refused before it plans, so no run folder exists."""
    root = new_root(tmp_path)
    with oslock.RunLock.acquire(tmp_path / "runs" / f".discriminate-{TASK}.lock", "HB-RUN-005"):
        with pytest.raises(BenchError) as err:
            trial(tmp_path, root)
    assert err.value.code == "HB-RUN-005"
    assert run_folders(tmp_path) == set()


def test_an_incomplete_engine_run_writes_no_record_and_names_the_cell(tmp_path, monkeypatch):
    """T-E21: an agent that exits non-zero fails its cell; nothing is written and the error names the cell."""
    bad = tmp_path / "bad_agent.py"
    bad.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    monkeypatch.setattr(discriminate, "AGENT", bad)
    root = new_root(tmp_path)
    with pytest.raises(BenchError) as err:
        trial(tmp_path, root)
    assert err.value.code == "HB-RDY-011" and f"{TASK}.synthetic-" in str(err.value)
    assert not (root / "bench" / "discrimination").exists() or not list((root / "bench" / "discrimination").rglob("*.json"))
    assert not list((tmp_path / "runs").rglob("discrimination-link.json"))


def test_a_leaked_temp_is_swept_before_the_write_and_never_by_a_reader(tmp_path):
    """T-E17: the writer sweeps `<name>.tmp-*` temps (files and folders) under its lock; a non-temp name survives."""
    root = new_root(tmp_path)
    folder = root / "bench" / "discrimination" / TASK
    folder.mkdir(parents=True)
    leaked = folder / f"x.json.tmp-1-{'a' * 32}"
    leaked.write_text("torn", encoding="utf-8")
    leaked_dir = folder / f"y.json.tmp-2-{'b' * 32}"
    leaked_dir.mkdir()
    keep = folder / "x.tmp-notes"
    keep.write_text("notes", encoding="utf-8")
    result = trial(tmp_path, root)
    assert result.outcome == "written"
    assert result.record_path.exists()
    assert not leaked.exists() and not leaked_dir.exists() and keep.exists()
