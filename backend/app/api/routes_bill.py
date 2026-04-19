"""법안 생성 API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.storage.db import get_db
from app.storage.models import StructuredProposal
from app.agents.llm_bill_generator import LLMBillGenerator, FormalBill
from app.schemas.proposal import PolicyProposal

router = APIRouter()
_bill_generator = LLMBillGenerator()


@router.post("/session/{session_id}/bill", response_model=FormalBill)
async def generate_bill(session_id: str, db: Session = Depends(get_db)):
    """저장된 제안서를 정식 법안 형식으로 변환."""
    proposal_db = db.query(StructuredProposal).filter(
        StructuredProposal.session_id == session_id
    ).first()

    if not proposal_db:
        raise HTTPException(status_code=404, detail="해당 세션의 제안서가 없습니다. 먼저 민원을 처리해 주세요.")

    proposal = PolicyProposal(
        title=proposal_db.title or "",
        background=proposal_db.background or "",
        core_requests=proposal_db.core_requests or "",
        expected_effects=proposal_db.expected_effects or "",
        responsible_dept=proposal_db.responsible_dept or "",
        related_laws=proposal_db.related_laws or [],
    )

    from app.storage.models import Session as SessionModel
    session = db.get(SessionModel, session_id)
    classification = session.final_classification if session else "제안"

    return _bill_generator.generate_bill(proposal, classification)
