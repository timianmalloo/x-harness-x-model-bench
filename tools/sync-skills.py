"""Copy this repo's own skills from skills/<name>/ to every harness surface that reads them.

skills/ is the source. .claude/skills/<name>/ (Claude Code) and .agents/skills/<name>/ (Codex,
Antigravity) are generated copies; tests/test_skills_in_sync.py fails when they drift.
The pack's own skills in those folders are owned by pack-apply.py and are never touched here.

Usage: python tools/sync-skills.py
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills"
SURFACES = (ROOT / ".claude" / "skills", ROOT / ".agents" / "skills")


def main() -> int:
    for skill in sorted(d for d in SOURCE.iterdir() if d.is_dir()):
        for surface in SURFACES:
            dest = surface / skill.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill, dest)
            print(f"synced {skill.name} -> {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
