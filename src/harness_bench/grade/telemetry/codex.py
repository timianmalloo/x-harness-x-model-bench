"""Codex session reader: ~/.codex/sessions rollout JSONL plus `codex exec --json` turn.completed usage.

NEW: session-profile.py has no Codex reader. First grader to build.
Output: one normalised event stream (prompt, model call, tool call, edit, test run, subagent spawn)
and per-turn usage, in OpenTelemetry GenAI attribute names. Spec: S-07 (docs/specs/README.md).
"""

from pathlib import Path


def read(run_dir: Path) -> list[dict]:
    raise NotImplementedError("telemetry.codex is not built yet; spec S-07")
