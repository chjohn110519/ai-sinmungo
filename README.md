# AI 신문고

AI Agent 기반 국민신문고 민원·제안 자동 구조화 및 처리 효율화 플랫폼

## 프로젝트 개요

시민이 자연어로 문제를 입력하면, AI Agent가 민원·제안·청원을 자동 분류·구조화하고, 정책 제안의 경우 법안 수준의 제안서 생성과 타당성 검증까지 수행하는 국민신문고 보조 플랫폼.

## 기술 스택

### Backend
- **FastAPI**: REST API 서버
- **LangGraph**: 멀티 에이전트 파이프라인 오케스트레이션
- **Anthropic Claude**: LLM (선택적 모델 통합)
- **Ko-SBERT**: 한국어 문서 임베딩
- **Chroma**: 벡터 데이터베이스
- **SQLite**: 관계형 데이터베이스

### Frontend
- **Next.js 14**: React 프레임워크
- **TypeScript**: 타입 안전성
- **Tailwind CSS**: 스타일링
- **Recharts**: 데이터 시각화
- **JUT_AI신문고**: 브랜딩과 대화형 UI 디자인

## 설치 및 실행

### Backend

```bash
cd backend
pip install -e .
python -m app.main
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 개발 마일스톤

### M1. 데이터·MVP 기반 (진행 중)
- [x] 프로젝트 구조 생성
- [x] FastAPI + Next.js 스캐폴딩
- [x] AI Router 구현 (Claude API + Instructor)
- [ ] Chroma에 법령·법안 인덱싱
- [ ] 프론트 최소 UI (채팅 박스 + 라우팅 결과 표시)

### M2. 핵심 AI 모델
- [ ] LangGraph 파이프라인 연결
- [ ] LLM1·2·3·4 프롬프트 및 Instructor 스키마 확정
- [ ] RAG 검색 품질 평가 및 프롬프트 튜닝
- [ ] Ko-SBERT 임베딩 파이프라인
- [ ] MLP 학습 (통과 확률·예상 소요 시간)
- [ ] 분석 결과 시각화

### M3. 고도화·통합
- [ ] 음성 입력(Whisper) 통합
- [ ] 통합 테스트 시나리오 3종
- [ ] UI/UX 개선 (스트리밍·프로그레스바)
- [ ] 최종 지표 측정 및 리포트

## API 엔드포인트

- `POST /api/chat`: 채팅 메시지 분류
- `POST /api/voice/transcribe`: 음성 텍스트 변환
- `GET /api/session/{session_id}`: 세션 정보 조회
- `GET /api/session/{session_id}/result`: 세션 결과 조회

## 환경 변수

`.env` 파일에 다음 변수를 설정하세요:

```
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key  # 선택사항
```

## 라이선스

이 프로젝트는 교육 및 연구 목적으로만 사용됩니다.