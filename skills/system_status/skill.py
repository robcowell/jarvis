import platform
from datetime import datetime
import os

from core import __build_datetime__ as CORE_BUILD_DATETIME
from core import __version__ as CORE_VERSION
from core.skills.base import BaseSkill, SkillContext
from core.skills.result import SkillResult


class SystemStatusSkill(BaseSkill):
    def execute(self, context: SkillContext) -> SkillResult:
        normalized = (context.text or "").strip().lower()
        console_version = os.getenv("JARVIS_CONSOLE_VERSION", "unknown").strip() or "unknown"
        console_build = os.getenv("JARVIS_CONSOLE_BUILD_DATETIME", "unknown").strip() or "unknown"

        if "core version" in normalized or "core build" in normalized:
            return SkillResult(
                ok=True,
                message=f"Core version is {CORE_VERSION}. Build datetime is {CORE_BUILD_DATETIME}.",
                skill_id=self.skill_id,
                data={
                    "service": "jarvis-core",
                    "core_version": CORE_VERSION,
                    "core_build_datetime": CORE_BUILD_DATETIME,
                    "device_id": context.device_id,
                    "location": context.location,
                },
            )

        if "console version" in normalized or "console build" in normalized:
            return SkillResult(
                ok=True,
                message=f"Console version is {console_version}. Build datetime is {console_build}.",
                skill_id=self.skill_id,
                data={
                    "service": "jarvis-console",
                    "console_version": console_version,
                    "console_build_datetime": console_build,
                    "device_id": context.device_id,
                    "location": context.location,
                },
            )

        if "version" in normalized:
            return SkillResult(
                ok=True,
                message=(
                    f"Core version is {CORE_VERSION} built at {CORE_BUILD_DATETIME}. "
                    f"Console version is {console_version} built at {console_build}."
                ),
                skill_id=self.skill_id,
                data={
                    "core_version": CORE_VERSION,
                    "core_build_datetime": CORE_BUILD_DATETIME,
                    "console_version": console_version,
                    "console_build_datetime": console_build,
                    "device_id": context.device_id,
                    "location": context.location,
                },
            )

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
