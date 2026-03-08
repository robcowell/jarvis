import platform
from datetime import datetime

from core.skills.base import BaseSkill, SkillContext
from core.skills.result import SkillResult


class SystemStatusSkill(BaseSkill):
    def execute(self, context: SkillContext) -> SkillResult:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system = platform.system() or "unknown"
        release = platform.release() or "unknown"
        python_version = platform.python_version()

        message = (
            f"System status is healthy. Host OS: {system} {release}. "
            f"Python: {python_version}. Checked at {now}."
        )

        return SkillResult(
            ok=True,
            message=message,
            skill_id=self.skill_id,
            data={
                "checked_at": now,
                "system": system,
                "release": release,
                "python_version": python_version,
                "device_id": context.device_id,
                "location": context.location,
            },
        )
