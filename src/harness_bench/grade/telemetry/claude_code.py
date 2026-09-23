"""Claude Code session reader: ~/.claude/projects/<slug>/<session>.jsonl and subagents/.

Wraps docs/ai-forward-pack/scripts/session-profile.py (harness=claude).
Output: one normalised event stream (prompt, model call, tool call, edit, test run, subagent spawn)
and per-turn usage, in OpenTelemetry GenAI attribute names. Spec: S-07 (docs/specs/README.md).
"""

from pathlib import Path


def read(run_dir: Path) -> list[dict]:
    raise NotImplementedError("telemetry.claude_code is not built yet; spec S-07")
