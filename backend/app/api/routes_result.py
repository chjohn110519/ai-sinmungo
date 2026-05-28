from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.storage.db import get_db
from app.storage.models import Session as SessionModel, StructuredProposal, AnalysisResult

router = APIRouter()


@router.get("/session/{session_id}/result")
async def get_session_result(session_id: str, db: Session = Depends(get_db)):
    """세션의 최종 결과 조회"""
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    proposal = db.query(StructuredProposal).filter(StructuredProposal.session_id == session_id).first()
    analysis = None
    if proposal:
        analysis = db.query(AnalysisResult).filter(AnalysisResult.proposal_id == proposal.proposal_id).first()

    # visualization_data 정규화:
    # 과거 저장분은 'committee_breakdown' 키를 사용했으므로
    # 프론트가 읽는 'committee_recommendations' (visualization_data 내부) 로 변환
    vis_data: dict = {}
    if analysis:
        vis_data = dict(analysis.visualization_data or {})
        if "committee_breakdown" in vis_data and "committee_recommendations" not in vis_data:
            raw = vis_data.pop("committee_breakdown") or []
            vis_data["committee_recommendations"] = [
                {
                    "committee": r.get("committee", ""),
                    "relevance": r.get("confidence", r.get("relevance", 0)),
                }
                if isinstance(r, dict) else {"committee": str(r), "relevance": 0}
                for r in raw
            ]

    return {
        "session": {
            "session_id": session.session_id,
            "status": session.status,
            "final_classification": session.final_classification,
        },
        "proposal": {
            "title": proposal.title,
            "background": proposal.background,
            "core_requests": proposal.core_requests,
            "expected_effects": proposal.expected_effects,
            "responsible_dept": proposal.responsible_dept,
            "related_laws": proposal.related_laws,
        } if proposal else None,
        "analysis": {
            "analysis_id": analysis.analysis_id,
            "similar_cases": analysis.similar_cases,
            "pass_probability": analysis.pass_probability,
            "expected_duration_days": analysis.expected_duration_days,
            "feasibility_score": analysis.feasibility_score,
            "visualization_data": vis_data,  # committee_recommendations 포함
        } if analysis else None,
    }