"""Offline pin for the Copilot US-13 canary classes (plan rows 12/13, R-16 c2). No live turn, no credentials mark:
runs in the default suite.

A dropped class fails here. Canary strings are unique per class; a string shared by two classes still reports both.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEEDED_PAIRS = {
    ("HB-US13-COPILOT-INSTRUCTION", "instruction"),
    ("hb-us13-copilot-skill", "skill"),
    ("HB-US13-COPILOT-HOOK", "hook"),
    ("gpt-6-astra", "settings model"),
    ("hb-us13-agents-skill", "skill (~/.agents/skills, via USERPROFILE)"),
    ("hb-us13-claude-skill", "skill (~/.claude/skills, via USERPROFILE)"),
}


def _canary_module():
    spec = importlib.util.spec_from_file_location("us13_canary_classes", ROOT / "tests" / "e2e" / "test_us13_canary.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_copilot_fake_profile_seeds_the_exact_canary_class_set(tmp_path):
    module = _canary_module()
    profile = module._fake_profile(tmp_path / "control")
    assert profile.resolve().is_relative_to(tmp_path.resolve())
    assert profile.resolve() != Path.home().resolve()

    pairs = module._seed_copilot_control(profile / ".copilot")
    assert pairs == SEEDED_PAIRS
    assert len({canary for canary, _ in pairs}) == len(pairs)  # canary strings are unique per class
    assert (profile / ".agents" / "skills" / "hb-us13-agents-skill" / "SKILL.md").is_file()
    assert (profile / ".claude" / "skills" / "hb-us13-claude-skill" / "SKILL.md").is_file()

    record = "\n".join(canary for canary, cls in SEEDED_PAIRS if cls not in {"hook", "settings model"})
    marker = profile / ".copilot" / module.COPILOT_HOOK_FILE
    marker.write_text(module.COPILOT_HOOK, encoding="utf-8")
    shown = module._copilot_shown(record, {module.COPILOT_SETTINGS_MODEL}, profile / ".copilot")
    assert set(shown) == {cls for _, cls in pairs}
    assert all(shown.values())


def test_classes_hit_by_reports_every_class_a_shared_string_belongs_to():
    module = _canary_module()
    colliding = {("graphify", "instruction file"), ("graphify", "skill")}
    assert module._classes_hit_by(colliding, "graphify") == {"instruction file", "skill"}
