"""다단계 대화형 민원 처리 API.

Stage 흐름:
  start   → 분류 + 명확화 질문 생성     (→ stage: questioning)
  answer  → 초안 제안서 + 개선안 제안   (→ stage: improving)
  finalize→ 최종 제안서 + DOCX 생성    (→ stage: complete)
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from typing import List, Optional

from app.storage.db import get_db
from app.storage.models import (
    Session as SessionModel,
    StructuredProposal as StructuredProposalModel,
    AnalysisResult as AnalysisResultModel,
    Message as MessageModel,
)
from app.agents.router import AIRouter
from app.agents.llm_questioner import LLMQuestioner
from app.agents.llm1_structurer import LLM1Structurer
from app.agents.llm2_searcher import LLM2Searcher
from app.agents.llm3_reviewer import LLM3Reviewer
from app.agents.llm4_visualizer import LLM4Visualizer
from app.agents.llm_improver import LLMImprover, Improvement
from app.schemas.proposal import StructuredProblem
from app.utils.doc_generator import generate_docx

router = APIRouter()

# 공유 에이전트 인스턴스
_router_agent = AIRouter()
_questioner = LLMQuestioner()
_structurer = LLM1Structurer()
_searcher = LLM2Searcher(persist_dir="./chroma_db")
_reviewer = LLM3Reviewer()
_visualizer = LLM4Visualizer()
_improver = LLMImprover()


# ── 요청/응답 스키마 ─────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    attachment_ids: Optional[List[str]] = None


class AnswerRequest(BaseModel):
    session_id: str
    answers: dict[str, str]   # question index → answer text


class FinalizeRequest(BaseModel):
    session_id: str
    accepted_improvement_ids: List[int]
    user_note: Optional[str] = None


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def _get_or_create_session(db: DBSession, session_id: str) -> SessionModel:
    s = db.get(SessionModel, session_id)
    if s is None:
        s = SessionModel(
            session_id=session_id,
            user_input_mode="text",
            status="in_progress",
            conversation_stage="init",
            conversation_context={},
        )
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _save_message(db: DBSession, session_id: str, role: str, content: str) -> None:
    db.add(MessageModel(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role=role,
        content=content,
    ))
    db.commit()


def _merge_attachment_text(db: DBSession, session_id: str, message: str, attachment_ids: list[str] | None) -> str:
    if not attachment_ids:
        return message
    from app.storage.models import Attachment as AttachmentModel
    parts = [message]
    for att_id in attachment_ids:
        att = db.get(AttachmentModel, att_id)
        if att and att.extracted_text:
            parts.append(f"\n[첨부: {att.filename}]\n{att.extracted_text[:2000]}")
    return "\n".join(parts)


# ── TURN 1: 분류 + 질문 생성 ────────────────────────────────────────────────

@router.post("/conversation/start")
async def conversation_start(req: StartRequest, db: DBSession = Depends(get_db)):
    """초기 메시지를 분류하고 명확화 질문을 반환합니다."""
    session_id = req.session_id or str(uuid.uuid4())
    session = _get_or_create_session(db, session_id)

    full_message = _merge_attachment_text(db, session_id, req.message, req.attachment_ids)
    _save_message(db, session_id, "user", req.message)

    # 분류
    routing = _router_agent.route_message(full_message)

    # 명확화 질문 생성
    questions = _questioner.generate(full_message, routing.classification, n=4)

    # 컨텍스트 저장
    ctx = {
        "stage": "questioning",
        "initial_message": full_message,
        "classification": routing.classification,
        "responsible_dept": routing.responsible_dept,
        "confidence": routing.confidence,
        "questions": questions,
    }
    session.conversation_stage = "questioning"
    session.conversation_context = ctx
    session.final_classification = routing.classification
    session.status = "classified"
    db.add(session)
    db.commit()

    # AI 응답 저장
    ai_msg = (
        f"[{routing.classification}] 유형으로 분류되었습니다 (신뢰도 {routing.confidence*100:.0f}%).\n"
        f"담당 부처: {routing.responsible_dept}\n\n"
        "제안서를 더 잘 작성하기 위해 몇 가지 여쭤보겠습니다."
    )
    _save_message(db, session_id, "assistant", ai_msg)

    return {
        "session_id": session_id,
        "stage": "questioning",
        "classification": routing.classification,
        "responsible_dept": routing.responsible_dept,
        "confidence": routing.confidence,
        "questions": questions,
    }


# ── TURN 2: 답변 처리 → 초안 + 개선안 ──────────────────────────────────────

@router.post("/conversation/answer")
async def conversation_answer(req: AnswerRequest, db: DBSession = Depends(get_db)):
    """사용자 답변을 처리하고 초안 제안서 + 개선안을 반환합니다."""
    session = db.get(SessionModel, req.session_id)
    if not session or session.conversation_stage != "questioning":
        raise HTTPException(status_code=400, detail="잘못된 세션 상태입니다.")

    ctx = session.conversation_context or {}
    questions: list[str] = ctx.get("questions", [])

    # 답변 텍스트 합산
    answers_text = "\n".join(
        f"Q{int(k)+1}. {questions[int(k)] if int(k) < len(questions) else ''}  \nA. {v}"
        for k, v in sorted(req.answers.items(), key=lambda x: int(x[0]))
    )
    _save_message(db, req.session_id, "user", answers_text)

    combined_message = ctx["initial_message"] + "\n\n[추가 정보]\n" + answers_text
    classification = ctx["classification"]
    responsible_dept = ctx["responsible_dept"]

    # 문제 구조화
    prob: StructuredProblem = _structurer.structure(combined_message, classification, responsible_dept)

    # 법령 검색
    laws = _searcher.search_related_laws(prob, top_k=5)
    cases = _searcher.search_similar_cases(prob, top_k=3)

    # 초안 제안서 생성
    draft_proposal = _structurer.generate_proposal(combined_message, prob, responsible_dept)
    draft_dict = draft_proposal.model_dump()
    # 검색된 법령명을 related_laws에 병합
    law_titles = [l.get("title", "") for l in laws if l.get("title")]
    existing = draft_dict.get("related_laws", [])
    draft_dict["related_laws"] = list(dict.fromkeys(existing + law_titles))[:8]

    # 개선안 제안
    improvements = _improver.suggest(classification, draft_dict, answers_text, n=4)
    improvements_data = [imp.model_dump() for imp in improvements]

    # 컨텍스트 업데이트
    ctx.update({
        "stage": "improving",
        "user_answers": answers_text,
        "combined_message": combined_message,
        "structured_problem": prob.model_dump(),
        "related_laws": laws,
        "similar_cases": cases,
        "draft_proposal": draft_dict,
        "improvements": improvements_data,
    })
    session.conversation_stage = "improving"
    session.conversation_context = ctx
    session.status = "structured"
    db.add(session)
    db.commit()

    ai_msg = f"초안 제안서를 작성했습니다: 『{draft_dict['title']}』\n통과 확률을 높이기 위한 개선안 {len(improvements)}가지를 확인해 주세요."
    _save_message(db, req.session_id, "assistant", ai_msg)

    return {
        "session_id": req.session_id,
        "stage": "improving",
        "classification": classification,
        "draft_proposal": draft_dict,
        "improvements": improvements_data,
        "related_laws": laws[:5],
        "similar_cases": cases,
    }


# ── TURN 3: 개선안 수락 → 최종 제안서 + DOCX ───────────────────────────────

@router.post("/conversation/finalize")
async def conversation_finalize(req: FinalizeRequest, db: DBSession = Depends(get_db)):
    """수락된 개선안을 반영한 최종 제안서를 생성하고 DOCX 파일을 제공합니다."""
    session = db.get(SessionModel, req.session_id)
    if not session or session.conversation_stage != "improving":
        raise HTTPException(status_code=400, detail="잘못된 세션 상태입니다.")

    ctx = session.conversation_context or {}
    classification = ctx["classification"]
    draft_proposal = ctx["draft_proposal"]
    improvements_data = ctx.get("improvements", [])
    user_answers = ctx.get("user_answers", "")

    # 수락된 개선안 객체 복원
    accepted: list[Improvement] = [
        Improvement(**imp)
        for imp in improvements_data
        if imp["id"] in req.accepted_improvement_ids
    ]

    user_note_msg = f"수락한 개선안: {req.accepted_improvement_ids}, 메모: {req.user_note or '없음'}"
    _save_message(db, req.session_id, "user", user_note_msg)

    # 최종 제안서 재작성
    final_proposal = _improver.refine_proposal(
        draft_proposal, accepted, req.user_note or "", user_answers, classification
    )

    # 타당성 검토 + 시각화
    from app.schemas.proposal import PolicyProposal, ProposalReview
    proposal_obj = PolicyProposal(**final_proposal)
    review = _reviewer.review(proposal_obj)
    similar_cases = ctx.get("similar_cases", [])
    visual = _visualizer.visualize(proposal_obj, review, similar_cases, classification)

    # DOCX 생성
    analysis_dict = {
        "feasibility_score": visual.feasibility_score,
        "pass_probability": visual.pass_probability,
        "expected_duration_days": visual.expected_duration_days,
    }
    docx_path = generate_docx(final_proposal, classification, analysis_dict, req.session_id)

    # DB 저장
    proposal_id = str(uuid.uuid4())
    db_proposal = StructuredProposalModel(
        proposal_id=proposal_id,
        session_id=req.session_id,
        title=final_proposal.get("title", ""),
        background=final_proposal.get("background", ""),
        core_requests=final_proposal.get("core_requests", ""),
        expected_effects=final_proposal.get("expected_effects", ""),
        responsible_dept=final_proposal.get("responsible_dept", ""),
        related_laws=final_proposal.get("related_laws", []),
    )
    db.add(db_proposal)
    db.flush()

    db.add(AnalysisResultModel(
        analysis_id=str(uuid.uuid4()),
        proposal_id=proposal_id,
        similar_cases=similar_cases,
        pass_probability=visual.pass_probability,
        expected_duration_days=visual.expected_duration_days,
        feasibility_score=visual.feasibility_score,
        visualization_data=visual.chart_data,
    ))

    ctx.update({
        "stage": "complete",
        "final_proposal": final_proposal,
        "review": review.model_dump(),
        "visual": analysis_dict,
        "docx_filename": docx_path.name,
    })
    session.conversation_stage = "complete"
    session.conversation_context = ctx
    session.status = "completed"
    db.add(session)
    db.commit()

    ai_msg = (
        f"최종 제안서 『{final_proposal.get('title')}』 완성!\n"
        f"실현 가능성 {visual.feasibility_score*100:.0f}% | "
        f"통과 예상 확률 {visual.pass_probability*100:.0f}% | "
        f"예상 처리 기간 {visual.expected_duration_days}일"
    )
    _save_message(db, req.session_id, "assistant", ai_msg)

    return {
        "session_id": req.session_id,
        "stage": "complete",
        "classification": classification,
        "final_proposal": final_proposal,
        "review": review.model_dump(),
        "analysis": analysis_dict,
        "similar_cases": similar_cases,
        "download_url": f"/api/session/{req.session_id}/download/docx",
        "docx_filename": docx_path.name,
    }


# ── 문서 다운로드 ─────────────────────────────────────────────────────────────

@router.get("/session/{session_id}/download/docx")
async def download_docx(session_id: str, db: DBSession = Depends(get_db)):
    """생성된 DOCX 파일 다운로드."""
    session = db.get(SessionModel, session_id)
    if not session or session.conversation_stage != "complete":
        raise HTTPException(status_code=404, detail="완성된 문서가 없습니다.")

    ctx = session.conversation_context or {}
    docx_filename = ctx.get("docx_filename")
    if not docx_filename:
        raise HTTPException(status_code=404, detail="문서 파일을 찾을 수 없습니다.")

    from app.utils.doc_generator import DOCS_DIR
    file_path = DOCS_DIR / docx_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="문서 파일이 서버에 없습니다.")

    return FileResponse(
        path=str(file_path),
        filename=docx_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ── 대화 재개 (페이지 새로고침 시) ──────────────────────────────────────────

@router.get("/conversation/{session_id}/state")
async def get_conversation_state(session_id: str, db: DBSession = Depends(get_db)):
    """현재 대화 단계 상태 조회 (프론트엔드 복원용)."""
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션 없음")

    ctx = session.conversation_context or {}
    return {
        "session_id": session_id,
        "stage": session.conversation_stage or "init",
        "classification": session.final_classification,
        "context": {
            "questions": ctx.get("questions", []),
            "draft_proposal": ctx.get("draft_proposal"),
            "improvements": ctx.get("improvements", []),
            "final_proposal": ctx.get("final_proposal"),
            "analysis": ctx.get("visual"),
            "download_url": f"/api/session/{session_id}/download/docx" if session.conversation_stage == "complete" else None,
        }
    }
