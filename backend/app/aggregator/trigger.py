"""TriggerManager — 클러스터 임계치 도달 시 Agent 2 트리거 판단.

임계치(기본 50)에 도달한 클러스터를 감지하고,
아직 triggered=False인 경우에만 문서 생성을 요청한다.
"""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session as DBSession

from app.storage.models import ProposalCluster


class TriggerManager:
    def should_trigger(self, cluster: ProposalCluster) -> bool:
        """클러스터가 임계치를 넘었고 아직 트리거되지 않았으면 True."""
        return (
            not cluster.triggered
            and cluster.count >= cluster.threshold
            and cluster.classification in ("제안", "청원")
        )

    def mark_triggered(self, db: DBSession, cluster: ProposalCluster) -> None:
        cluster.triggered = True
        db.add(cluster)
        db.commit()

    def get_pending_triggers(self, db: DBSession) -> List[ProposalCluster]:
        """임계치 초과 + 미트리거 클러스터 목록 반환."""
        return (
            db.query(ProposalCluster)
            .filter(
                ProposalCluster.triggered == False,
                ProposalCluster.count >= ProposalCluster.threshold,
            )
            .all()
        )

    def progress_percent(self, cluster: ProposalCluster) -> int:
        """임계치 대비 현재 진행률 (0~100)."""
        if cluster.threshold <= 0:
            return 100
        pct = int(cluster.count / cluster.threshold * 100)
        return min(pct, 100)
