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

init_db()

app = FastAPI(
    title="AI 신문고 API",
    description="AI Agent 기반 국민신문고 민원·제안 자동 구조화 플랫폼",
    version="0.2.0",
    debug=settings.debug,
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
