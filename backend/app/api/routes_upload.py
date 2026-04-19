"""파일 첨부 API — PDF/DOCX/이미지 업로드 및 텍스트 추출."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session as DBSession

from app.storage.db import get_db
from app.storage.models import Attachment, Session as SessionModel
from app.utils.file_extractor import extract_text

router = APIRouter()

import os as _os
UPLOAD_DIR = Path("/tmp/uploads") if _os.environ.get("VERCEL") else Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "text/plain",
}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    db: DBSession = Depends(get_db),
):
    """파일 업로드 및 텍스트 추출.

    Returns:
        attachment_id, filename, extracted_text (있을 경우)
    """
    content_type = (file.content_type or "application/octet-stream").lower().split(";")[0].strip()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"지원하지 않는 파일 형식입니다: {content_type}. PDF, DOCX, 이미지, TXT만 허용됩니다.",
        )

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="파일 크기는 20MB를 초과할 수 없습니다.")

    # 세션 확인 (없으면 생성)
    session = db.get(SessionModel, session_id)
    if session is None:
        session = SessionModel(session_id=session_id, user_input_mode="text", status="in_progress")
        db.add(session)
        db.commit()

    # 저장
    attachment_id = str(uuid.uuid4())
    safe_name = f"{attachment_id}_{file.filename or 'file'}"
    save_path = UPLOAD_DIR / safe_name
    save_path.write_bytes(data)

    # 텍스트 추출
    extracted = extract_text(data, content_type, file.filename or "")

    db_att = Attachment(
        attachment_id=attachment_id,
        session_id=session_id,
        filename=file.filename or "파일",
        content_type=content_type,
        file_size=len(data),
        extracted_text=extracted,
        storage_path=str(save_path),
    )
    db.add(db_att)
    db.commit()

    return {
        "attachment_id": attachment_id,
        "filename": file.filename,
        "content_type": content_type,
        "file_size": len(data),
        "extracted_text": extracted[:500] if extracted else None,  # 미리보기용 500자
        "has_text": bool(extracted),
    }


@router.get("/session/{session_id}/attachments")
async def list_attachments(session_id: str, db: DBSession = Depends(get_db)):
    """세션의 첨부파일 목록 조회."""
    atts = (
        db.query(Attachment)
        .filter(Attachment.session_id == session_id)
        .order_by(Attachment.created_at)
        .all()
    )
    return [
        {
            "attachment_id": a.attachment_id,
            "filename": a.filename,
            "content_type": a.content_type,
            "file_size": a.file_size,
            "has_text": bool(a.extracted_text),
            "created_at": a.created_at,
        }
        for a in atts
    ]
