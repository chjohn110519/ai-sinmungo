from typing import Literal, List, Optional
from pydantic import BaseModel


class RoutingResult(BaseModel):
    classification: Literal["민원", "제안", "청원"]
    confidence: float  # 0.0 ~ 1.0
    responsible_dept: str
    reasoning: str


class RoutingRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    attachment_ids: Optional[List[str]] = None  # 업로드된 첨부파일 ID 목록


class RoutingResponse(BaseModel):
    result: RoutingResult
    session_id: str