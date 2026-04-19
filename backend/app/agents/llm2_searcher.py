from app.rag.retriever import RAGRetriever
from app.rag.law_api import search_laws, search_precedents
from app.schemas.proposal import StructuredProblem


class LLM2Searcher:
    """관련 법령 및 유사 사례를 검색하는 RAG + 국가법령정보센터 API 에이전트."""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.retriever = RAGRetriever(persist_dir)

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

        # 국가법령정보센터 API 검색 (키가 설정된 경우)
        api_results = search_laws(query, top_k=3)

        # 중복 제거 후 병합 (API 결과 우선)
        seen_titles: set[str] = {r["title"] for r in api_results}
        merged = api_results[:]
        for r in rag_results:
            if r["title"] not in seen_titles:
                merged.append(r)
                seen_titles.add(r["title"])

        if not merged:
            merged = [{"doc_id": "law_001", "title": "도로교통법", "snippet": "도로에서의 교통안전 및 질서 유지", "relevance": 0.85, "source": "내부DB"}]

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

        # 판례 API 검색
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
