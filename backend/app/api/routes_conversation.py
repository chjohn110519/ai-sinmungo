"""다단계 대화형 민원 처리 API — Stateless 버전.

컨텍스트를 DB 대신 요청/응답 페이로드로 주고받아
서버리스(Vercel) 환경에서도 동작합니다.

Stage 흐름:
  start   → 분류 + 명확화 질문 생성     (→ stage: questioning)
  answer  → 초안 제안서 + 개선안 제안   (→ stage: improving)
  finalize→ 최종 제안서 + DOCX 생성    (→ stage: complete)
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from typing import Any, Dict, List, Optional

from app.storage.db import get_db
from app.storage.models import (
    Session as SessionModel,
    StructuredProposal as StructuredProposalModel,
    AnalysisResult as AnalysisResultModel,
    Message as MessageModel,
    ProposalCluster,
)
from app.agents.router import AIRouter
from app.aggregator.cluster import ClusterManager
from app.aggregator.trigger import TriggerManager
from app.agents.llm_questioner import LLMQuestioner
from app.agents.llm1_structurer import LLM1Structurer
from app.agents.llm2_searcher import LLM2Searcher
from app.agents.llm3_reviewer import LLM3Reviewer
from app.agents.llm4_visualizer import LLM4Visualizer
from app.agents.llm_improver import LLMImprover, Improvement
from app.schemas.proposal import StructuredProblem
from app.utils.doc_generator import generate_docx
from app.config import settings

router = APIRouter()

# 공유 에이전트 인스턴스
_router_agent = AIRouter()
_cluster_mgr = ClusterManager()
_trigger_mgr = TriggerManager()
_questioner = LLMQuestioner()
_structurer = LLM1Structurer()
_searcher = LLM2Searcher(persist_dir=settings.chroma_persist_directory)
_reviewer = LLM3Reviewer()
_visualizer = LLM4Visualizer()
_improver = LLMImprover()


# ── Agent 2: 클러스터 레벨 공식문서 자동 생성 ────────────────────────────────

def _generate_cluster_proposal(db: DBSession, cluster: ProposalCluster) -> str:
    """클러스터 집계가 임계치에 도달했을 때 공식 제안서를 자동 생성한다."""
    synthetic_msg = (
        f"주제: {cluster.topic}\n"
        f"키워드: {', '.join(cluster.keywords or [])}\n"
        f"분류: {cluster.classification}\n"
        f"{cluster.count}명이 같은 방향의 의견을 제출했습니다. "
        f"이를 바탕으로 공식 {cluster.classification} 문서를 작성해주세요."
    )

    prob = _structurer.structure(synthetic_msg, cluster.classification, cluster.responsible_dept)
    laws = _searcher.search_related_laws(prob, top_k=5)
    draft = _structurer.generate_proposal(synthetic_msg, prob, cluster.responsible_dept)
    proposal_dict = draft.model_dump()
    law_titles = [l.get("title", "") for l in laws if l.get("title")]
    proposal_dict["related_laws"] = list(dict.fromkeys(
        proposal_dict.get("related_laws", []) + law_titles
    ))[:8]

    from app.schemas.proposal import PolicyProposal
    proposal_obj = PolicyProposal(**proposal_dict)
    review = _reviewer.review(proposal_obj)
    visual = _visualizer.visualize(
        proposal_obj, review, [], cluster.classification,
        cluster_count=cluster.count,
    )

    proposal_id = str(uuid.uuid4())
    db_proposal = StructuredProposalModel(
        proposal_id=proposal_id,
        session_id=f"cluster-{cluster.cluster_id}",
        title=proposal_dict.get("title", f"{cluster.topic} {cluster.classification}"),
        background=proposal_dict.get("background", ""),
        core_requests=proposal_dict.get("core_requests", ""),
        expected_effects=proposal_dict.get("expected_effects", ""),
        responsible_dept=cluster.responsible_dept,
        related_laws=proposal_dict.get("related_laws", []),
    )
    db.add(db_proposal)
    db.flush()
    db.add(AnalysisResultModel(
        analysis_id=str(uuid.uuid4()),
        proposal_id=proposal_id,
        similar_cases=[],
        pass_probability=visual.pass_probability,
        expected_duration_days=visual.expected_duration_days,
        feasibility_score=visual.feasibility_score,
        visualization_data=visual.chart_data,
    ))
    db.commit()
    return proposal_id


# ── 요청/응답 스키마 ─────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    attachment_ids: Optional[List[str]] = None


class AnswerRequest(BaseModel):
    session_id: str
    answers: Dict[str, str]
    # 프론트엔드가 start 응답에서 받은 ctx를 그대로 전달 (서버리스용)
    ctx: Optional[Dict[str, Any]] = None


class FinalizeRequest(BaseModel):
    session_id: str
    accepted_improvement_ids: List[int]
    user_note: Optional[str] = None
    # 프론트엔드가 answer 응답에서 받은 ctx를 그대로 전달 (서버리스용)
    ctx: Optional[Dict[str, Any]] = None


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def _try_save_session(db: DBSession, session_id: str, stage: str, ctx: dict, status: str, classification: str | None = None) -> None:
    """DB 저장 시도 — 실패해도 API 흐름에 영향 없음 (서버리스 환경 대응)."""
    try:
        s = db.get(SessionModel, session_id)
        if s is None:
            s = SessionModel(
                session_id=session_id,
                user_input_mode="text",
                status=status,
                conversation_stage=stage,
                conversation_context=ctx,
            )
            if classification:
                s.final_classification = classification
            db.add(s)
        else:
            s.conversation_stage = stage
            s.conversation_context = ctx
            s.status = status
            if classification:
                s.final_classification = classification
            db.add(s)
        db.commit()
    except Exception as e:
        print(f"[Session] DB 저장 실패 (무시됨): {e}")


def _try_save_message(db: DBSession, session_id: str, role: str, content: str) -> None:
    """메시지 저장 시도 — 실패해도 무시."""
    try:
        db.add(MessageModel(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
        ))
        db.commit()
    except Exception as e:
        print(f"[Message] DB 저장 실패 (무시됨): {e}")


def _get_ctx_from_db(db: DBSession, session_id: str, expected_stage: str) -> dict:
    """DB에서 컨텍스트를 조회합니다."""
    session = db.get(SessionModel, session_id)
    if not session or session.conversation_stage != expected_stage:
        raise HTTPException(status_code=400, detail="잘못된 세션 상태입니다.")
    return session.conversation_context or {}


def _merge_attachment_text(db: DBSession, session_id: str, message: str, attachment_ids: list[str] | None) -> str:
    if not attachment_ids:
        return message
    try:
        from app.storage.models import Attachment as AttachmentModel
        parts = [message]
        for att_id in attachment_ids:
            att = db.get(AttachmentModel, att_id)
            if att and att.extracted_text:
                parts.append(f"\n[첨부: {att.filename}]\n{att.extracted_text[:2000]}")
        return "\n".join(parts)
    except Exception:
        return message


# ── TURN 1: 분류 + 질문 생성 ────────────────────────────────────────────────

@router.post("/conversation/start")
async def conversation_start(req: StartRequest, db: DBSession = Depends(get_db)):
    """초기 메시지를 분류하고 명확화 질문을 반환합니다."""
    session_id = req.session_id or str(uuid.uuid4())

    full_message = _merge_attachment_text(db, session_id, req.message, req.attachment_ids)
    _try_save_message(db, session_id, "user", req.message)

    # 분류
    routing = _router_agent.route_message(full_message)

    # 제안/청원인 경우 클러스터 배정 (Agent 1 집계 로직)
    cluster_id: str | None = None
    cluster_count: int = 0
    cluster_threshold: int = 50
    cluster_triggered: bool = False

    if routing.classification in ("제안", "청원"):
        try:
            cluster = _cluster_mgr.get_or_create_cluster(
                db,
                topic=routing.topic,
                keywords=routing.keywords,
                classification=routing.classification,
                responsible_dept=routing.responsible_dept,
            )
            cluster_id = cluster.cluster_id
            cluster_count = cluster.count
            cluster_threshold = cluster.threshold
            cluster_triggered = cluster.triggered

            # Agent 2: 임계치 도달 시 인라인으로 공식문서 생성
            if _trigger_mgr.should_trigger(cluster):
                try:
                    new_proposal_id = _generate_cluster_proposal(db, cluster)
                    cluster.proposal_id = new_proposal_id
                    db.add(cluster)
                    _trigger_mgr.mark_triggered(db, cluster)
                    cluster_triggered = True
                    print(f"[Agent2] 클러스터 {cluster_id} 공식문서 생성 완료: {new_proposal_id}")
                except Exception as e:
                    print(f"[Agent2] 클러스터 공식문서 생성 실패 (무시됨): {e}")

            # 세션에 cluster_id 기록
            s = db.get(SessionModel, session_id)
            if s is None:
                s = SessionModel(
                    session_id=session_id,
                    user_input_mode="text",
                    status="classified",
                    cluster_id=cluster_id,
                )
                db.add(s)
            else:
                s.cluster_id = cluster_id
                s.status = "aggregated"
                db.add(s)
            db.commit()
        except Exception as e:
            print(f"[Cluster] 배정 실패 (무시됨): {e}")

    # 명확화 질문 생성
    questions = _questioner.generate(full_message, routing.classification, n=5)

    ctx = {
        "stage": "questioning",
        "initial_message": full_message,
        "classification": routing.classification,
        "responsible_dept": routing.responsible_dept,
        "confidence": routing.confidence,
        "topic": routing.topic,
        "keywords": routing.keywords,
        "cluster_id": cluster_id,
        "cluster_count": cluster_count,
        "cluster_threshold": cluster_threshold,
        "questions": questions,
    }

    _try_save_session(db, session_id, "questioning", ctx, "classified", routing.classification)
    _try_save_message(db, session_id, "assistant",
        f"[{routing.classification}] 분류됨. 담당: {routing.responsible_dept}")

    return {
        "session_id": session_id,
        "stage": "questioning",
        "classification": routing.classification,
        "responsible_dept": routing.responsible_dept,
        "confidence": routing.confidence,
        "topic": routing.topic,
        "keywords": routing.keywords,
        "cluster_id": cluster_id,
        "cluster_count": cluster_count,
        "cluster_threshold": cluster_threshold,
        "cluster_triggered": cluster_triggered,
        "questions": questions,
        "ctx": ctx,
    }


# ── TURN 2: 답변 처리 → 초안 + 개선안 ──────────────────────────────────────

@router.post("/conversation/answer")
async def conversation_answer(req: AnswerRequest, db: DBSession = Depends(get_db)):
    """사용자 답변을 처리하고 초안 제안서 + 개선안을 반환합니다."""
    # 컨텍스트 우선순위: 요청 페이로드 > DB
    if req.ctx and req.ctx.get("stage") == "questioning":
        ctx = req.ctx
    else:
        ctx = _get_ctx_from_db(db, req.session_id, "questioning")

    questions: list[str] = ctx.get("questions", [])

    answers_text = "\n".join(
        f"Q{int(k)+1}. {questions[int(k)] if int(k) < len(questions) else ''}  \nA. {v}"
        for k, v in sorted(req.answers.items(), key=lambda x: int(x[0]))
    )
    _try_save_message(db, req.session_id, "user", answers_text)

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
    law_titles = [l.get("title", "") for l in laws if l.get("title")]
    existing = draft_dict.get("related_laws", [])
    draft_dict["related_laws"] = list(dict.fromkeys(existing + law_titles))[:8]

    # 개선안 제안
    improvements = _improver.suggest(classification, draft_dict, answers_text, n=4)
    improvements_data = [imp.model_dump() for imp in improvements]

    new_ctx = {
        **ctx,
        "stage": "improving",
        "user_answers": answers_text,
        "combined_message": combined_message,
        "structured_problem": prob.model_dump(),
        "related_laws": laws,
        "similar_cases": cases,
        "draft_proposal": draft_dict,
        "improvements": improvements_data,
    }

    _try_save_session(db, req.session_id, "improving", new_ctx, "structured")
    _try_save_message(db, req.session_id, "assistant",
        f"초안 제안서 작성 완료: 『{draft_dict['title']}』")

    return {
        "session_id": req.session_id,
        "stage": "improving",
        "classification": classification,
        "draft_proposal": draft_dict,
        "improvements": improvements_data,
        "related_laws": laws[:5],
        "similar_cases": cases,
        # 서버리스용
        "ctx": new_ctx,
    }


# ── TURN 3: 개선안 수락 → 최종 제안서 + DOCX ───────────────────────────────

@router.post("/conversation/finalize")
async def conversation_finalize(req: FinalizeRequest, db: DBSession = Depends(get_db)):
    """수락된 개선안을 반영한 최종 제안서를 생성하고 DOCX 파일을 제공합니다."""
    # 컨텍스트 우선순위: 요청 페이로드 > DB
    if req.ctx and req.ctx.get("stage") == "improving":
        ctx = req.ctx
    else:
        ctx = _get_ctx_from_db(db, req.session_id, "improving")

    classification = ctx["classification"]
    draft_proposal = ctx["draft_proposal"]
    improvements_data = ctx.get("improvements", [])
    user_answers = ctx.get("user_answers", "")

    accepted: list[Improvement] = [
        Improvement(**imp)
        for imp in improvements_data
        if imp["id"] in req.accepted_improvement_ids
    ]

    _try_save_message(db, req.session_id, "user",
        f"수락한 개선안: {req.accepted_improvement_ids}")

    # 최종 제안서 재작성
    final_proposal = _improver.refine_proposal(
        draft_proposal, accepted, req.user_note or "", user_answers, classification
    )

    # 타당성 검토 + 시각화
    from app.schemas.proposal import PolicyProposal
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

    # DB 저장 (실패해도 무시)
    try:
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
        db.commit()

        # 세션이 클러스터에 속하는 경우 아직 proposal 없으면 이 문서를 임시 연결
        try:
            session_obj = db.get(SessionModel, req.session_id)
            if session_obj and session_obj.cluster_id:
                cluster_obj = db.get(ProposalCluster, session_obj.cluster_id)
                if cluster_obj and not cluster_obj.proposal_id:
                    cluster_obj.proposal_id = proposal_id
                    db.add(cluster_obj)
                    db.commit()
        except Exception as ce:
            print(f"[Finalize] 클러스터 연결 실패 (무시됨): {ce}")

    except Exception as e:
        print(f"[Finalize] DB 저장 실패 (무시됨): {e}")

    final_ctx = {
        **ctx,
        "stage": "complete",
        "final_proposal": final_proposal,
        "review": review.model_dump(),
        "visual": analysis_dict,
        "docx_filename": docx_path.name,
    }
    _try_save_session(db, req.session_id, "complete", final_ctx, "completed")

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
        "ctx": final_ctx,
    }


# ── 문서 다운로드 ─────────────────────────────────────────────────────────────

@router.get("/session/{session_id}/download/docx")
async def download_docx(session_id: str, db: DBSession = Depends(get_db)):
    """생성된 DOCX 파일 다운로드."""
    from app.utils.doc_generator import DOCS_DIR

    # DOCX 파일명을 DB 또는 파일시스템에서 찾기
    docx_filename = None
    try:
        session = db.get(SessionModel, session_id)
        if session and session.conversation_context:
            docx_filename = session.conversation_context.get("docx_filename")
    except Exception:
        pass

    # DB에서 못 찾으면 파일시스템에서 패턴 검색
    if not docx_filename:
        prefix = session_id[:8]
        matches = list(DOCS_DIR.glob(f"{prefix}_*.docx"))
        if matches:
            docx_filename = matches[0].name

    if not docx_filename:
        raise HTTPException(status_code=404, detail="문서 파일을 찾을 수 없습니다.")

    file_path = DOCS_DIR / docx_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="문서 파일이 서버에 없습니다.")

    return FileResponse(
        path=str(file_path),
        filename=docx_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ── 대화 상태 조회 ────────────────────────────────────────────────────────────

@router.get("/conversation/{session_id}/state")
async def get_conversation_state(session_id: str, db: DBSession = Depends(get_db)):
    try:
        session = db.get(SessionModel, session_id)
    except Exception:
        session = None

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
            "download_url": f"/api/session/{session_id}/download/docx"
                if session.conversation_stage == "complete" else None,
        }
    }
