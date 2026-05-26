from typing import List, Optional
from pydantic import BaseModel


class StructuredProblem(BaseModel):
    cause: str              # 문제의 원인
    affected_subjects: str  # 영향받는 대상
    resolution_direction: str  # 해결 방향
    keywords: List[str]
    # APMP: Win Theme & Discriminators
    win_theme: Optional[str] = None              # 핵심 승리 메시지 1~2문장
    discriminators: Optional[List[str]] = None   # 차별화 포인트 3개


class PolicyProposal(BaseModel):
    title: str              # 법안명
    background: str         # 제안이유
    core_requests: str      # 주요내용
    expected_effects: str
    responsible_dept: str   # 소관위원회
    related_laws: List[str]
    # APMP: Executive Summary, Win Theme, Proof Points
    executive_summary: Optional[str] = None      # 의사결정자용 150~200자 요약
    win_theme: Optional[str] = None              # StructuredProblem에서 전달
    proof_points: Optional[List[str]] = None     # 수치 기반 주장 5개+


class ProposalReview(BaseModel):
    validity_score: float  # 0.0 ~ 1.0
    strengths: List[str]
    weaknesses: List[str]
    revision_suggestions: List[str]
    needs_revision: bool
    # APMP: Red Team 준수 체크
    apmp_compliance: Optional[dict] = None        # APMP 준수 체크 결과
    proof_point_score: Optional[float] = None     # 증거 충실도 0.0~1.0
    buyer_centric_score: Optional[float] = None   # 독자 중심 언어 0.0~1.0


class VisualAnalysis(BaseModel):
    similar_cases: List[dict]
    feasibility_score: float
    pass_probability: float
    expected_duration_days: int
    chart_data: dict  # 프론트에서 recharts로 렌더링
