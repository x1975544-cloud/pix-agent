from __future__ import annotations

from pix.skills.loader import load_skills
from pix.skills.registry import SkillRegistry


def test_load_and_registry(tmp_path):
    (tmp_path / "coding.md").write_text("# Coding\nKeep changes focused.\n", encoding="utf-8")
    skills = load_skills(tmp_path)
    assert [skill.name for skill in skills] == ["coding"]
    registry = SkillRegistry(skills)
    assert registry.names() == ["coding"]
    assert "Keep changes focused" in registry.instruction_texts()[-1]
    assert registry.get("coding") is not None


def test_load_skills_missing_directory_returns_empty(tmp_path):
    assert load_skills(tmp_path / "missing") == []
