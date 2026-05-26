"""웹 검색 에이전트 — Tavily Search API.

패키지 설치 불필요. httpx로 REST 직접 호출 (Vercel 호환).
TAVILY_API_KEY 미설정 시 빈 리스트 반환 (graceful fallback).
"""
from __future__ import annotations

import asyncio

import httpx

from app.config import settings

_TAVILY_URL = "https://api.tavily.com/search"
_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)


async def search(query: str, max_results: int = 5) -> list[dict]:
    """Tavily 검색. [{title, url, content, score}] 반환.

    API 키 미설정이거나 오류 시 빈 리스트 반환.
    """
    api_key = (getattr(settings, "tavily_api_key", None) or "").strip()
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _TAVILY_URL,
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                    "include_answer": True,
                },
            )
            resp.raise_for_status()
        data = resp.json()

        results: list[dict] = []
        # 요약 답변이 있으면 첫 항목으로 추가
        if data.get("answer"):
            results.append({
                "title": "검색 요약",
                "url": "",
                "content": str(data["answer"])[:600],
                "score": 1.0,
            })
        # 개별 결과
        for r in (data.get("results") or [])[:max_results]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": str(r.get("content", ""))[:500],
                "score": r.get("score", 0),
            })
        return results
    except Exception as e:
        print(f"[WebSearch] 오류 (무시됨): {type(e).__name__}: {e}")
        return []


async def search_for_proposal(topic: str, keywords: list[str]) -> list[dict]:
    """제안서용 복합 검색 — 3가지 쿼리를 병렬 실행.

    Args:
        topic: 정규화된 주제 (예: "교통", "환경")
        keywords: 사용자 입력에서 추출한 키워드 리스트

    Returns:
        중복 제거된 검색 결과 최대 10개
    """
    kw = " ".join(keywords[:3])
    queries = [
        f"{topic} {kw} 통계 현황 한국",
        f"{topic} {kw} 법령 개정 사례",
        f"{topic} {kw} 문제점 피해 현황",
    ]
    results_list = await asyncio.gather(*[search(q, max_results=3) for q in queries])

    # 중복 URL 제거 후 합산
    seen: set[str] = set()
    combined: list[dict] = []
    for results in results_list:
        for r in results:
            key = r.get("url") or r.get("content", "")[:80]
            if key not in seen:
                seen.add(key)
                combined.append(r)

    return combined[:10]
