"""클러스터 집계 현황 API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from typing import Optional

from app.storage.db import get_db
from app.storage.models import ProposalCluster, StructuredProposal as StructuredProposalModel, AnalysisResult as AnalysisResultModel
from app.aggregator.cluster import ClusterManager
from app.aggregator.trigger import TriggerManager

router = APIRouter()
_cluster_mgr = ClusterManager()
_trigger_mgr = TriggerManager()


def _cluster_to_dict(c) -> dict:
    return {
        "cluster_id": c.cluster_id,
        "topic": c.topic,
        "keywords": c.keywords or [],
        "responsible_dept": c.responsible_dept,
        "classification": c.classification,
        "count": c.count,
        "threshold": c.threshold,
        "triggered": c.triggered,
        "proposal_id": c.proposal_id,
        "progress_percent": _trigger_mgr.progress_percent(c),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _topic_trends(db: DBSession, limit: int) -> list[dict]:
    """클러스터 count를 주제별로 합산한다.

    기존 키워드 집계는 하나의 클러스터 count가 여러 키워드에 중복 반영되어
    집계 현황의 참여 수와 메인 화면 수치가 다르게 보였다. 주제별 집계는
    클러스터 count를 한 번만 더하므로 시민 제안 집계 현황과 의미가 일치한다.
    """
    clusters = db.query(ProposalCluster).all()
    topic_weights: dict[str, int] = {}
    topic_best: dict[str, dict] = {}

    for c in clusters:
        topic = (c.topic or "기타").strip() or "기타"
        topic_weights[topic] = topic_weights.get(topic, 0) + c.count
        prev = topic_best.get(topic)
        if prev is None or c.count > prev["count"]:
            topic_best[topic] = {
                "cluster_id": c.cluster_id,
                "topic": topic,
                "count": c.count,
            }

    trending = sorted(topic_weights.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [
        {
            # 기존 프론트 호환용: keyword 필드에는 주제명을 넣는다.
            "keyword": topic,
            "topic": topic,
            "total_count": cnt,
            "cluster_id": topic_best.get(topic, {}).get("cluster_id"),
        }
        for topic, cnt in trending
    ]


@router.get("/cluster/{cluster_id}")
async def get_cluster(cluster_id: str, db: DBSession = Depends(get_db)):
    """특정 클러스터의 집계 현황 조회."""
    cluster = _cluster_mgr.get_cluster(db, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다.")
    return _cluster_to_dict(cluster)


@router.get("/clusters")
async def list_clusters(
    classification: Optional[str] = Query(None, description="제안 또는 청원"),
    dept: Optional[str] = Query(None, description="관할 부처 키워드"),
    limit: int = Query(20, ge=1, le=100),
    db: DBSession = Depends(get_db),
):
    """집계 클러스터 목록 조회 (카운트 내림차순)."""
    clusters = _cluster_mgr.list_clusters(db, classification=classification, dept=dept, limit=limit)
    return {
        "total": len(clusters),
        "clusters": [_cluster_to_dict(c) for c in clusters],
    }


@router.get("/clusters/trending-keywords")
async def get_trending_keywords(
    limit: int = Query(10, ge=1, le=30),
    db: DBSession = Depends(get_db),
):
    """인기 주제 TOP N.

    경로명은 하위 호환을 위해 유지하지만, 실제 집계 기준은 키워드가 아니라 주제다.
    """
    trending = _topic_trends(db, limit)
    return {
        "trending_keywords": trending,
        "trending_topics": trending,
    }


@router.get("/clusters/trending-topics")
async def get_trending_topics(
    limit: int = Query(10, ge=1, le=30),
    db: DBSession = Depends(get_db),
):
    """클러스터 count를 주제별로 합산한 인기 주제 TOP N."""
    trending = _topic_trends(db, limit)
    return {
        "trending_topics": trending,
        "trending_keywords": trending,
    }


@router.get("/cluster/{cluster_id}/opinions")
async def get_cluster_opinions(cluster_id: str, db: DBSession = Depends(get_db)):
    """클러스터에 속한 의견 목록 조회 (최신순, 최대 50건)."""
    from app.storage.models import Session as SessionModel, StructuredProposal

    sessions = (
        db.query(SessionModel)
        .filter(SessionModel.cluster_id == cluster_id)
        .order_by(SessionModel.created_at.desc())
        .limit(50)
        .all()
    )
    opinions = []
    for s in sessions:
        ctx = s.conversation_context or {}
        proposal = (
            db.query(StructuredProposal)
            .filter(StructuredProposal.session_id == s.session_id)
            .first()
        )
        opinions.append({
            "session_id": s.session_id[:8],
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "message": (ctx.get("initial_message") or "")[:300],
            "classification": s.final_classification,
            "proposal_title": proposal.title if proposal else None,
        })
    return {"cluster_id": cluster_id, "total": len(opinions), "opinions": opinions}


@router.get("/clusters/pending-triggers")
async def get_pending_triggers(db: DBSession = Depends(get_db)):
    """임계치 초과했지만 아직 문서가 생성되지 않은 클러스터 목록."""
    clusters = _trigger_mgr.get_pending_triggers(db)
    return {
        "total": len(clusters),
        "clusters": [_cluster_to_dict(c) for c in clusters],
    }


@router.get("/proposal/{proposal_id}")
async def get_proposal(proposal_id: str, db: DBSession = Depends(get_db)):
    """공식 제안서 상세 조회 (클러스터 또는 개별 세션 제안서)."""
    proposal = db.get(StructuredProposalModel, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="제안서를 찾을 수 없습니다.")

    analysis = (
        db.query(AnalysisResultModel)
        .filter(AnalysisResultModel.proposal_id == proposal_id)
        .first()
    )

    return {
        "proposal_id": proposal.proposal_id,
        "title": proposal.title,
        "background": proposal.background,
        "core_requests": proposal.core_requests,
        "expected_effects": proposal.expected_effects,
        "responsible_dept": proposal.responsible_dept,
        "related_laws": proposal.related_laws or [],
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
        # APMP 신규 필드
        "executive_summary": proposal.executive_summary,
        "win_theme": proposal.win_theme,
        "proof_points": proposal.proof_points or [],
        "analysis": {
            "pass_probability": analysis.pass_probability if analysis else None,
            "expected_duration_days": analysis.expected_duration_days if analysis else None,
            "feasibility_score": analysis.feasibility_score if analysis else None,
            "visualization_data": analysis.visualization_data if analysis else None,
        } if analysis else None,
    }
