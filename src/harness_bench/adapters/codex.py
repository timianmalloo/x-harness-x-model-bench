"""Codex CLI adapter.

Headless invocation recorded in the proposal: `codex exec --model <id> --json --full-auto`.
JSONL carries turn.completed usage. OTel metrics were reported missing in exec mode (openai/codex#12913).
Spec: S-06 (docs/specs/README.md).
"""

from harness_bench.adapters.base import HarnessAdapter


class Adapter(HarnessAdapter):
    harness = "codex"
    coord_harness = "codex"
