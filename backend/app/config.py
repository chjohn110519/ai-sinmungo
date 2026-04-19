import os
from typing import Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

# Vercel 환경에서는 /tmp 경로 사용
_IS_VERCEL = bool(os.environ.get("VERCEL"))
_DEFAULT_DB = "sqlite:////tmp/app.db" if _IS_VERCEL else "sqlite:///./data/app.db"
_DEFAULT_CHROMA = "/tmp/chroma" if _IS_VERCEL else "./chroma_db"


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=False, extra="allow")

    # API Keys
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Database
    database_url: str = _DEFAULT_DB

    # Chroma
    chroma_persist_directory: str = _DEFAULT_CHROMA

    # Models
    embedding_model_name: str = "jhgan/ko-sroberta-multitask"
    llm_model_name: str = "claude-3-5-sonnet-20241022"
    anthropic_model_name: str = "claude-3-5-sonnet-20241022"
    openai_model_name: str = "gpt-3.5-turbo"
    backend_model: str = "gpt-4o-mini"

    # 국가법령정보센터 API (https://open.law.go.kr 에서 발급)
    law_api_key: Optional[str] = None

    # STT
    whisper_model_size: str = "base"

    # App
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()