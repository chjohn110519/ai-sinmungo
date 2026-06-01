"""관리자 통계 API + 민원 목록 API."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.config import settings
from app.storage.db import get_db
from app.storage.models import Session as SessionModel, StructuredProposal, AnalysisResult

router = APIRouter()


def require_admin(x_admin_api_key: str | None = Header(default=None)) -> None:
    """ADMIN_API_KEY가 설정된 환경에서만 관리자 API 키를 강제한다."""
    if settings.admin_api_key and x_admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="관리자 인증이 필요합니다.")


@router.get("/admin/stats")
async def get_admin_stats(
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """전체 통계 + 최근 세션 목록."""
    total = db.query(func.count(SessionModel.session_id)).scalar() or 0

    class_counts = (
        db.query(SessionModel.final_classification, func.count(SessionModel.session_id))
        .filter(SessionModel.final_classification.isnot(None))
        .group_by(SessionModel.final_classification)
        .all()
    )
    classification_breakdown = {row[0]: row[1] for row in class_counts}

    status_counts = (
        db.query(SessionModel.status, func.count(SessionModel.session_id))
        .group_by(SessionModel.status)
        .all()
    )
    status_breakdown = {row[0]: row[1] for row in status_counts}

    avg_score = db.query(func.avg(AnalysisResult.feasibility_score)).scalar()
    avg_pass = db.query(func.avg(AnalysisResult.pass_probability)).scalar()

    recent_sessions = (
        db.query(SessionModel)
        .order_by(desc(SessionModel.created_at))
        .limit(20)
        .all()
    )

    recent_list = []
    for s in recent_sessions:
        proposal = db.query(StructuredProposal).filter(
            StructuredProposal.session_id == s.session_id
        ).first()
        cls = s.final_classification or (s.conversation_context or {}).get("classification")
        recent_list.append({
            "session_id": s.session_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "status": s.status,
            "classification": cls,
            "proposal_title": proposal.title if proposal else None,
        })

    return {
        "total_sessions": total,
        "classification_breakdown": {
            "민원": classification_breakdown.get("민원", 0),
            "제안": classification_breakdown.get("제안", 0),
            "청원": classification_breakdown.get("청원", 0),
        },
        "status_breakdown": status_breakdown,
        "avg_feasibility_score": round(avg_score or 0, 3),
        "avg_pass_probability": round(avg_pass or 0, 3),
        "recent_sessions": recent_list,
    }


@router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    classification: str = Query(None),
    db: Session = Depends(get_db),
):
    """민원 목록 조회 (페이지네이션 + 필터).
    classification은 final_classification → conversation_context['classification'] 순 폴백.
    """
    query = db.query(SessionModel).order_by(desc(SessionModel.created_at))
    if status:
        query = query.filter(SessionModel.status == status)
    # classification 필터는 final_classification이 null인 경우를 놓치므로
    # DB 레벨 필터 대신 Python 포스트 필터로 처리
    all_sessions = query.all()

    items = []
    for s in all_sessions:
        # final_classification 없으면 conversation_context에서 폴백
        cls = s.final_classification or (s.conversation_context or {}).get("classification")
        # 분류 필터 적용 (포스트 필터)
        if classification and cls != classification:
            continue
        proposal = db.query(StructuredProposal).filter(
            StructuredProposal.session_id == s.session_id
        ).first()
        items.append({
            "session_id": s.session_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "status": s.status,
            "classification": cls,
            "proposal_title": proposal.title if proposal else None,
        })

    total = len(items)
    paginated = items[(page - 1) * page_size : page * page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "items": paginated,
    }


@router.get("/session/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    _: None = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """세션의 채팅 메시지 목록 조회 (히스토리 복원용)."""
    from app.storage.models import Message as MessageModel
    from fastapi import HTTPException

    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    messages = (
        db.query(MessageModel)
        .filter(MessageModel.session_id == session_id)
        .order_by(MessageModel.created_at)
        .all()
    )
    cls = session.final_classification or (session.conversation_context or {}).get("classification")
    return {
        "session_id": session_id,
        "status": session.status,
        "classification": cls,
        "messages": [
            {
                "message_id": m.message_id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }
