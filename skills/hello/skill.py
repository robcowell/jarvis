from datetime import datetime

from core.skills.base import BaseSkill, SkillContext
from core.skills.result import SkillResult


class HelloSkill(BaseSkill):
    def execute(self, context: SkillContext) -> SkillResult:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        message = f"Hello. Skill '{self.skill_id}' is online. Local time is {timestamp}."

        if context.location and context.location != "unknown":
            message = f"{message} You are marked as being in {context.location}."

        return SkillResult(
            ok=True,
            message=message,
            skill_id=self.skill_id,
            data={"device_id": context.device_id, "location": context.location},
        )
