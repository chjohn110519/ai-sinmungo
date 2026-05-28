"""LLM1 구조화 에이전트 — APMP 방법론 기반 제안서 생성.

sync OpenAI SDK 대신 httpx 직접 호출 (Vercel 서버리스 Connection error 방지).
structure() / generate_proposal() 모두 async.
"""

from __future__ import annotations
import json
import logging
from typing import Optional

import httpx

from app.schemas.proposal import StructuredProblem, PolicyProposal
from app.config import settings

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_TIMEOUT = httpx.Timeout(connect=10.0, read=90.0, write=30.0, pool=10.0)

_STRUCTURE_SYSTEM = (
    "당신은 정부 정책 제안서 작성 전문가이자 APMP 인증 제안 관리 전문가입니다. "
    "제안서의 핵심 승리 메시지(Win Theme)를 도출하고 의사결정자 중심으로 문제를 구조화합니다."
)

_GENERATE_SYSTEM = (
    "당신은 대한민국 국회 입법조사처 수석 연구원으로, "
    "실제 통과된 법안 수준의 정책 제안서를 APMP 방법론에 따라 작성합니다."
)


def _get_api_key() -> str:
    return (settings.openai_api_key or "").strip()


def _get_model() -> str:
    return (settings.openai_model_name or "gpt-4o-mini").strip()


class LLM1Structurer:
    """정책 제안 입력을 구조화하고 정책 제안서를 생성하는 LLM 에이전트."""

    # ── 구조화 ──────────────────────────────────────────────────────────────

    async def structure(
        self, user_input: str, classification: str, responsible_dept: str
    ) -> StructuredProblem:
        """사용자 입력을 구조화된 문제로 변환 (APMP Win Theme 추출 포함)."""
        api_key = _get_api_key()
        if not api_key:
            return self._default_structured_problem(user_input)

        prompt = f"""다음 {classification} 내용을 분석하여 핵심 문제를 구조화하세요.

입력: {user_input}

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "cause": "문제의 근본 원인 (1~2문장)",
  "affected_subjects": "영향받는 대상 그룹",
  "resolution_direction": "해결 방향 (1문장)",
  "keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"],
  "win_theme": "이 제안이 반드시 승인되어야 하는 핵심 이유 1~2문장. 형식: '○○문제로 인해 [피해 대상]이 [피해 내용]을 겪고 있으므로, [해결책]을 통해 [핵심 이익]을 실현해야 합니다.'",
  "discriminators": ["긴급성: 연간 ○만명 영향", "선례: ○○국 시행 성공", "법적 공백: 현행 ○○법 미규정"]
}}"""

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    _OPENAI_URL,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": _get_model(),
                        "messages": [
                            {"role": "system", "content": _STRUCTURE_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 800,
                        "response_format": {"type": "json_object"},
                    },
                )
                resp.raise_for_status()
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            return StructuredProblem(
                cause=data.get("cause", user_input),
                affected_subjects=data.get("affected_subjects", "일반국민"),
                resolution_direction=data.get("resolution_direction", "개선 필요"),
                keywords=data.get("keywords", ["민원", "정책", "제안"]),
                win_theme=data.get("win_theme") or None,
                discriminators=data.get("discriminators") or None,
            )
        except Exception as e:
            logger.warning("LLM1 structure 오류 (폴백): %s: %s", type(e).__name__, e)
            return self._default_structured_problem(user_input)

    def _default_structured_problem(self, user_input: str) -> StructuredProblem:
        return StructuredProblem(
            cause=user_input,
            affected_subjects="일반국민",
            resolution_direction="개선 필요",
            keywords=["민원", "정책", "제안"],
            win_theme=None,
            discriminators=None,
        )

    # ── 제안서 생성 ──────────────────────────────────────────────────────────

    async def generate_proposal(
        self,
        user_input: str,
        structured_problem: StructuredProblem,
        responsible_dept: str,
        web_context: list[dict] | None = None,
    ) -> PolicyProposal:
        """구조화된 문제에서 APMP 방법론 기반 정책 제안서 생성."""
        api_key = _get_api_key()
        if not api_key:
            return self._default_proposal(user_input, responsible_dept)

        discriminators_str = ", ".join(structured_problem.discriminators or []) or "없음"

        # ── 웹 검색 컨텍스트 블록 구성 ────────────────────────────────────────
        web_block = ""
        if web_context:
            lines = ["[실제 검색 결과 — 아래 내용만 인용 허용]"]
            for i, r in enumerate(web_context[:8], 1):
                title = r.get("title", "")
                url   = r.get("url", "")
                body  = r.get("content", "")
                ref   = f"({url})" if url else ""
                lines.append(f"{i}. 출처: {title} {ref}\n   {body}")
            lines.append(
                "\n[주의] 위 검색 결과에 없는 수치·통계는 절대 생성하지 마세요. "
                "근거가 불확실한 경우 '(출처 확인 필요)'로 표기하세요."
            )
            web_block = "\n".join(lines) + "\n\n"

        prompt = f"""{web_block}[입력 정보]
민원/제안 내용 (원본 + Q&A 추가 정보 포함):
{user_input}

문제 원인 분석: {structured_problem.cause}
영향받는 대상: {structured_problem.affected_subjects}
해결 방향: {structured_problem.resolution_direction}
담당 부처: {responsible_dept}
핵심 승리 메시지(Win Theme): {structured_problem.win_theme or "설정 필요"}
차별화 포인트: {discriminators_str}

[각 필드 작성 지침]

title: "○○에 관한 ○○법 개정 요청" 또는 "○○ 안전 강화를 위한 ○○ 개선 제안" 형식의 공식 제목

executive_summary (150~200자):
- 의사결정자(장관/위원장)가 30초 안에 읽는 요약. 반드시 Win Theme 문장으로 시작.
- 문제 → 해결책 → 핵심 기대효과 순서.

win_theme: 위 핵심 승리 메시지를 그대로 유지하거나 보다 설득력 있게 개선.

proof_points (검색 결과에서 확인된 사실 기반, 최대 5개):
- 반드시 위 [실제 검색 결과]에서 확인된 내용만 사용하세요.
- 형식: "출처: [제목] — 내용 (URL)" 또는 "○○에 따르면 ○○ (출처 URL)"
- 검색 결과에 수치가 없으면 해당 항목을 생략하거나 "(출처 확인 필요)"로 표기.
- 절대로 수치·통계를 추정하거나 발명하지 마세요.
- 막연한 표현("많은", "크게") 금지.

background (600자 이상):
⚠️ 중요: 원본 입력의 "Q1., A., Q2., A." 형식을 그대로 복사하지 마세요.
모든 내용을 전문적인 행정 서술체로 완전히 재작성해야 합니다.
- 위 [실제 검색 결과]에서 확인된 통계·수치만 포함하세요.
- 검색 결과에 없는 구체적 숫자는 추정하지 말고 서술형으로 대체하세요.
  예: "정확한 규모는 관련 기관 통계 확인이 필요하나, 검색 결과에 따르면..."
- 현황 및 문제점 서술 (검색 결과 인용 시 출처 명시)
- 문제의 심각성과 사회적 파급 효과
- 현행 법령·제도의 한계 및 공백 분석
- 문제 발생 장소, 시간, 규모 등 Q&A에서 얻은 사실 정보를 자연스러운 문장으로 통합

core_requests (600자 이상):
- 최소 5개의 구체적 정책 요청 사항
- 각 요청에 "○○법 제○조에 따라..." 형식으로 법적 근거 명시
- 단계별 이행 방안 포함

expected_effects (400자 이상):
- 직접 효과 3가지 이상 (정량적 목표 포함)
- 간접 효과 2가지 이상

related_laws: 관련 한국 법령 7개 이상 (실제 법령명 배열)
responsible_dept: "{responsible_dept}"

[APMP Buyer-Centric 원칙]
- "우리가 제안한다" → "시민은 ○○의 혜택을 받게 됩니다" (독자 중심)
- 의사결정자가 승인했을 때 얻는 이익 중심으로 서술

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "title": "...",
  "executive_summary": "...",
  "win_theme": "...",
  "proof_points": ["...", "...", "..."],
  "background": "...",
  "core_requests": "...",
  "expected_effects": "...",
  "related_laws": ["법령1", "법령2"],
  "responsible_dept": "{responsible_dept}"
}}"""

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    _OPENAI_URL,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": _get_model(),
                        "messages": [
                            {"role": "system", "content": _GENERATE_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.4,
                        "max_tokens": 3500,
                        "response_format": {"type": "json_object"},
                    },
                )
                resp.raise_for_status()
            data = json.loads(resp.json()["choices"][0]["message"]["content"])
            return PolicyProposal(
                title=data.get("title", "제안서"),
                background=data.get("background", user_input),
                core_requests=data.get("core_requests", "개선 요청"),
                expected_effects=data.get("expected_effects", "정책 개선 및 국민 편의 증진"),
                responsible_dept=data.get("responsible_dept", responsible_dept),
                related_laws=data.get("related_laws", []),
                executive_summary=data.get("executive_summary") or None,
                win_theme=data.get("win_theme") or None,
                proof_points=data.get("proof_points") or None,
            )
        except Exception as e:
            logger.warning("LLM1 generate_proposal 오류 (폴백): %s: %s", type(e).__name__, e)
            return self._default_proposal(user_input, responsible_dept)

    def _default_proposal(self, user_input: str, responsible_dept: str) -> PolicyProposal:
        return PolicyProposal(
            title="제안 법안",
            background=user_input,
            core_requests="개선 요청",
            expected_effects="정책 개선 및 국민 편의 증진",
            responsible_dept=responsible_dept,
            related_laws=[],
            executive_summary=None,
            win_theme=None,
            proof_points=None,
        )
