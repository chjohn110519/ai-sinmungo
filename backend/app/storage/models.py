from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_input_mode = Column(Enum("text", "voice"), default="text")
    final_classification = Column(Enum("민원", "제안", "청원"), nullable=True)
    status = Column(Enum("in_progress", "classified", "structured", "completed", "failed"), default="in_progress")
    # 다단계 대화 상태 저장 (questioning / improving / complete)
    conversation_stage = Column(String, nullable=True, default="init")
    conversation_context = Column(JSON, nullable=True)  # 단계별 축적 컨텍스트


class Message(Base):
    __tablename__ = "messages"

    message_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.session_id"))
    role = Column(Enum("user", "assistant"))
    content = Column(Text)
    agent_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    message_metadata = Column(JSON, nullable=True)  # token usage, model name 등

    session = relationship("Session", back_populates="messages")


class StructuredProposal(Base):
    __tablename__ = "structured_proposals"

    proposal_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.session_id"), unique=True)
    title = Column(String)                      # 법안명 형식
    background = Column(Text)                   # 제안 배경
    core_requests = Column(Text)                # 핵심 요청사항
    expected_effects = Column(Text)
    responsible_dept = Column(String)           # 소관 부처
    related_laws = Column(JSON)                 # 관련 법령 ID 리스트
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="proposal", foreign_keys=[session_id])


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    analysis_id = Column(String, primary_key=True)
    proposal_id = Column(String, ForeignKey("structured_proposals.proposal_id"))
    similar_cases = Column(JSON)                # 유사 사례 리스트
    pass_probability = Column(Float)            # 0.0 ~ 1.0
    expected_duration_days = Column(Integer)
    feasibility_score = Column(Float)
    visualization_data = Column(JSON)           # 프론트 차트용
    created_at = Column(DateTime, default=datetime.utcnow)

    proposal = relationship("StructuredProposal", back_populates="analysis")


class Attachment(Base):
    __tablename__ = "attachments"

    attachment_id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.session_id"))
    filename = Column(String)
    content_type = Column(String)
    file_size = Column(Integer)
    extracted_text = Column(Text, nullable=True)   # PDF/DOCX에서 추출한 텍스트
    storage_path = Column(String)                  # 서버 저장 경로
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", back_populates="attachments")


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    doc_id = Column(String, primary_key=True)
    doc_type = Column(Enum("law", "petition", "bill", "민원사례"))
    title = Column(String)
    content = Column(Text)
    source_url = Column(String, nullable=True)
    doc_metadata = Column(JSON, nullable=True)     # 소관부처, 공포일자 등
    embedding = Column(JSON, nullable=True)    # Chroma에 저장될 벡터 (임시)


# 역방향 관계 설정
Session.messages = relationship("Message", order_by=Message.created_at, back_populates="session")
Session.proposal = relationship("StructuredProposal", uselist=False, back_populates="session")
Session.attachments = relationship("Attachment", order_by=Attachment.created_at, back_populates="session")
StructuredProposal.analysis = relationship("AnalysisResult", uselist=False, back_populates="proposal")