"""Build coord-run/1 contracts for a batch of cells, for docs/ai-forward-pack/scripts/coord-runner.py.

Limits the runner enforces (read from coord-runner.py, pack revision 92):
- 1-8 workers per contract, parallelism 1-4
- worker deadline_seconds 1-3600, so no task budget may exceed 60 minutes
- runtime.max_turns 1-8 counts prompts sent over ACP, not agent tool turns
- prompts are completed /compile audit ids (CO-S0), not raw text
- harness in claude | codex | grok | agy | copilot; ACP transport except agy
- each worker gets a new session id and a new branch; worktrees come from the invoking checkout
Spec: S-05 (docs/specs/README.md).
"""

from harness_bench.plan import Cell


def contract(run_id: str, owner: str, cells: list[Cell], parallelism: int) -> dict:
    raise NotImplementedError("runner.coord_contract is not built yet; spec S-05")
