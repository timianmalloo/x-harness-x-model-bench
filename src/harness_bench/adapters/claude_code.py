"""Claude Code adapter.

Headless invocation recorded in the proposal: `claude -p --model <id> --output-format json`.
The JSON result carries cost, duration, turns and usage.
Spec: S-06 (docs/specs/README.md).
"""

from harness_bench.adapters.base import HarnessAdapter


class Adapter(HarnessAdapter):
    harness = "claude-code"
    coord_harness = "claude"
