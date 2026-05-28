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

    # API Keys (strip whitespace/newlines in case env var was set with trailing newline)
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    def model_post_init(self, __context):
        """환경변수에 포함된 줄바꿈/공백 제거."""
        if self.openai_api_key:
            object.__setattr__(self, "openai_api_key", self.openai_api_key.strip())
        if self.anthropic_api_key:
            object.__setattr__(self, "anthropic_api_key", self.anthropic_api_key.strip())
        if self.tavily_api_key:
            object.__setattr__(self, "tavily_api_key", self.tavily_api_key.strip())

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

    # Tavily Search API (https://app.tavily.com 에서 발급, 월 1,000회 무료)
    tavily_api_key: Optional[str] = None

    # STT
    whisper_model_size: str = "base"

    # ML 모델 설정
    # ML_ENABLE_KOBERT=false 로 설정하면 KoBERT 로딩을 건너뜀 (메모리 절약, 배포 환경 최적화)
    ml_enable_kobert: bool = True
    # ml_assets_dir: 빈 문자열이면 app/ml_assets/ 로 자동 결정
    ml_assets_dir: str = ""
    # HuggingFace 모델 캐시 경로 (비어있으면 기본값 ~/.cache/huggingface 사용)
    huggingface_cache_dir: Optional[str] = None

    # App
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()