"""STT 모듈 — OpenAI Whisper API 직접 호출 (httpx).

OpenAI SDK 대신 httpx를 직접 사용:
- Vercel 서버리스(Mangum)에서 OpenAI SDK Connection error 우회
- httpx는 이미 FastAPI 의존성에 포함되어 있어 별도 설치 불필요
"""

from io import BytesIO
from pathlib import Path

import httpx

from app.config import settings

WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)


async def transcribe_audio(audio_data: bytes, filename: str = "recording.webm") -> tuple[str, float]:
    """음성 바이트를 텍스트로 변환 (httpx → Whisper API 직접 호출).

    Returns:
        (transcript, confidence) — confidence는 항상 0.9

    Raises:
        ValueError: API 키 미설정 또는 빈 오디오
        httpx.HTTPStatusError: Whisper API 오류 응답
        httpx.RequestError: 네트워크 연결 실패
    """
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    if not audio_data:
        raise ValueError("오디오 데이터가 비어 있습니다.")

    safe_filename = Path(filename).name or "recording.webm"

    # Content-Type 추론
    ext = Path(safe_filename).suffix.lower()
    mime_map = {
        ".webm": "audio/webm",
        ".mp4": "audio/mp4",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
    }
    content_type = mime_map.get(ext, "audio/webm")

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            WHISPER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={
                "file": (safe_filename, BytesIO(audio_data), content_type),
            },
            data={
                "model": "whisper-1",
                "language": "ko",
                "response_format": "text",
            },
        )
        response.raise_for_status()

    transcript = response.text.strip()
    return transcript, 0.9
