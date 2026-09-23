"""Host-side git with a bench-owned configuration (ADR-0010 B6): cell repositories are untrusted input.

System and global git config are ignored, hooks come from an empty directory, and fsmonitor is off,
so no agent-written hook, fsmonitor command or config include runs on the host. Commits made by the
bench are deterministic (fixed identity and date). Every call has a deadline and runs in its own job.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from harness_bench import procs

_STATE = Path(tempfile.gettempdir()) / "harness-bench-git"
BENCH_IDENTITY = {
    "GIT_AUTHOR_NAME": "harness-bench", "GIT_AUTHOR_EMAIL": "bench@localhost",
    "GIT_COMMITTER_NAME": "harness-bench", "GIT_COMMITTER_EMAIL": "bench@localhost",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
}


class GitError(Exception):
    def __init__(self, args: list[str], result: procs.Completed) -> None:
        tail = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["(no output)"]
        what = "timed out" if result.timed_out else f"exit {result.returncode}"
        super().__init__(f"git {' '.join(args[:3])} {what}: {tail[0]}")
        self.result = result


def _safe_paths() -> tuple[Path, Path]:
    hooks = _STATE / "empty-hooks"
    config = _STATE / "gitconfig"
    hooks.mkdir(parents=True, exist_ok=True)
    if not config.exists():
        config.write_text("", encoding="utf-8")
    return hooks, config


def git(args: list[str], cwd: Path, timeout: float, identity: bool = False, check: bool = True) -> procs.Completed:
    hooks, config = _safe_paths()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(config), "GIT_TERMINAL_PROMPT": "0"})
    if identity:
        env.update(BENCH_IDENTITY)
    argv = ["git", "-c", "core.fsmonitor=false", "-c", f"core.hooksPath={hooks}", "-c", "core.longpaths=true",
            "-c", "core.autocrlf=false", *args]
    result = procs.run(argv, cwd=str(cwd), env=env, timeout=timeout)
    if check and (result.timed_out or result.returncode != 0):
        raise GitError(args, result)
    return result
