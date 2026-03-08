from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

from core import services
from shared.schemas import (
    CommandRequest,
    CommandResponse,
    HealthResponse,
    SkillInfo,
    SkillsResponse,
    TranscribeResponse,
    TtsRequest,
)

app = FastAPI(title="J.A.R.V.I.S. Core", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)) -> TranscribeResponse:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    text = services.transcribe_file_bytes(file.filename or "input.wav", audio_bytes)
    return TranscribeResponse(text=text)


@app.post("/command", response_model=CommandResponse)
def command(body: CommandRequest) -> CommandResponse:
    payload = services.command(body.text, body.device_id, body.location)
    return CommandResponse(**payload)


@app.post("/tts")
def tts(body: TtsRequest) -> Response:
    wav = services.tts_wav_bytes(body.text)
    return Response(content=wav, media_type="audio/wav")


@app.get("/skills", response_model=SkillsResponse)
def skills() -> SkillsResponse:
    records = services.list_skills()
    return SkillsResponse(
        ok=True,
        count=len(records),
        skills=[SkillInfo(**record) for record in records],
    )
