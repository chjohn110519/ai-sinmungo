FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU 전용 torch 먼저 설치 (GPU 제외 → 이미지 크기 약 1/6로 감소)
# requirements.txt의 torch>=2.0.0은 이미 설치된 CPU 버전으로 충족됨
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# 나머지 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# KoBERT 모델을 빌드 시 미리 다운로드 (런타임 네트워크 의존성 제거)
# HF_HOME을 /app/.huggingface로 고정하여 빌드·런타임 캐시 경로 통일
ENV HF_HOME=/app/.huggingface
RUN python -c "\
from transformers import AutoTokenizer, AutoModel; \
print('Downloading skt/kobert-base-v1 ...'); \
AutoTokenizer.from_pretrained('skt/kobert-base-v1'); \
AutoModel.from_pretrained('skt/kobert-base-v1'); \
print('KoBERT download complete')"

# App code
COPY . .

# data 디렉토리 생성 (config.py의 경로와 통일)
RUN mkdir -p data/uploads data/documents data/chroma

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
