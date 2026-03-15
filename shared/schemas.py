from pydantic import BaseModel, Field
from typing import Any


class CommandRequest(BaseModel):
    text: str = Field(min_length=1)
    device_id: str = Field(default="console-unknown")
    location: str = Field(default="unknown")


class CommandResponse(BaseModel):
    ok: bool = True
    response: str
    source: str = "core"
    route: str = "llm"
    skill_id: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None


class TranscribeResponse(BaseModel):
    ok: bool = True
    text: str
    source: str = "core"


class TtsRequest(BaseModel):
    text: str = Field(min_length=1)


class HealthResponse(BaseModel):
    ok: bool = True
    service: str = "jarvis-core"
    status: str = "healthy"
    version: str = "0.1.0"
    build_datetime: str = "unknown"


class VersionResponse(BaseModel):
    ok: bool = True
    service: str = "jarvis-core"
    version: str = "0.1.0"
    build_datetime: str = "unknown"


class SkillInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    entry_class: str
    trigger_phrases: list[str] = Field(default_factory=list)
    priority: int = 100
    enabled: bool = True
    path: str


class SkillsResponse(BaseModel):
    ok: bool = True
    count: int = 0
    skills: list[SkillInfo] = Field(default_factory=list)
