"""Copilot CLI session reader: ~/.copilot/session-store.db and session-state/<id>/events.jsonl.

Wraps docs/ai-forward-pack/scripts/session-profile.py (harness=copilot).
Output: one normalised event stream (prompt, model call, tool call, edit, test run, subagent spawn)
and per-turn usage, in OpenTelemetry GenAI attribute names. Spec: S-07 (docs/specs/README.md).
"""

from pathlib import Path


def read(run_dir: Path) -> list[dict]:
    raise NotImplementedError("telemetry.copilot is not built yet; spec S-07")
