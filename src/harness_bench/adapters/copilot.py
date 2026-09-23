"""GitHub Copilot CLI adapter.

Headless invocation recorded in the proposal: `copilot -p <prompt> --model <id> --allow-all-tools --autopilot --share`.
Bills in premium requests: cost is NA unless a token count and list price both exist. coord-runner requires ACP,
one pinned non-auto model, and a committed .github/allowed_models.txt.
Spec: S-06 (docs/specs/README.md).
"""

from harness_bench.adapters.base import HarnessAdapter


class Adapter(HarnessAdapter):
    harness = "copilot"
    coord_harness = "copilot"
