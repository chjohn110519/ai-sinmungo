import os
from typing import Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=False, extra="allow")
    
    # API Keys
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Chroma
    chroma_persist_directory: str = "./data/chroma"

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