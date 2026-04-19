"""STT 모듈 — OpenAI Whisper API 사용 (cloud).

로컬 whisper 대신 OpenAI API를 호출하므로 torch/GPU 의존성이 없습니다.
OPENAI_API_KEY가 없으면 빈 문자열을 반환합니다.
"""

import tempfile
import os
from pathlib import Path

from app.config import settings


def transcribe_audio(audio_data: bytes, filename: str = "recording.webm") -> tuple[str, float]:
    """음성 바이트를 텍스트로 변환.

    Returns:
        (transcript, confidence) — confidence는 항상 0.9 (API가 미제공)
    """
    if not settings.openai_api_key:
        return "", 0.0

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        # 임시 파일로 저장 (API는 파일 객체를 요구)
        suffix = Path(filename).suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="ko",
                    response_format="text",
                )
            transcript = result.strip() if isinstance(result, str) else str(result).strip()
            return transcript, 0.9
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        print(f"[STT] Whisper API 오류: {e}")
        return "", 0.0
