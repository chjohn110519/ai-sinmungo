"""국가법령정보센터 Open API 연동 모듈.

API 키는 https://open.law.go.kr 에서 발급받아 .env에 LAW_API_KEY로 설정하세요.
키 없이도 동작하지만, 실시간 검색 대신 샘플 데이터만 사용됩니다.
"""

from __future__ import annotations

import httpx
from typing import Optional

from app.config import settings


LAW_SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
LAW_DETAIL_URL = "https://www.law.go.kr/DRF/lawService.do"


def _api_key() -> Optional[str]:
    return getattr(settings, "law_api_key", None) or None


def search_laws(query: str, top_k: int = 5) -> list[dict]:
    """키워드로 법령 검색. API 키 없으면 빈 리스트 반환."""
    key = _api_key()
    if not key:
        return []

    try:
        resp = httpx.get(
            LAW_SEARCH_URL,
            params={
                "OC": key,
                "target": "law",
                "type": "JSON",
                "query": query,
                "display": top_k,
                "sort": "lasc",
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        data = resp.json()

        laws = data.get("LawSearch", {}).get("law", [])
        if isinstance(laws, dict):
            laws = [laws]

        results = []
        for law in laws[:top_k]:
            results.append({
                "doc_id": f"law_api_{law.get('법령ID', '')}",
                "title": law.get("법령명한글", ""),
                "snippet": f"소관부처: {law.get('소관부처명', '')} | 공포일: {law.get('공포일자', '')}",
                "relevance": 0.85,
                "source": "국가법령정보센터",
                "url": f"https://www.law.go.kr/법령/{law.get('법령명한글', '')}",
            })
        return results

    except Exception as e:
        print(f"[법령API] 검색 오류: {e}")
        return []


def get_law_detail(law_id: str) -> Optional[dict]:
    """법령 ID로 상세 내용 조회."""
    key = _api_key()
    if not key:
        return None

    try:
        resp = httpx.get(
            LAW_DETAIL_URL,
            params={"OC": key, "target": "law", "ID": law_id, "type": "JSON"},
            timeout=8.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[법령API] 상세 조회 오류: {e}")
        return None


def search_precedents(query: str, top_k: int = 3) -> list[dict]:
    """판례 검색 (참고용)."""
    key = _api_key()
    if not key:
        return []

    try:
        resp = httpx.get(
            LAW_SEARCH_URL,
            params={
                "OC": key,
                "target": "prec",
                "type": "JSON",
                "query": query,
                "display": top_k,
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        data = resp.json()
        precs = data.get("PrecSearch", {}).get("prec", [])
        if isinstance(precs, dict):
            precs = [precs]

        return [
            {
                "doc_id": f"prec_{p.get('판례정보일련번호', '')}",
                "title": p.get("사건명", ""),
                "snippet": p.get("선고일자", ""),
                "relevance": 0.75,
                "source": "법원판례",
            }
            for p in precs[:top_k]
        ]
    except Exception as e:
        print(f"[법령API] 판례 검색 오류: {e}")
        return []
