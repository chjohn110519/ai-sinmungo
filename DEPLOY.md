# AI 신문고 배포 가이드

## 로컬 개발 환경

```bash
# 1. 환경변수 설정
cp .env.example backend/.env
# backend/.env 에서 OPENAI_API_KEY 등 입력

# 2. 백엔드 실행
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# 3. 프론트엔드 실행
cd frontend
npm install
npm run dev        # http://localhost:3000
```

---

## 프로덕션 DB 설정 (SQLite → PostgreSQL)

SQLite는 Vercel/Railway 재시작 시 `/tmp/app.db`가 초기화됩니다.
`DATABASE_URL` 환경변수만 변경하면 즉시 PostgreSQL로 전환됩니다.

### Railway (권장 — 백엔드 + DB 같은 프로젝트)

1. [Railway](https://railway.app) 프로젝트 생성
2. **Add Service → Database → PostgreSQL** 클릭
3. 생성된 `DATABASE_URL` 복사 (`postgresql://...` 형식)
4. 백엔드 서비스 환경변수에 추가:
   ```
   DATABASE_URL=postgresql://postgres:password@hostname:5432/railway
   ```
5. 서버 재배포 — 테이블이 자동 생성됩니다 (`init_db()` 호출)

### Neon (Vercel 통합)

1. [Vercel Dashboard](https://vercel.com/dashboard) → **Storage** 탭 → **Connect Store**
2. **Neon** 선택 → 프로젝트 생성
3. 환경변수가 자동 주입됨 (`DATABASE_URL=postgresql://...`)
4. Preview/Production 브랜치 각각 적용 확인

### 로컬에서 PostgreSQL 테스트

```bash
# Docker로 PostgreSQL 실행
docker run -d \
  --name sinmungo-db \
  -e POSTGRES_DB=sinmungo \
  -e POSTGRES_USER=dev \
  -e POSTGRES_PASSWORD=devpass \
  -p 5432:5432 \
  postgres:15-alpine

# 환경변수 설정
export DATABASE_URL=postgresql://dev:devpass@localhost:5432/sinmungo

# 백엔드 실행 (테이블 자동 생성 확인)
cd backend && uvicorn app.main:app --reload --port 8001
```

### 마이그레이션 주의사항

- `backend/app/storage/db.py`의 `_run_migrations()`가 `ALTER TABLE`을 자동 실행합니다
- SQLite에서 PostgreSQL로 **데이터 이전이 필요한 경우** `pg_restore` 또는 별도 스크립트 작성 필요
- 데이터 이전 없이 신규 배포하는 경우 환경변수 교체만으로 충분합니다
- Alembic 자동 마이그레이션은 P2-8에서 구현 예정

---

## 환경변수 전체 목록

`/.env.example` 참조:

| 변수 | 설명 | 필수 |
|------|------|------|
| `OPENAI_API_KEY` | 모든 LLM 에이전트(gpt-4o-mini), Whisper STT | 필수 |
| `DATABASE_URL` | SQLite (로컬 기본) 또는 PostgreSQL (운영: Neon) | 운영 필수 |
| `TAVILY_API_KEY` | 웹 검색 | 선택 |
| `LAW_API_KEY` | 국가법령정보센터 Open API | 선택 |
| `ML_ENABLE_KOBERT` | KoBERT 가결 예측 on/off | 기본 true |
| `ENABLE_CHROMA` | 내부 Chroma RAG 검색 on/off (로컬 안정성을 위해 기본 false) | 선택 |
| `ADMIN_API_KEY` | 관리자 API 보호 키 | 선택 |
| `NEXT_PUBLIC_API_URL` | 프론트 → 백엔드 URL | 필수 |

---

## 운영 배포 (현재 방식): Render + Vercel + Neon

| 구성 | 플랫폼 | 플랜 | URL |
|---|---|---|---|
| 백엔드 (FastAPI, Docker) | Render `ai-sinmungo-backend` | starter (512MB) | https://ai-sinmungo-backend.onrender.com |
| 프론트엔드 (Next.js) | Vercel `ai-sinmungo` | Hobby (무료) | https://ai-sinmungo.vercel.app |
| DB (PostgreSQL) | Neon | Free (0.5GB, 만료 없음) | 외부 연결 (`DATABASE_URL`) |

### 1) Neon DB
1. [console.neon.tech](https://console.neon.tech) → New Project, Region **AWS Asia Pacific (Singapore)**
2. Dashboard → **Connect** → 연결 문자열 복사 (`postgresql://...neon.tech/neondb?sslmode=require...`)
3. 테이블·시드 데이터는 백엔드 첫 기동 시 자동 생성 (`init_db()`)

### 2) Render 백엔드
- `render.yaml` Blueprint (New → Blueprint → `chjohn110519/ai-sinmungo`, `master`)
- Environment 탭에서 입력: `DATABASE_URL`(Neon, 필수), `OPENAI_API_KEY`(필수), `TAVILY_API_KEY`·`LAW_API_KEY`(선택)
- `ADMIN_API_KEY`는 비워두기 권장 — 설정하면 프론트가 헤더 없이 호출하는 `/api/admin/stats`, `/api/session/{id}/messages`가 401
- `postgres://`·`postgresql://` 어느 형식이든 `config.py`가 `postgresql+psycopg2://`로 변환

### 3) Vercel 프론트
- Vercel 프로젝트 `ai-sinmungo`가 GitHub와 연결되어 `master` 푸시 시 자동 배포 (Root Directory: `frontend`)
- 백엔드 URL은 `frontend/vercel.json`의 `build.env`(`NEXT_PUBLIC_API_URL`, `API_URL`)에 지정
- 백엔드 CORS는 `*.vercel.app`, `*.onrender.com`을 허용 (`backend/app/main.py`)

주의사항
- `NEXT_PUBLIC_API_URL`은 빌드 시점에 번들에 포함 → 값을 바꾸면 프론트 재배포 필요
- KoBERT(가결 확률·소요 기간 예측)는 `ML_ENABLE_KOBERT=false`로 꺼져 있음. 켜려면 백엔드 플랜을 standard(2GB) 이상으로 올리고 `ML_ENABLE_KOBERT=true` 후 재배포 (Docker build arg로 torch·모델이 함께 설치됨)
- Neon Free는 5분 유휴 시 compute가 잠들어 첫 쿼리가 1초 내외 지연됨 (`pool_pre_ping`으로 끊긴 연결 자동 복구)

---

## 배포 플랫폼별 설정 (이전 방식)

### Vercel (프론트엔드)
- `frontend/` 폴더를 Vercel 프로젝트로 연결
- 환경변수: `NEXT_PUBLIC_API_URL=https://your-backend.railway.app`

### Railway (백엔드)
- `backend/` 폴더 기준, `railway.json` 설정 포함
- `DATABASE_URL`, `OPENAI_API_KEY` 등 환경변수 설정 필요
- 포트: `8001` (기본값, `PORT` 환경변수로 변경 가능)

### Docker (셀프 호스팅)
```bash
cd backend
docker build -t sinmungo-backend .
docker run -p 8001:8001 \
  -e DATABASE_URL=postgresql://... \
  -e OPENAI_API_KEY=sk-... \
  sinmungo-backend
```
