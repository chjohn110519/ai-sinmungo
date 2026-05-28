from __future__ import annotations
import logging
import chromadb
from app.config import settings

logger = logging.getLogger(__name__)


def _get_ef():
    """임베딩 함수 반환.

    openai_api_key가 설정된 경우: OpenAI text-embedding-3-small (1536 dims).
    미설정 시: chromadb 기본 로컬 임베딩(all-MiniLM-L6-v2, 384 dims)으로 fallback.
    """
    if settings.openai_api_key:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name="text-embedding-3-small",
        )
    logger.warning(
        "OPENAI_API_KEY 미설정 — 로컬 임베딩(all-MiniLM-L6-v2)으로 fallback. "
        "검색 품질이 저하될 수 있습니다."
    )
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    return DefaultEmbeddingFunction()


class RAGRetriever:
    def __init__(self, persist_dir: str):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self._ef = _get_ef()

    def search(self, query: str, top_k: int = 5, collection_name: str = "legal_documents") -> list[dict]:
        try:
            collection = self.client.get_collection(name=collection_name, embedding_function=self._ef)
        except Exception:
            return []
        results = collection.query(query_texts=[query], n_results=min(top_k, collection.count() or 1))
        hits = []
        for i, doc_id in enumerate(results["ids"][0]):
            hits.append({
                "doc_id": doc_id,
                "title": results["metadatas"][0][i].get("title", ""),
                "content_snippet": (results["documents"][0][i] if results.get("documents") else "")[:220],
                "similarity": results["distances"][0][i] if results.get("distances") else 0.5,
            })
        return hits
