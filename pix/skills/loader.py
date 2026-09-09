"""Load markdown skill instructions from disk."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Skill:
    """A loaded markdown skill."""

    name: str
    path: Path
    content: str

    def instruction(self) -> str:
        return f"## Skill: {self.name}\n{self.content}"


def load_skill(path: str | Path) -> Skill:
    skill_path = Path(path)
    if not skill_path.is_file():
        raise FileNotFoundError(f"Skill file not found: {skill_path}")
    return Skill(
        name=skill_path.stem,
        path=skill_path.resolve(),
        content=skill_path.read_text(encoding="utf-8"),
    )


def load_skills(directory: str | Path) -> list[Skill]:
    root = Path(directory)
    if not root.is_dir():
        return []
    skills: list[Skill] = []
    for path in sorted(root.glob("*.md")):
        if path.name.lower() in {"readme.md", "index.md"}:
            continue
        skills.append(load_skill(path))
    return skills
