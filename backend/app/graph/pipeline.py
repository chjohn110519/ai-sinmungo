"""LangGraph 기반 민원 처리 파이프라인.

State Flow:
  route → structure → search → generate → review ─┐(needs_revision, <2회)
                                    ↑───────────────┘
                                    ↓
                                visualize → [END]

Conditional edge: review 완료 후 needs_revision=True 이고 revision_count<2 이면
search 로 되돌아가서 법령 재검색 후 generate/review 반복.
"""

from __future__ import annotations

import asyncio
from typing import TypedDict, Optional, List, AsyncIterator

from langgraph.graph import StateGraph, END

from app.agents.router import AIRouter
from app.agents.llm1_structurer import LLM1Structurer
from app.agents.llm2_searcher import LLM2Searcher
from app.agents.llm3_reviewer import LLM3Reviewer
from app.agents.llm4_visualizer import LLM4Visualizer
from app.schemas.routing import RoutingResult
from app.schemas.proposal import StructuredProblem, PolicyProposal, ProposalReview, VisualAnalysis
from app.config import settings


# ─── 공유 에이전트 인스턴스 ───────────────────────────────────────────────────
_router = AIRouter()
_structurer = LLM1Structurer()
_searcher = LLM2Searcher(persist_dir=settings.chroma_persist_directory)
_reviewer = LLM3Reviewer()
_visualizer = LLM4Visualizer()


# ─── 파이프라인 상태 ──────────────────────────────────────────────────────────
class PipelineState(TypedDict):
    # 입력
    message: str
    session_id: str

    # 단계별 결과 (dict로 직렬화해 JSON 호환성 유지)
    routing_result: Optional[dict]
    structured_problem: Optional[dict]
    related_laws: Optional[List[dict]]
    similar_cases: Optional[List[dict]]
    policy_proposal: Optional[dict]
    proposal_review: Optional[dict]
    visual_analysis: Optional[dict]

    # 메타
    revision_count: int          # 재검토 횟수 (최대 1회)
    processing_steps: List[str]
    errors: List[str]
    current_node: str            # 현재 실행 중인 노드 이름 (SSE용)


# ─── 노드 함수 ────────────────────────────────────────────────────────────────

def _step(state: PipelineState, label: str) -> dict:
    """processing_steps 와 current_node 를 갱신하는 헬퍼."""
    return {
        "processing_steps": state["processing_steps"] + [label],
        "current_node": label,
    }


def node_route(state: PipelineState) -> dict:
    update = _step(state, "민원 분류 중...")
    try:
        result: RoutingResult = _router.route_message(state["message"])
        update["routing_result"] = result.model_dump()
        update["processing_steps"] = state["processing_steps"] + ["✓ 분류 완료"]
    except Exception as e:
        update["errors"] = state["errors"] + [f"route: {e}"]
        update["routing_result"] = {
            "classification": "민원",
            "confidence": 0.5,
            "responsible_dept": "행정안전부",
            "reasoning": str(e),
        }
    return update


def node_structure(state: PipelineState) -> dict:
    update = _step(state, "문제 구조화 중...")
    routing = state["routing_result"] or {}
    try:
        prob: StructuredProblem = _structurer.structure(
            state["message"],
            routing.get("classification", "민원"),
            routing.get("responsible_dept", "행정안전부"),
        )
        update["structured_problem"] = prob.model_dump()
        update["processing_steps"] = state["processing_steps"] + ["✓ 구조화 완료"]
    except Exception as e:
        update["errors"] = state["errors"] + [f"structure: {e}"]
        update["structured_problem"] = {
            "cause": state["message"],
            "affected_subjects": "일반국민",
            "resolution_direction": "개선 필요",
            "keywords": ["민원"],
        }
    return update


def node_search(state: PipelineState) -> dict:
    update = _step(state, "법령 검색 중...")
    sp = state["structured_problem"] or {}
    prob = StructuredProblem(**sp)
    try:
        laws = _searcher.search_related_laws(prob, top_k=3)
        cases = _searcher.search_similar_cases(prob, top_k=2)
        update["related_laws"] = laws
        update["similar_cases"] = cases
        update["processing_steps"] = state["processing_steps"] + ["✓ 검색 완료"]
    except Exception as e:
        update["errors"] = state["errors"] + [f"search: {e}"]
        update["related_laws"] = []
        update["similar_cases"] = []
    return update


def node_generate(state: PipelineState) -> dict:
    update = _step(state, "제안서 생성 중...")
    routing = state["routing_result"] or {}
    sp = state["structured_problem"] or {}
    prob = StructuredProblem(**sp)
    try:
        proposal: PolicyProposal = _structurer.generate_proposal(
            state["message"], prob, routing.get("responsible_dept", "행정안전부")
        )
        update["policy_proposal"] = proposal.model_dump()
        update["processing_steps"] = state["processing_steps"] + ["✓ 제안서 생성 완료"]
    except Exception as e:
        update["errors"] = state["errors"] + [f"generate: {e}"]
        update["policy_proposal"] = {
            "title": "제안 법안",
            "background": state["message"],
            "core_requests": "개선 요청",
            "expected_effects": "국민 편의 증진",
            "responsible_dept": routing.get("responsible_dept", "행정안전부"),
            "related_laws": [],
        }
    return update


def node_review(state: PipelineState) -> dict:
    update = _step(state, "타당성 검토 중...")
    pp = state["policy_proposal"] or {}
    proposal = PolicyProposal(**pp)
    try:
        review: ProposalReview = _reviewer.review(proposal)
        update["proposal_review"] = review.model_dump()
        update["revision_count"] = state["revision_count"]
        update["processing_steps"] = state["processing_steps"] + ["✓ 검토 완료"]
    except Exception as e:
        update["errors"] = state["errors"] + [f"review: {e}"]
        update["proposal_review"] = {
            "validity_score": 0.7,
            "strengths": [],
            "weaknesses": [],
            "revision_suggestions": [],
            "needs_revision": False,
        }
    return update


def node_visualize(state: PipelineState) -> dict:
    update = _step(state, "시각화 분석 중...")
    pp = state["policy_proposal"] or {}
    pr = state["proposal_review"] or {}
    routing = state["routing_result"] or {}
    proposal = PolicyProposal(**pp)
    review = ProposalReview(**pr)
    similar_cases = state["similar_cases"] or []
    try:
        visual: VisualAnalysis = _visualizer.visualize(
            proposal, review, similar_cases, routing.get("classification", "민원")
        )
        update["visual_analysis"] = visual.model_dump()
        update["processing_steps"] = state["processing_steps"] + ["✓ 분석 완료"]
    except Exception as e:
        update["errors"] = state["errors"] + [f"visualize: {e}"]
        update["visual_analysis"] = None
    return update


# ─── 조건부 엣지 ─────────────────────────────────────────────────────────────

def should_revise(state: PipelineState) -> str:
    """검토 결과 수정 필요 여부로 분기."""
    review = state.get("proposal_review") or {}
    needs = review.get("needs_revision", False)
    count = state.get("revision_count", 0)
    if needs and count < 1:
        return "revise"   # → node_search (재검색 후 재생성)
    return "done"         # → node_visualize


def increment_revision(state: PipelineState) -> dict:
    """재검토 전 카운터 증가."""
    return {"revision_count": state["revision_count"] + 1}


# ─── 그래프 빌드 ──────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(PipelineState)

    g.add_node("route",     node_route)
    g.add_node("structure", node_structure)
    g.add_node("search",    node_search)
    g.add_node("generate",  node_generate)
    g.add_node("review",    node_review)
    g.add_node("inc_rev",   increment_revision)   # 재검토 카운터 증가
    g.add_node("visualize", node_visualize)

    g.set_entry_point("route")
    g.add_edge("route",     "structure")
    g.add_edge("structure", "search")
    g.add_edge("search",    "generate")
    g.add_edge("generate",  "review")

    g.add_conditional_edges(
        "review",
        should_revise,
        {"revise": "inc_rev", "done": "visualize"},
    )
    g.add_edge("inc_rev",   "search")   # 재검색 후 재생성
    g.add_edge("visualize", END)

    return g.compile()


# ─── 공개 API ────────────────────────────────────────────────────────────────

# 컴파일된 그래프 (모듈 로드 시 1회만 빌드)
compiled_graph = build_graph()


def make_initial_state(message: str, session_id: str) -> PipelineState:
    return PipelineState(
        message=message,
        session_id=session_id,
        routing_result=None,
        structured_problem=None,
        related_laws=None,
        similar_cases=None,
        policy_proposal=None,
        proposal_review=None,
        visual_analysis=None,
        revision_count=0,
        processing_steps=[],
        errors=[],
        current_node="",
    )


def run_pipeline(message: str, session_id: str) -> PipelineState:
    """동기 실행 (POST /chat 용)."""
    initial = make_initial_state(message, session_id)
    return compiled_graph.invoke(initial)


def stream_pipeline(message: str, session_id: str):
    """스텝별 상태 업데이트를 yield (SSE 용).

    각 iteration 은 {node_name: state_update_dict} 형태.
    """
    initial = make_initial_state(message, session_id)
    return compiled_graph.stream(initial, stream_mode="updates")
