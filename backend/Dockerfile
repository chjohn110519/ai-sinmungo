FROM python:3.11-slim

WORKDIR /app

# KoBERT 포함 여부 (Render는 같은 이름의 환경변수를 build arg로 자동 전달)
#   false: torch/transformers 미설치 → 이미지 작고 RAM 512MB 플랜에서 구동 가능
#   true : CPU torch + KoBERT 모델을 이미지에 포함 → RAM 2GB 이상 필요
ARG ML_ENABLE_KOBERT=false
ENV ML_ENABLE_KOBERT=${ML_ENABLE_KOBERT}
# HF_HOME을 /app/.huggingface로 고정하여 빌드·런타임 캐시 경로 통일
ENV HF_HOME=/app/.huggingface \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps (build-essential에 lightgbm 런타임에 필요한 libgomp1 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ml.txt ./

RUN pip install -r requirements.txt

# KoBERT 활성화 시에만 CPU 전용 torch + 모델 다운로드 (런타임 네트워크 의존성 제거)
RUN if [ "$ML_ENABLE_KOBERT" = "true" ]; then \
      pip install torch --index-url https://download.pytorch.org/whl/cpu && \
      pip install -r requirements-ml.txt && \
      python -c "from transformers import AutoTokenizer, AutoModel; \
AutoTokenizer.from_pretrained('skt/kobert-base-v1'); \
AutoModel.from_pretrained('skt/kobert-base-v1'); \
print('KoBERT download complete')"; \
    else \
      echo 'ML_ENABLE_KOBERT=false — torch/KoBERT 설치 생략'; \
    fi

# App code
COPY . .

# data 디렉토리 생성 (config.py의 경로와 통일)
RUN mkdir -p data/uploads data/documents data/chroma

EXPOSE 8000

# Render는 PORT 환경변수(기본 10000)를 주입한다
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips="*"
