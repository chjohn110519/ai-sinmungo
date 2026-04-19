from fastapi import APIRouter, UploadFile, File, HTTPException
from app.stt.whisper_client import transcribe_audio
from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    transcript: str
    confidence: float


router = APIRouter()

ALLOWED_AUDIO_TYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/mpeg",
    "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/flac",
    "audio/aac", "video/webm",  # Chrome이 video/webm으로 보내기도 함
}


@router.post("/voice/transcribe", response_model=TranscriptionResponse)
async def transcribe_voice(audio: UploadFile = File(...)):
    """음성 파일을 텍스트로 변환 (OpenAI Whisper API)."""
    content_type = (audio.content_type or "").lower()
    if content_type not in ALLOWED_AUDIO_TYPES and not content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="오디오 파일만 지원됩니다")

    try:
        audio_data = await audio.read()
        filename = audio.filename or "recording.webm"
        transcript, confidence = transcribe_audio(audio_data, filename)

        if not transcript:
            raise HTTPException(status_code=422, detail="음성을 인식할 수 없습니다. 다시 시도해 주세요.")

        return TranscriptionResponse(transcript=transcript, confidence=confidence)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"음성 인식 중 오류 발생: {str(e)}")
