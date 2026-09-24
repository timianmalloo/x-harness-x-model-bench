"""Preflight before `bench run` (design: Run-level codes HB-PRE-002/003/005/007)."""

import pytest
from test_tools import _fake_tree

from harness_bench import preflight, tools
from harness_bench.errors import BenchError


def _plan(tools_dir):
    return {"builds": {h: b.record() for h, b in tools.resolve(tools_dir).items()}}


def _code(fn) -> str:
    with pytest.raises(BenchError) as err:
        fn()
    return err.value.code


def test_a_clean_host_passes(tmp_path, base):
    tools_dir = _fake_tree(tmp_path / "tools")
    facts = preflight.check(_plan(tools_dir), base / "cells", tools_dir, min_free=1, long_paths=lambda: True)
    assert facts["free_bytes"] > 0 and (base / "cells").is_dir()


def test_an_instruction_file_above_the_cells_root_is_hb_pre_002(tmp_path, base):
    tools_dir = _fake_tree(tmp_path / "tools")
    (base / "AGENTS.md").write_text("be helpful", encoding="utf-8")
    assert _code(lambda: preflight.check(_plan(tools_dir), base / "cells", tools_dir, min_free=1, long_paths=lambda: True)) == "HB-PRE-002"


def test_too_little_disk_is_hb_pre_003(tmp_path, base):
    tools_dir = _fake_tree(tmp_path / "tools")
    assert _code(lambda: preflight.check(_plan(tools_dir), base / "cells", tools_dir, min_free=10**18,
                                         long_paths=lambda: True)) == "HB-PRE-003"


def test_long_paths_off_is_hb_pre_005(tmp_path, base):
    tools_dir = _fake_tree(tmp_path / "tools")
    assert _code(lambda: preflight.check(_plan(tools_dir), base / "cells", tools_dir, min_free=1,
                                         long_paths=lambda: False)) == "HB-PRE-005"


def test_a_build_changed_since_the_plan_is_hb_pre_007(tmp_path, base):
    tools_dir = _fake_tree(tmp_path / "tools")
    plan = _plan(tools_dir)
    (tools_dir / "node_modules/@anthropic-ai/claude-agent-sdk-win32-x64/claude.exe").write_text("updated", encoding="utf-8")
    assert _code(lambda: preflight.check(plan, base / "cells", tools_dir, min_free=1, long_paths=lambda: True)) == "HB-PRE-007"


def test_missing_tools_are_hb_pre_007(tmp_path, base):
    plan = {"builds": {"codex": {"version": "0.156.0"}}}
    assert _code(lambda: preflight.check(plan, base / "cells", tmp_path / "none", min_free=1, long_paths=lambda: True)) == "HB-PRE-007"


def test_the_long_paths_probe_reads_the_host():
    assert preflight.long_paths_enabled() in (True, False, None)
