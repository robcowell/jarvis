from dataclasses import dataclass

from core.skills.base import BaseSkill, SkillContext
from core.skills.registry import SkillRegistry
from core.skills.result import SkillResult


@dataclass(frozen=True)
class SkillMatch:
    trigger: str
    skill: BaseSkill
    priority: int


class CommandRouter:
    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def route(self, text: str) -> SkillMatch | None:
        normalized = text.strip().lower()
        if not normalized:
            return None

        matches: list[SkillMatch] = []
        for loaded in self.registry.skills:
            for phrase in loaded.manifest.trigger_phrases:
                if phrase in normalized:
                    matches.append(
                        SkillMatch(
                            trigger=phrase,
                            skill=loaded.instance,
                            priority=loaded.manifest.priority,
                        )
                    )

        if not matches:
            return None

        # Deterministic ordering: longest trigger wins, then priority, then skill id.
        matches.sort(key=lambda m: (-len(m.trigger), m.priority, m.skill.skill_id))
        return matches[0]

    def execute(self, text: str, device_id: str, location: str) -> SkillResult | None:
        match = self.route(text)
        if match is None:
            return None
        context = SkillContext(text=text, device_id=device_id, location=location)
        return match.skill.execute(context)
