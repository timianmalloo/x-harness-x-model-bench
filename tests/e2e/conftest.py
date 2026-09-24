from pathlib import Path

import pytest

from harness_bench import tools

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def pinned_builds() -> Path:
    """The pinned harness builds in this checkout's tools folder, installed once if absent."""
    tools_dir = ROOT / ".tools" / "harness"
    if not tools_dir.is_dir():
        tools.install(ROOT / "bench" / "tools", tools_dir)
    return tools_dir
