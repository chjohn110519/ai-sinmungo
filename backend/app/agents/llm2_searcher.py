from app.rag.retriever import RAGRetriever
from app.rag.law_api import search_laws, search_precedents
from app.schemas.proposal import StructuredProblem
from app.config import settings

try:
    import instructor
    from anthropic import Anthropic
    from openai import OpenAI
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False
    try:
        from openai import OpenAI
    except ImportError:
        OpenAI = None
    try:
        from anthropic import Anthropic
    except ImportError:
        Anthropic = None


class LLM2Searcher:
    """관련 법령 및 유사 사례를 검색하는 RAG + 국가법령정보센터 API 에이전트."""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.retriever = RAGRetriever(persist_dir)
        self.openai_client = None
        self.anthropic_client = None

        # LLM 클라이언트 초기화 (법령 fallback용)
        if settings.openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=settings.openai_api_key)
            except Exception:
                pass
        if settings.anthropic_api_key:
            try:
                self.anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
            except Exception:
                pass

        # Chroma 컬렉션에 샘플 데이터가 없으면 초기화
        if settings.openai_api_key:
            try:
                from app.rag.indexer import RAGIndexer
                indexer = RAGIndexer(persist_dir)
                indexer.initialize_with_sample_data()
            except Exception as e:
                print(f"[LLM2] Chroma 초기화 실패 (무시됨): {e}")

    def _llm_suggest_laws(self, problem_desc: str, classification: str, responsible_dept: str) -> list[dict]:
        """RAG/API 검색이 빈 결과일 때 LLM에게 직접 관련 법령을 물어봅니다."""
        prompt = (
            f"다음 {classification} 내용과 관련된 대한민국 실제 법령 이름 7개를 나열하세요.\n"
            f"담당 부처: {responsible_dept}\n"
            f"내용: {problem_desc}\n\n"
            "형식: 각 법령명을 줄바꿈으로 구분. 법령명만 쓰고 설명 없이 반환하세요.\n"
            "예시:\n주택임대차보호법\n민법\n행정절차법"
        )

        law_names: list[str] = []

        if self.anthropic_client is not None:
            try:
                response = self.anthropic_client.messages.create(
                    model=settings.anthropic_model_name,
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text
                law_names = [l.strip() for l in text.strip().splitlines() if l.strip()]
            except Exception as e:
                print(f"[LLM2] Anthropic 법령 제안 오류: {e}")

        if not law_names and self.openai_client is not None:
            try:
                response = self.openai_client.chat.completions.create(
                    model=settings.openai_model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=256,
                    temperature=0.2,
                )
                text = response.choices[0].message.content
                law_names = [l.strip() for l in text.strip().splitlines() if l.strip()]
            except Exception as e:
                print(f"[LLM2] OpenAI 법령 제안 오류: {e}")

        if not law_names:
            # LLM도 실패하면 부처별 기본 법령 반환
            law_names = _dept_default_laws(responsible_dept, classification)

        return [
            {"doc_id": f"llm-{i}", "title": name, "snippet": "", "relevance": 0.7, "source": "AI제안"}
            for i, name in enumerate(law_names[:7])
        ]

    def search_related_laws(self, problem: StructuredProblem, top_k: int = 5) -> list[dict]:
        """RAG 벡터 검색 + 국가법령정보센터 API 병합 검색."""
        query = f"{problem.cause} {problem.resolution_direction} {' '.join(problem.keywords)}"

        rag_results: list[dict] = []
        try:
            hits = self.retriever.search(query, top_k=top_k, collection_name="legal_documents")
            rag_results = [
                {
                    "doc_id": r["doc_id"],
                    "title": r["title"],
                    "snippet": r["content_snippet"],
                    "relevance": round(max(0.0, 1.0 - r["similarity"]), 3),
                    "source": "내부DB",
                }
                for r in hits
            ]
        except Exception as e:
            print(f"LLM2 RAG 검색 오류: {e}")

        api_results = search_laws(query, top_k=3)

        seen_titles: set[str] = {r["title"] for r in api_results}
        merged = api_results[:]
        for r in rag_results:
            if r["title"] not in seen_titles:
                merged.append(r)
                seen_titles.add(r["title"])

        # RAG·API 모두 빈 경우 → LLM에게 직접 법령 제안 요청
        if not merged:
            dept = getattr(problem, "responsible_dept", "행정안전부") if hasattr(problem, "responsible_dept") else "행정안전부"
            merged = self._llm_suggest_laws(problem.cause, "민원", dept)

        return merged[:top_k]

    def search_similar_cases(self, problem: StructuredProblem, top_k: int = 3) -> list[dict]:
        """유사 민원/판례 사례 검색."""
        query = f"{problem.affected_subjects} {problem.resolution_direction}"

        rag_results: list[dict] = []
        try:
            hits = self.retriever.search(query, top_k=top_k, collection_name="legal_documents")
            rag_results = [
                {
                    "case_id": r["doc_id"],
                    "title": r["title"],
                    "description": r["content_snippet"],
                    "similarity": round(max(0.0, 1.0 - r["similarity"]), 3),
                    "source": "내부DB",
                }
                for r in hits
            ]
        except Exception as e:
            print(f"LLM2 유사사례 검색 오류: {e}")

        prec_results = [
            {
                "case_id": p["doc_id"],
                "title": p["title"],
                "description": p["snippet"],
                "similarity": p["relevance"],
                "source": p["source"],
            }
            for p in search_precedents(query, top_k=2)
        ]

        seen = {r["title"] for r in prec_results}
        merged = prec_results[:]
        for r in rag_results:
            if r["title"] not in seen:
                merged.append(r)
                seen.add(r["title"])

        return merged[:top_k]


# ── 부처별 기본 법령 (LLM도 실패할 경우 최후 fallback) ───────────────────────

_DEPT_LAWS: dict[str, list[str]] = {
    "국토교통부": ["국토의 계획 및 이용에 관한 법률", "주택법", "도로법", "건설기술진흥법", "건축법"],
    "환경부": ["환경정책기본법", "대기환경보전법", "물환경보전법", "폐기물관리법", "소음·진동관리법"],
    "보건복지부": ["국민건강보험법", "사회복지사업법", "노인복지법", "장애인복지법", "아동복지법"],
    "교육부": ["교육기본법", "초·중등교육법", "고등교육법", "학교폭력예방 및 대책에 관한 법률", "사립학교법"],
    "행정안전부": ["지방자치법", "행정절차법", "전자정부법", "민원처리에 관한 법률", "개인정보보호법"],
    "경찰청": ["경찰관직무집행법", "도로교통법", "형사소송법", "특정범죄 가중처벌 등에 관한 법률"],
    "고용노동부": ["근로기준법", "최저임금법", "산업안전보건법", "고용보험법", "직업안정법"],
    "기획재정부": ["국가재정법", "조세특례제한법", "부가가치세법", "소득세법", "법인세법"],
}

_DEFAULT_LAWS = ["행정절차법", "민원처리에 관한 법률", "지방자치법", "공공기관의 운영에 관한 법률", "국가재정법"]


def _dept_default_laws(responsible_dept: str, classification: str) -> list[str]:
    for dept, laws in _DEPT_LAWS.items():
        if dept in responsible_dept:
            return laws
    return _DEFAULT_LAWS
