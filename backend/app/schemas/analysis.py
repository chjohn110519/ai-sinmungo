from typing import List, Optional
from pydantic import BaseModel
from app.schemas.routing import RoutingResult
from app.schemas.proposal import StructuredProblem, PolicyProposal, ProposalReview, VisualAnalysis


class AnalysisResult(BaseModel):
    analysis_id: str
    proposal_id: str
    similar_cases: List[dict]      # [{case_id, similarity, title}, ...]
    pass_probability: float        # 0.0 ~ 1.0
    expected_duration_days: int
    feasibility_score: float
    visualization_data: dict       # 프론트 차트용


class MLPPrediction(BaseModel):
    pass_probability: float
    expected_duration_days: int
    feasibility_score: float


class SimilarCase(BaseModel):
    case_id: str
    similarity: float
    title: str
    content_snippet: str
    source_url: Optional[str] = None


class ComprehensiveAnalysisResponse(BaseModel):
    """완전한 AI 분석 응답 - 5단계 파이프라인"""
    session_id: str
    
    # 1단계: 분류
    routing_result: RoutingResult
    
    # 2단계: 구조화
    structured_problem: Optional[StructuredProblem] = None
    
    # 3단계: 법령 검색
    related_laws: Optional[List[dict]] = None
    similar_cases: Optional[List[dict]] = None
    
    # 4단계: 제안서 생성
    policy_proposal: Optional[PolicyProposal] = None
    
    # 5단계: 타당성 검토
    proposal_review: Optional[ProposalReview] = None

    # 6단계: 시각화 분석 (LLM4)
    visual_analysis: Optional[VisualAnalysis] = None

    # 메타데이터
    processing_steps: List[str] = []
    errors: List[str] = []
    success: bool = True
