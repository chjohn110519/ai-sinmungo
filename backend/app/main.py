import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_chat import router as chat_router
from app.api.routes_voice import router as voice_router
from app.api.routes_result import router as result_router
from app.api.routes_admin import router as admin_router
from app.api.routes_bill import router as bill_router
from app.api.routes_upload import router as upload_router
from app.api.routes_conversation import router as conversation_router
from app.api.routes_cluster import router as cluster_router
from app.config import settings
from app.storage.db import init_db

logger = logging.getLogger(__name__)

init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 ML 모델을 사전 로드한다.
    로드 실패해도 서버는 정상 기동 — 해당 기능만 휴리스틱으로 fallback.
    """
    try:
        from app.ml import get_registry
        registry = get_registry()
        logger.info(
            "ML 모델 사전 로드 완료 | 위원회추천: %s | 가결예측: %s",
            "활성화" if registry.committee_enabled else "비활성화",
            "활성화" if registry.approval_enabled else "비활성화",
        )
    except Exception as exc:
        logger.warning("ML 모델 로드 실패 (휴리스틱으로 동작): %s", exc)
    yield  # 서버 실행 중


app = FastAPI(
    title="AI 신문고 API",
    description="AI Agent 기반 국민신문고 민원·제안 자동 구조화 플랫폼",
    version="0.2.0",
    debug=settings.debug,
    lifespan=lifespan,
)

import os as _os

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "https://frontend-bay-nine-83.vercel.app",
]
# 환경변수로 추가 도메인 허용
_extra = _os.environ.get("CORS_ORIGINS", "")
if _extra:
    _ALLOWED_ORIGINS.extend([o.strip() for o in _extra.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(voice_router, prefix="/api", tags=["voice"])
app.include_router(result_router, prefix="/api", tags=["result"])
app.include_router(admin_router, prefix="/api", tags=["admin"])
app.include_router(bill_router, prefix="/api", tags=["bill"])
app.include_router(upload_router, prefix="/api", tags=["upload"])
app.include_router(conversation_router, prefix="/api", tags=["conversation"])
app.include_router(cluster_router, prefix="/api", tags=["cluster"])


@app.get("/")
async def root():
    return {"message": "AI 신문고 API", "version": "0.2.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
