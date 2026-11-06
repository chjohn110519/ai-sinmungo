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
| `OPENAI_API_KEY` | GPT-4o, Whisper STT | 권장 |
| `ANTHROPIC_API_KEY` | Claude (라우터 fallback) | 선택 |
| `DATABASE_URL` | SQLite (기본) 또는 PostgreSQL | 자동 |
| `TAVILY_API_KEY` | 웹 검색 | 선택 |
| `LAW_API_KEY` | 국가법령정보센터 Open API | 선택 |
| `ML_ENABLE_KOBERT` | KoBERT 가결 예측 on/off | 기본 true |
| `ENABLE_CHROMA` | 내부 Chroma RAG 검색 on/off (로컬 안정성을 위해 기본 false) | 선택 |
| `ADMIN_API_KEY` | 관리자 API 보호 키 | 선택 |
| `NEXT_PUBLIC_API_URL` | 프론트 → 백엔드 URL | 필수 |

---

## Render 배포 (현재 운영 방식)

저장소 루트의 `render.yaml` Blueprint 하나로 백엔드·프론트엔드·PostgreSQL이 함께 생성됩니다.

| 리소스 | 이름 | 플랜 | URL |
|---|---|---|---|
| 백엔드 (Docker) | `ai-sinmungo-backend` | starter (512MB) | https://ai-sinmungo-backend.onrender.com |
| 프론트엔드 (Node) | `ai-sinmungo` | free | https://ai-sinmungo.onrender.com |
| DB | `ai-sinmungo-db` | free (30일 후 만료) | 내부 연결 (`DATABASE_URL` 자동 주입) |

1. [Render Dashboard](https://dashboard.render.com) → **New → Blueprint** → GitHub `chjohn110519/ai-sinmungo` 선택, 브랜치 `master`
2. `sync: false` 항목 입력: `OPENAI_API_KEY`(필수), `ANTHROPIC_API_KEY`·`TAVILY_API_KEY`·`LAW_API_KEY`(선택), `ADMIN_API_KEY`(비워두기 권장 — 설정하면 프론트가 헤더 없이 호출하는 `/api/admin/stats`, `/api/session/{id}/messages`가 401)
3. **Apply** → 백엔드 `/health` 200 확인 → 프론트 접속
4. Render가 서비스 URL에 접미사를 붙인 경우(이름 중복 시) 프론트의 `NEXT_PUBLIC_API_URL`, `API_URL`을 실제 백엔드 URL로 수정 후 프론트 **Manual Deploy**

주의사항
- `NEXT_PUBLIC_API_URL`은 빌드 시점에 번들에 포함 → 값을 바꾸면 프론트 재배포 필요
- KoBERT(가결 확률·소요 기간 예측)는 `ML_ENABLE_KOBERT=false`로 꺼져 있음. 켜려면 백엔드 플랜을 standard(2GB) 이상으로 올리고 `ML_ENABLE_KOBERT=true` 후 재배포 (Docker build arg로 torch·모델이 함께 설치됨)
- Free Postgres는 생성 30일 후 만료 → 유지하려면 DB 플랜 업그레이드
- 프론트 free 플랜은 15분 무요청 시 슬립 (첫 접속 30~60초)

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
