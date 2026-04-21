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
    "환경": ["환경", "쓰레기", "미세먼지", "공기", "소음", "하천"],
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


def _keyword_overlap(kws_a: list[str], kws_b: list[str]) -> float:
    """두 키워드 목록의 Jaccard 유사도."""
    if not kws_a or not kws_b:
        return 0.0
    set_a = {k.strip() for k in kws_a}
    set_b = {k.strip() for k in kws_b}
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


class ClusterManager:
    KEYWORD_THRESHOLD = 0.2  # 이 이상이면 동일 클러스터로 판단

    def find_matching_cluster(
        self,
        db: DBSession,
        topic: str,
        keywords: List[str],
        classification: str,
        responsible_dept: str,
    ) -> Optional[ProposalCluster]:
        """topic과 keywords가 유사한 기존 클러스터를 반환. 없으면 None."""
        normalized = _normalize_topic(topic)

        candidates = (
            db.query(ProposalCluster)
            .filter(
                ProposalCluster.classification == classification,
                ProposalCluster.topic == normalized,
            )
            .all()
        )

        best: Optional[ProposalCluster] = None
        best_score = 0.0
        for c in candidates:
            score = _keyword_overlap(keywords, c.keywords or [])
            if score > best_score:
                best_score = score
                best = c

        if best_score >= self.KEYWORD_THRESHOLD:
            return best
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
