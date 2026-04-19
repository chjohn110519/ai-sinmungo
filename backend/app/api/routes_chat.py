import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.storage.db import get_db
from app.storage.models import (
    Message as MessageModel,
    Session as SessionModel,
    StructuredProposal as StructuredProposalModel,
    AnalysisResult as AnalysisResultModel,
    Attachment as AttachmentModel,
)
from app.schemas.routing import RoutingRequest, RoutingResponse, RoutingResult
from typing import List, Optional
from app.schemas.analysis import ComprehensiveAnalysisResponse
from app.schemas.proposal import VisualAnalysis
from app.graph.pipeline import run_pipeline, stream_pipeline, PipelineState
from app.rag.indexer import RAGIndexer

router = APIRouter()

# RAG 초기화 (서버 시작 시 1회)
try:
    rag_indexer = RAGIndexer(persist_dir="./chroma_db")
    rag_indexer.initialize_with_sample_data()
except Exception as e:
    print(f"RAG 초기화 오류: {e}")


# ─── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _ensure_session(db: Session, session_id: str) -> SessionModel:
    session = db.get(SessionModel, session_id)
    if session is None:
        session = SessionModel(session_id=session_id, user_input_mode="text", status="in_progress")
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def _save_user_message(db: Session, session_id: str, content: str) -> None:
    db.add(MessageModel(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=content,
    ))
    db.commit()


def _save_pipeline_results(db: Session, session_id: str, state: PipelineState) -> None:
    """LangGraph 최종 상태를 DB에 영속화."""
    proposal_id = str(uuid.uuid4())
    pp = state.get("policy_proposal") or {}
    va = state.get("visual_analysis") or {}
    routing = state.get("routing_result") or {}
    review = state.get("proposal_review") or {}

    db_proposal = StructuredProposalModel(
        proposal_id=proposal_id,
        session_id=session_id,
        title=pp.get("title", ""),
        background=pp.get("background", ""),
        core_requests=pp.get("core_requests", ""),
        expected_effects=pp.get("expected_effects", ""),
        responsible_dept=pp.get("responsible_dept", ""),
        related_laws=pp.get("related_laws", []),
    )
    db.add(db_proposal)
    db.flush()

    db.add(AnalysisResultModel(
        analysis_id=str(uuid.uuid4()),
        proposal_id=proposal_id,
        similar_cases=va.get("similar_cases", []),
        pass_probability=va.get("pass_probability", 0.0),
        expected_duration_days=va.get("expected_duration_days", 0),
        feasibility_score=va.get("feasibility_score", 0.0),
        visualization_data=va.get("chart_data", {}),
    ))

    db.add(MessageModel(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role="assistant",
        content=json.dumps({
            "classification": routing.get("classification"),
            "confidence": routing.get("confidence"),
            "validity_score": review.get("validity_score"),
        }, ensure_ascii=False),
        agent_name="comprehensive_pipeline",
    ))
    db.commit()


def _state_to_response(state: PipelineState) -> ComprehensiveAnalysisResponse:
    routing = state.get("routing_result") or {}
    sp = state.get("structured_problem")
    pp = state.get("policy_proposal")
    pr = state.get("proposal_review")
    va = state.get("visual_analysis")

    from app.schemas.routing import RoutingResult
    from app.schemas.proposal import StructuredProblem, PolicyProposal, ProposalReview

    return ComprehensiveAnalysisResponse(
        session_id=state["session_id"],
        routing_result=RoutingResult(**routing) if routing else RoutingResult(
            classification="민원", confidence=0.5,
            responsible_dept="행정안전부", reasoning="오류"
        ),
        structured_problem=StructuredProblem(**sp) if sp else None,
        related_laws=state.get("related_laws"),
        similar_cases=state.get("similar_cases"),
        policy_proposal=PolicyProposal(**pp) if pp else None,
        proposal_review=ProposalReview(**pr) if pr else None,
        visual_analysis=VisualAnalysis(**va) if va else None,
        processing_steps=state.get("processing_steps", []),
        errors=state.get("errors", []),
        success=len(state.get("errors", [])) == 0,
    )


# ─── 엔드포인트 ───────────────────────────────────────────────────────────────

def _merge_attachment_text(db: Session, session_id: str, message: str, attachment_ids: list[str]) -> str:
    """첨부파일에서 추출한 텍스트를 메시지에 합산."""
    if not attachment_ids:
        return message
    parts = [message]
    for att_id in attachment_ids:
        att = db.get(AttachmentModel, att_id)
        if att and att.extracted_text:
            parts.append(f"\n[첨부파일: {att.filename}]\n{att.extracted_text[:2000]}")
    return "\n".join(parts)


@router.post("/chat", response_model=ComprehensiveAnalysisResponse)
async def comprehensive_chat_endpoint(request: RoutingRequest, db: Session = Depends(get_db)):
    """LangGraph 파이프라인 동기 실행."""
    session_id = request.session_id or str(uuid.uuid4())

    session = _ensure_session(db, session_id)
    _save_user_message(db, session_id, request.message)
    attachment_ids = getattr(request, "attachment_ids", []) or []
    full_message = _merge_attachment_text(db, session_id, request.message, attachment_ids)

    try:
        final_state: PipelineState = run_pipeline(full_message, session_id)

        routing = final_state.get("routing_result") or {}
        session.final_classification = routing.get("classification")
        session.status = "completed"
        db.add(session)
        db.commit()

        _save_pipeline_results(db, session_id, final_state)
        return _state_to_response(final_state)

    except Exception as e:
        db.rollback()
        session.status = "failed"
        db.add(session)
        db.commit()
        print(f"파이프라인 오류: {e}")
        return ComprehensiveAnalysisResponse(
            session_id=session_id,
            routing_result=RoutingResult(
                classification="민원", confidence=0.5,
                responsible_dept="행정안전부", reasoning=str(e),
            ),
            processing_steps=[],
            errors=[str(e)],
            success=False,
        )


# SSE 노드 이름 → 한국어 라벨 매핑
_NODE_LABELS: dict[str, str] = {
    "route":     "민원 분류",
    "structure": "문제 구조화",
    "search":    "법령 검색",
    "generate":  "제안서 생성",
    "review":    "타당성 검토",
    "inc_rev":   "재검토 준비",
    "visualize": "시각화 분석",
}

_NODE_STAGE: dict[str, int] = {
    "route": 1, "structure": 2, "search": 3,
    "generate": 4, "review": 5, "inc_rev": 5, "visualize": 6,
}


@router.get("/chat/stream")
async def stream_chat_endpoint(
    message: str,
    session_id: str = None,
    db: Session = Depends(get_db),
):
    """LangGraph 파이프라인 SSE 스트리밍 — 각 노드 완료 시 이벤트 전송."""
    session_id = session_id or str(uuid.uuid4())

    async def generate():
        _ensure_session(db, session_id)
        _save_user_message(db, session_id, message)

        final_state: PipelineState = None

        try:
            for step in stream_pipeline(message, session_id):
                for node_name, update in step.items():
                    if node_name == "__end__":
                        continue
                    label = _NODE_LABELS.get(node_name, node_name)
                    stage = _NODE_STAGE.get(node_name, 0)

                    # 노드별 요약 데이터 추출
                    data: dict = {}
                    if "routing_result" in update and update["routing_result"]:
                        r = update["routing_result"]
                        data = {"classification": r.get("classification"), "confidence": r.get("confidence")}
                    elif "structured_problem" in update and update["structured_problem"]:
                        sp = update["structured_problem"]
                        data = {"cause": sp.get("cause", "")[:80]}
                    elif "related_laws" in update:
                        data = {"law_count": len(update.get("related_laws") or [])}
                    elif "policy_proposal" in update and update["policy_proposal"]:
                        data = {"title": update["policy_proposal"].get("title", "")}
                    elif "proposal_review" in update and update["proposal_review"]:
                        pr = update["proposal_review"]
                        data = {"validity_score": pr.get("validity_score"), "needs_revision": pr.get("needs_revision")}
                    elif "visual_analysis" in update and update["visual_analysis"]:
                        va = update["visual_analysis"]
                        data = {"feasibility_score": va.get("feasibility_score"), "pass_probability": va.get("pass_probability")}

                    payload = json.dumps({
                        "stage": stage, "node": node_name,
                        "label": label, "status": "done", "data": data,
                    }, ensure_ascii=False)
                    yield f"data: {payload}\n\n"

                    # 최신 상태 누적
                    if final_state is None:
                        final_state = {**update, "message": message, "session_id": session_id,
                                       "revision_count": 0, "errors": [], "processing_steps": [],
                                       "current_node": ""}
                    else:
                        final_state.update(update)

            # 완료 — DB 저장 후 전체 결과 전송
            if final_state:
                session = db.get(SessionModel, session_id)
                if session:
                    routing = final_state.get("routing_result") or {}
                    session.final_classification = routing.get("classification")
                    session.status = "completed"
                    db.add(session)
                    db.commit()
                _save_pipeline_results(db, session_id, final_state)

                result_resp = _state_to_response(final_state)
                complete_payload = json.dumps({
                    "stage": "complete",
                    "session_id": session_id,
                    "result": result_resp.model_dump(),
                }, ensure_ascii=False)
                yield f"data: {complete_payload}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'stage': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/simple", response_model=RoutingResponse)
async def simple_chat_endpoint(request: RoutingRequest, db: Session = Depends(get_db)):
    """분류만 수행하는 경량 엔드포인트."""
    from app.agents.router import AIRouter
    session_id = request.session_id or str(uuid.uuid4())
    _ensure_session(db, session_id)
    _save_user_message(db, session_id, request.message)

    try:
        ai_router = AIRouter()
        result = ai_router.route_message(request.message)
        session = db.get(SessionModel, session_id)
        session.final_classification = result.classification
        session.status = "classified"
        db.add(session)
        db.add(MessageModel(
            message_id=str(uuid.uuid4()), session_id=session_id,
            role="assistant",
            content=f"분류: {result.classification} (신뢰도: {result.confidence:.1%})",
            agent_name="router",
        ))
        db.commit()
        return RoutingResponse(result=result, session_id=session_id)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션 없음")
    messages = (
        db.query(MessageModel)
        .filter(MessageModel.session_id == session_id)
        .order_by(MessageModel.created_at).all()
    )
    return {
        "session": {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "user_input_mode": session.user_input_mode,
            "final_classification": session.final_classification,
            "status": session.status,
        },
        "messages": [
            {"message_id": m.message_id, "role": m.role, "content": m.content,
             "agent_name": m.agent_name, "created_at": m.created_at}
            for m in messages
        ],
    }


@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str, db: Session = Depends(get_db)):
    """민원 처리 현황 조회 (처리 단계 + 결과 요약)."""
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션 없음")

    proposal = db.query(StructuredProposalModel).filter(
        StructuredProposalModel.session_id == session_id
    ).first()

    STATUS_STEPS = {
        "in_progress":  {"step": 1, "label": "접수 완료"},
        "classified":   {"step": 2, "label": "분류 완료"},
        "structured":   {"step": 3, "label": "구조화 완료"},
        "completed":    {"step": 6, "label": "처리 완료"},
        "failed":       {"step": 0, "label": "처리 실패"},
    }
    step_info = STATUS_STEPS.get(session.status, {"step": 1, "label": "처리 중"})

    return {
        "session_id": session_id,
        "status": session.status,
        "current_step": step_info["step"],
        "current_label": step_info["label"],
        "classification": session.final_classification,
        "created_at": session.created_at,
        "proposal_title": proposal.title if proposal else None,
        "has_result": proposal is not None,
        "steps": [
            {"step": 1, "label": "접수", "done": True},
            {"step": 2, "label": "분류", "done": step_info["step"] >= 2},
            {"step": 3, "label": "구조화", "done": step_info["step"] >= 3},
            {"step": 4, "label": "제안서 생성", "done": step_info["step"] >= 4},
            {"step": 5, "label": "타당성 검토", "done": step_info["step"] >= 5},
            {"step": 6, "label": "처리 완료", "done": step_info["step"] >= 6},
        ],
    }
