"""클러스터 집계 현황 API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from typing import Optional

from app.storage.db import get_db
from app.storage.models import StructuredProposal as StructuredProposalModel, AnalysisResult as AnalysisResultModel
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
        "analysis": {
            "pass_probability": analysis.pass_probability if analysis else None,
            "expected_duration_days": analysis.expected_duration_days if analysis else None,
            "feasibility_score": analysis.feasibility_score if analysis else None,
            "visualization_data": analysis.visualization_data if analysis else None,
        } if analysis else None,
    }
