"""Registry of skills available to agents."""

from __future__ import annotations

from typing import TypeAlias

from pix.skills.loader import Skill

SkillList: TypeAlias = list[Skill]
SkillNames: TypeAlias = list[str]
SkillTexts: TypeAlias = list[str]


class SkillRegistry:
    def __init__(self, skills: list[Skill] | None = None) -> None:
        self._skills: dict[str, Skill] = {}
        for skill in skills or []:
            self.register(skill)

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def list(self) -> SkillList:
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def names(self) -> SkillNames:
        return sorted(self._skills)

    def instruction_texts(self, names: SkillNames | None = None) -> SkillTexts:
        selected = names or self.names()
        return [self._skills[name].instruction() for name in selected if name in self._skills]
