"""The adapter contract every harness implements.

Workers are launched by the pack's coord-runner.py (coord-run/1), not by adapters directly.
An adapter owns what differs per harness: the argv, the model pin, where its session log lives,
and how to read its usage summary. Spec: S-06 (docs/specs/README.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Invocation:
    argv: list[str]
    binding_files: list[str]
    env: dict[str, str]


class HarnessAdapter:
    harness: str = ""        # name in matrix.yaml
    coord_harness: str = ""  # name coord-runner.py expects: claude | codex | copilot | grok | agy

    def invocation(self, model: str, worktree: Path) -> Invocation:
        raise NotImplementedError(f"{self.harness} adapter is not built yet; spec S-06")

    def session_log(self, worktree: Path) -> Path | None:
        raise NotImplementedError(f"{self.harness} adapter is not built yet; spec S-06")
