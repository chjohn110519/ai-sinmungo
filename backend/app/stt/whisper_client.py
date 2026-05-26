"""STT 모듈 — OpenAI Whisper API 사용 (cloud).

로컬 whisper 대신 OpenAI API를 호출하므로 torch/GPU 의존성이 없습니다.
AsyncOpenAI 사용 — FastAPI async 환경에서 Connection error 방지.
"""

from io import BytesIO
from pathlib import Path

from app.config import settings


async def transcribe_audio(audio_data: bytes, filename: str = "recording.webm") -> tuple[str, float]:
    """음성 바이트를 텍스트로 변환 (비동기).

    Returns:
        (transcript, confidence) — confidence는 항상 0.9 (API가 미제공)

    Raises:
        ValueError: OPENAI_API_KEY 미설정 또는 빈 오디오
        Exception: Whisper API 오류 (그대로 전파)
    """
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    if not audio_data:
        raise ValueError("오디오 데이터가 비어 있습니다.")

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # BytesIO + (filename, buffer) 튜플: OpenAI 클라이언트가 파일명으로 포맷 감지
    safe_filename = Path(filename).name or "recording.webm"
    audio_buf = BytesIO(audio_data)

    result = await client.audio.transcriptions.create(
        model="whisper-1",
        file=(safe_filename, audio_buf),
        language="ko",
        response_format="text",
    )

    transcript = result.strip() if isinstance(result, str) else str(result).strip()
    return transcript, 0.9
