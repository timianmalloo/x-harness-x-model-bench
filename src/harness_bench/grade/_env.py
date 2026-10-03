"""One grading environment allowlist (ADR-0018 section 9; W0 section 3 `env`, section 10 G4).

The only module under `grade/` that defines `HOST_ENV` or reads `os.environ`, so the graders cannot drift (DM7).
`DOTNET_HOST_ENV` moved here verbatim from `correctness.py` (req-01M41DM80, G17); `mutation.py` keeps its own,
different tuple. Design: docs/design/eval-property-grader.md section 5.9.
"""

import os
from collections.abc import Iterable

from harness_bench.profiles import CELL_ENV, DROP_EXACT, DROP_PREFIXES

HOST_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP")
DOTNET_HOST_ENV = ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "ProgramData", "ProgramFiles",
                   "NUGET_PACKAGES")
TOOLCHAIN_ENV = frozenset(DOTNET_HOST_ENV)
CHECK_PREFIX = "HB_CHECK_"
_DENIED_EXTRA = frozenset({"HB_CLAUDE_OAUTH_TOKEN", "GH_TOKEN"})


def grading_env(extra: Iterable[str] = ()) -> dict[str, str]:
    """HOST_ENV, CELL_ENV and the interpreter trio, plus the `extra` names that are set; never `os.environ` wholesale."""
    env = {k: os.environ[k] for k in HOST_ENV if k in os.environ}
    env |= {k: os.environ[k] for k in extra if k in os.environ and not denied(k)}
    return {**env, **CELL_ENV, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "PYTHONUTF8": "1"}


def denied(name: str) -> bool:
    """True for a credential or agent-harness name that no grading child may inherit (the profiles denylist)."""
    upper = name.upper()
    return upper in DROP_EXACT or upper in _DENIED_EXTRA or upper.startswith(DROP_PREFIXES)
