from __future__ import annotations
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from app.config import settings


def _get_ef():
    return OpenAIEmbeddingFunction(
        api_key=settings.openai_api_key or "dummy",
        model_name="text-embedding-3-small",
    )


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
