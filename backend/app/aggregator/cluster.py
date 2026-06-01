"""ClusterManager — Agent 1의 집계 핵심 로직.

동일 방향의 제안/청원 입력을 topic + keywords 유사도로 클러스터에 매핑하고,
카운트를 증가시킨다. 매칭되는 클러스터가 없으면 신규 생성.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session as DBSession

from app.storage.models import ProposalCluster


_TOPIC_ALIASES: dict[str, list[str]] = {
    "교통": ["도로", "버스", "지하철", "주차", "신호", "교통"],
    "환경": ["환경", "쓰레기", "미세먼지", "공기", "소음", "하천",
             "탄소", "배출", "대기", "공기질", "기후", "온실가스", "오염", "재활용"],
    "주거": ["주택", "아파트", "임대", "전세", "주거", "건물"],
    "복지": ["복지", "장애", "노인", "아동", "청소년", "사회서비스"],
    "교육": ["교육", "학교", "학원", "교사", "급식", "입시"],
    "의료": ["의료", "병원", "의사", "약", "건강", "보건"],
    "경제": ["경제", "세금", "금융", "중소기업", "창업", "일자리"],
    "노동": ["노동", "근로", "임금", "고용", "실업", "직장"],
    "안전": ["안전", "범죄", "사고", "재난", "소방", "경찰"],
    "기타": [],
}


def _normalize_topic(topic: str) -> str:
    topic_lower = topic.lower()
    for canonical, aliases in _TOPIC_ALIASES.items():
        if canonical in topic_lower or any(a in topic_lower for a in aliases):
            return canonical
    return "기타"


def _kw_match(a: str, b: str) -> bool:
    """두 키워드의 부분 일치 여부 (포함 관계 인식).

    예: "배출" == "배출가스", "미세먼지" == "미세먼지" 모두 True.
    길이 2자 미만은 정확 일치만 허용 (너무 짧은 단어의 오매칭 방지).
    """
    if a == b:
        return True
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 2 and long.startswith(short)


def _keyword_overlap(kws_a: list[str], kws_b: list[str]) -> float:
    """두 키워드 목록의 유사도 (부분 일치 포함 Jaccard).

    정확 일치 + 포함 관계(prefix) 를 모두 매칭으로 인정한다.
    예) ["배출가스", "환경"] vs ["배출", "환경", "법안"] → "배출가스"≈"배출" 포함 인식.
    """
    if not kws_a or not kws_b:
        return 0.0
    list_a = [k.strip() for k in kws_a]
    list_b = [k.strip() for k in kws_b]

    matched_a: set[int] = set()
    matched_b: set[int] = set()
    for i, a in enumerate(list_a):
        for j, b in enumerate(list_b):
            if _kw_match(a, b):
                matched_a.add(i)
                matched_b.add(j)

    # 유효 교집합 크기: 매칭된 인덱스 수의 평균
    intersection = (len(matched_a) + len(matched_b)) / 2
    union = len(list_a) + len(list_b) - intersection
    return intersection / union if union > 0 else 0.0


class ClusterManager:
    KEYWORD_THRESHOLD = 0.35       # 같은 타입(classification) + 주제 매칭
    DEPT_KEYWORD_THRESHOLD = 0.25  # 위원회명 일치 시 완화된 키워드 임계값
    CROSS_TYPE_THRESHOLD = 0.50    # 타입 불문 주제 교차 매칭 임계값

    def _best_by_keyword(
        self, candidates: list, keywords: List[str]
    ) -> tuple:
        """후보 클러스터 중 키워드 유사도 최고를 반환 → (cluster, score)."""
        best: Optional[ProposalCluster] = None
        best_score = 0.0
        for c in candidates:
            score = _keyword_overlap(keywords, c.keywords or [])
            if score > best_score:
                best_score = score
                best = c
        return best, best_score

    def find_matching_cluster(
        self,
        db: DBSession,
        topic: str,
        keywords: List[str],
        classification: str,
        responsible_dept: str,
    ) -> Optional[ProposalCluster]:
        """topic·keywords·위원회명이 유사한 기존 클러스터를 반환. 없으면 None.

        Phase 1 — 동일 타입 + 동일 주제, keyword overlap ≥ 0.35 (기존 로직)
        Phase 2 — 동일 위원회명, keyword overlap ≥ 0.25 (위원회명 기반 매칭)
        Phase 3 — 동일 주제 (타입 무관), keyword overlap ≥ 0.50 (교차 타입 매칭)
        """
        normalized = _normalize_topic(topic)

        # Phase 1: 같은 타입 + 같은 주제
        phase1 = (
            db.query(ProposalCluster)
            .filter(
                ProposalCluster.classification == classification,
                ProposalCluster.topic == normalized,
            )
            .all()
        )
        best, best_score = self._best_by_keyword(phase1, keywords)
        if best_score >= self.KEYWORD_THRESHOLD:
            return best

        # Phase 2: 위원회명 일치 (타입/주제 불문)
        if responsible_dept:
            phase2 = (
                db.query(ProposalCluster)
                .filter(ProposalCluster.responsible_dept == responsible_dept)
                .all()
            )
            best2, score2 = self._best_by_keyword(phase2, keywords)
            if score2 >= self.DEPT_KEYWORD_THRESHOLD:
                return best2

        # Phase 3: 같은 주제 교차 타입 (제안 ↔ 청원)
        phase3 = (
            db.query(ProposalCluster)
            .filter(ProposalCluster.topic == normalized)
            .all()
        )
        best3, score3 = self._best_by_keyword(phase3, keywords)
        if score3 >= self.CROSS_TYPE_THRESHOLD:
            return best3

        return None

    def get_or_create_cluster(
        self,
        db: DBSession,
        topic: str,
        keywords: List[str],
        classification: str,
        responsible_dept: str,
        threshold: int = 50,
    ) -> ProposalCluster:
        """기존 클러스터에 배정하거나 신규 생성 후 카운트 증가."""
        cluster = self.find_matching_cluster(
            db, topic, keywords, classification, responsible_dept
        )

        if cluster is None:
            cluster = ProposalCluster(
                cluster_id=str(uuid.uuid4()),
                topic=_normalize_topic(topic),
                keywords=keywords,
                responsible_dept=responsible_dept,
                classification=classification,
                count=0,
                threshold=threshold,
                triggered=False,
            )
            db.add(cluster)
            db.flush()
        else:
            # 키워드 병합 (새 키워드 추가)
            existing = set(cluster.keywords or [])
            existing.update(keywords)
            cluster.keywords = list(existing)[:20]
            cluster.updated_at = datetime.utcnow()

        cluster.count += 1
        db.commit()
        db.refresh(cluster)
        return cluster

    def get_cluster(self, db: DBSession, cluster_id: str) -> Optional[ProposalCluster]:
        return db.get(ProposalCluster, cluster_id)

    def list_clusters(
        self,
        db: DBSession,
        classification: Optional[str] = None,
        dept: Optional[str] = None,
        limit: int = 50,
    ) -> List[ProposalCluster]:
        q = db.query(ProposalCluster)
        if classification:
            q = q.filter(ProposalCluster.classification == classification)
        if dept:
            q = q.filter(ProposalCluster.responsible_dept.ilike(f"%{dept}%"))
        return q.order_by(ProposalCluster.count.desc()).limit(limit).all()
