"""T-E9 (c): `bench discriminate <task>` through the real `cli.main` (X-E's design section 300; X-C3a owns the dispatch row)."""

from __future__ import annotations

from pathlib import Path

from test_cli_campaign import cli_rc

from harness_bench import cli, discriminate
from harness_bench.errors import BenchError


def test_discriminate_dispatches_to_run_and_prints_the_record_path_and_outcome(tmp_path, monkeypatch, capsys):
    seen = {}

    def fake_run(root, task_id, *, runs, cells_root, upstream_root=None):
        seen.update(root=root, task=task_id, runs=runs, cells_root=cells_root)
        return discriminate.Result("written", Path("bench/discrimination/T1/rec.json"), "disc-t1-run")

    monkeypatch.setattr(cli.discriminate, "run", fake_run)
    rc = cli_rc(["--root", str(tmp_path), "--runs", str(tmp_path / "r"), "--cells-root", str(tmp_path / "c"), "discriminate", "T1"])
    out = capsys.readouterr().out
    assert rc == 0 and "written" in out and "rec.json" in out
    assert seen == {"root": tmp_path.resolve(), "task": "T1", "runs": (tmp_path / "r").resolve(), "cells_root": (tmp_path / "c").resolve()}


def test_discriminate_options_are_accepted_after_the_command_and_a_bench_error_reaches_main_s_handler(tmp_path, monkeypatch, capsys):
    seen = {}

    def refusing(root, task_id, *, runs, cells_root, upstream_root=None):
        seen.update(runs=runs, cells_root=cells_root)
        raise BenchError("HB-RDY-011", "a trial cell has a check NA row. Fix the task.")

    monkeypatch.setattr(cli.discriminate, "run", refusing)
    rc = cli_rc(["discriminate", "T1", "--root", str(tmp_path), "--runs", str(tmp_path / "r2"), "--cells-root", str(tmp_path / "c2")])
    assert rc == 1 and "HB-RDY-011" in capsys.readouterr().err
    assert seen == {"runs": (tmp_path / "r2").resolve(), "cells_root": (tmp_path / "c2").resolve()}
