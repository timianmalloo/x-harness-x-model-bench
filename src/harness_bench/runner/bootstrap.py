"""Build a cell's workspace: clone the task base commit, apply pack=on or pack=off, warm the build.

Spec: S-05 (docs/specs/README.md).
"""

from pathlib import Path

# pack=off strips these from a workspace that carries the pack (ai-de and cfd-bench already do).
# Source: proposal, "Design rules". The managed blocks in AGENTS.md / CLAUDE.md are removed too.
PACK_OFF_STRIP = (
    ".claude/",
    ".github/",
    ".agents/",
    ".codex/",
    ".grok/",
    "docs/ai-forward-pack/",
)
MANAGED_BLOCK_FILES = ("AGENTS.md", "CLAUDE.md")
MANAGED_BLOCK_MARKERS = ("AI-FORWARD-PACK:BEGIN", "AI-FORWARD-PACK:END")


def bootstrap(task_dir: Path, pack: str, dest: Path) -> str:
    """Return the tree hash of the prepared workspace."""
    raise NotImplementedError("runner.bootstrap is not built yet; spec S-05")
