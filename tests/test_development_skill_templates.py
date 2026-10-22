"""Validate portable drafts with the actual MOBS format, without installing them."""
from pathlib import Path

import pytest

from services.memory.skill_format import Skill


@pytest.mark.parametrize("name", ["investigate-bug", "implement-change", "review-change"])
def test_development_draft_roundtrip(name):
    path = Path(__file__).resolve().parents[1] / "docs/development/skills" / name / "SKILL.md"
    skill = Skill.from_markdown(path.read_text(encoding="utf-8"))
    assert skill.name == name
    assert skill.status == "draft"
    assert skill.owner is None
    assert skill.requires_toolsets == []
    assert skill.procedure and skill.pitfalls and skill.verification
    assert "PROJECT_INDEX.md" in skill.procedure[0]
    assert "autoriza" in path.read_text(encoding="utf-8").lower()
    restored = Skill.from_markdown(skill.to_markdown())
    assert restored.to_dict() == skill.to_dict()
