"""The slow ring's opt-in (design phase3-graders, Catalog-version rule 4; seam V-4).

The `slow` tests run the real dotnet graders on the grading host: `HB_REQUIRE_DOTNET=1 python -m pytest -m slow`.
Without HB_REQUIRE_DOTNET=1 a slow test skips; with it, a missing dotnet fails the test instead of skipping, so the
grading host cannot pass the ring vacuously. conftest.py's `require_dotnet` fixture applies it.
"""

import shutil
from collections.abc import Callable, Mapping

import pytest


def dotnet_gate(env: Mapping[str, str], which: Callable[[str], str | None] = shutil.which) -> None:
    if env.get("HB_REQUIRE_DOTNET") != "1":
        pytest.skip("dotnet not required")
    if which("dotnet") is None:
        pytest.fail("HB_REQUIRE_DOTNET=1 but dotnet is not on PATH")
