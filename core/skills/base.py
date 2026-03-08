from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.skills.manifest import SkillManifest
from core.skills.result import SkillResult


@dataclass(frozen=True)
class SkillContext:
    text: str
    device_id: str
    location: str


class BaseSkill(ABC):
    def __init__(self, manifest: SkillManifest) -> None:
        self.manifest = manifest

    @property
    def skill_id(self) -> str:
        return self.manifest.skill_id

    @abstractmethod
    def execute(self, context: SkillContext) -> SkillResult:
        """Run the skill against the provided command context."""
