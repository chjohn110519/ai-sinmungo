from typing import Literal, List, Optional
from pydantic import BaseModel, Field


class RoutingResult(BaseModel):
    classification: Literal["민원", "제안", "청원"]
    confidence: float
    responsible_dept: str
    reasoning: str
    topic: str = Field(default="일반", description="대주제 (예: 교통, 환경, 주거)")
    keywords: List[str] = Field(default_factory=list, description="핵심 키워드 목록")


class ClassificationResult(RoutingResult):
    """클러스터 배정 정보까지 포함한 확장 분류 결과."""
    cluster_id: Optional[str] = None
    cluster_count: int = 0
    cluster_threshold: int = 50
    cluster_triggered: bool = False


class RoutingRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    attachment_ids: Optional[List[str]] = None


class RoutingResponse(BaseModel):
    result: RoutingResult
    session_id: str