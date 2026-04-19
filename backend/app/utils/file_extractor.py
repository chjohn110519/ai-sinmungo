"""파일 유형별 텍스트 추출 유틸리티."""

from __future__ import annotations

import io


def extract_text(data: bytes, content_type: str, filename: str) -> str:
    """파일 바이트에서 텍스트 추출.

    지원 형식:
    - PDF → pypdf
    - DOCX → python-docx
    - TXT → UTF-8 디코딩
    - 이미지 → Pillow로 열어 파일명/메타 반환 (OCR 없음)
    """
    ct = content_type.lower()

    if ct == "application/pdf" or filename.lower().endswith(".pdf"):
        return _extract_pdf(data)

    if ct in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ) or filename.lower().endswith((".docx", ".doc")):
        return _extract_docx(data)

    if ct == "text/plain" or filename.lower().endswith(".txt"):
        return _extract_text_plain(data)

    if ct.startswith("image/"):
        return _extract_image_info(data, filename)

    return ""


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
        return "\n\n".join(pages)
    except Exception as e:
        print(f"[FileExtractor] PDF 추출 오류: {e}")
        return ""


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(data))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except Exception as e:
        print(f"[FileExtractor] DOCX 추출 오류: {e}")
        return ""


def _extract_text_plain(data: bytes) -> str:
    for encoding in ("utf-8", "euc-kr", "cp949", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_image_info(data: bytes, filename: str) -> str:
    """이미지는 OCR 없이 파일 메타 정보만 반환."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        return f"[첨부 이미지] {filename} ({img.width}×{img.height}, {img.mode})"
    except Exception:
        return f"[첨부 이미지] {filename}"
