from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    text: str = Field(min_length=1)
    device_id: str = Field(default="console-unknown")
    location: str = Field(default="unknown")


class CommandResponse(BaseModel):
    ok: bool = True
    response: str
    source: str = "core"


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
