from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillResult:
    ok: bool
    message: str
    skill_id: str
    route: str = "skill"
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_command_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "response": self.message,
            "source": "core",
            "route": self.route,
            "skill_id": self.skill_id,
        }
        if self.data:
            payload["data"] = self.data
        if self.error:
            payload["error"] = self.error
        return payload
