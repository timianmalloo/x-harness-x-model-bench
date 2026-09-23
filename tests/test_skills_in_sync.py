from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACES = (ROOT / ".claude" / "skills", ROOT / ".agents" / "skills")


def _files(d: Path) -> dict[str, bytes]:
    return {str(f.relative_to(d)): f.read_bytes() for f in d.rglob("*") if f.is_file()}


def test_repo_skills_match_every_surface():
    for skill in (d for d in (ROOT / "skills").iterdir() if d.is_dir()):
        for surface in SURFACES:
            copy = surface / skill.name
            assert copy.is_dir(), f"{copy} missing: run python tools/sync-skills.py"
            assert _files(copy) == _files(skill), f"{copy} drifted: run python tools/sync-skills.py"
