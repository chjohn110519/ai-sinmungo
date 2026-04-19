from typing import List
from pydantic import BaseModel


class StructuredProblem(BaseModel):
    cause: str              # 문제의 원인
    affected_subjects: str  # 영향받는 대상
    resolution_direction: str  # 해결 방향
    keywords: List[str]


class PolicyProposal(BaseModel):
    title: str              # 법안명
    background: str         # 제안이유
    core_requests: str      # 주요내용
    expected_effects: str
    responsible_dept: str   # 소관위원회
    related_laws: List[str]


class ProposalReview(BaseModel):
    validity_score: float  # 0.0 ~ 1.0
    strengths: List[str]
    weaknesses: List[str]
    revision_suggestions: List[str]
    needs_revision: bool


class VisualAnalysis(BaseModel):
    similar_cases: List[dict]
    feasibility_score: float
    pass_probability: float
    expected_duration_days: int
    chart_data: dict  # 프론트에서 recharts로 렌더링