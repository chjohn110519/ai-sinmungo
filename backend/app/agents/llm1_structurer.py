"""LLM1 구조화 에이전트 — APMP 방법론 기반 제안서 생성.

sync OpenAI SDK 대신 httpx 직접 호출 (Vercel 서버리스 Connection error 방지).
structure() / generate_proposal() 모두 async.
"""

from __future__ import annotations
import json
import logging
import re
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


# ── Q&A 형식 감지 + 정제 헬퍼 ────────────────────────────────────────────────

def _is_qa_format(text: str) -> bool:
    """combined_message 형태의 Q&A 포맷 감지."""
    return "[추가 정보]" in text or bool(re.search(r"\bQ\d+\.", text))


def _clean_qa_to_prose(user_input: str, structured_problem=None) -> str:
    """Q&A combined_message에서 가독성 있는 prose 배경 생성.

    [추가 정보] 이전의 원본 문장을 추출하고,
    structured_problem 필드에서 원인·대상·해결 방향을 자연스러운 문장으로 조합한다.
    """
    original = user_input.split("[추가 정보]")[0].strip()
    parts: list[str] = [original] if original else []
    if structured_problem is not None:
        cause = getattr(structured_problem, "cause", "") or ""
        subjects = getattr(structured_problem, "affected_subjects", "") or ""
        direction = getattr(structured_problem, "resolution_direction", "") or ""
        # structured_problem의 cause가 user_input과 다를 때만 추가
        if cause and cause not in (original, user_input):
            parts.append(f"이 문제의 주요 원인은 {cause}입니다.")
        if subjects and subjects not in ("일반국민",):
            parts.append(f"주요 영향 대상은 {subjects}입니다.")
        if direction and direction not in ("개선 필요",):
            parts.append(f"해결 방향: {direction}")
    return "\n\n".join(parts) if parts else (original or "제안 내용을 확인해 주세요.")


def _default_laws_for_dept(responsible_dept: str) -> list[str]:
    dept = responsible_dept or ""
    if "국토" in dept or "교통" in dept:
        return ["도로법", "도로교통법", "교통안전법", "보행안전 및 편의증진에 관한 법률", "국토의 계획 및 이용에 관한 법률", "지방자치법", "행정절차법"]
    if "환경" in dept:
        return ["환경정책기본법", "대기환경보전법", "물환경보전법", "폐기물관리법", "소음·진동관리법", "지방자치법", "행정절차법"]
    if "복지" in dept or "보건" in dept:
        return ["사회복지사업법", "국민건강보험법", "노인복지법", "장애인복지법", "아동복지법", "지방자치법", "행정절차법"]
    if "교육" in dept:
        return ["교육기본법", "초·중등교육법", "고등교육법", "학교보건법", "학교폭력예방 및 대책에 관한 법률", "지방자치법", "행정절차법"]
    if "노동" in dept or "고용" in dept:
        return ["근로기준법", "산업안전보건법", "고용보험법", "직업안정법", "최저임금법", "지방자치법", "행정절차법"]
    return ["민원 처리에 관한 법률", "행정절차법", "전자정부법", "개인정보 보호법", "지방자치법", "공공기관의 운영에 관한 법률", "국가재정법"]


def _needs_expansion(text: str, min_len: int) -> bool:
    clean = (text or "").strip()
    return len(clean) < min_len or _is_qa_format(clean)


def _structured_background(existing: str, user_input: str, structured_problem) -> str:
    base = existing.strip()
    if _needs_expansion(base, 450):
        base = _clean_qa_to_prose(user_input, structured_problem)

    cause = getattr(structured_problem, "cause", "") or "제출된 의견에서 확인되는 생활상 불편과 제도적 공백"
    subjects = getattr(structured_problem, "affected_subjects", "") or "해당 문제의 영향을 받는 시민"
    direction = getattr(structured_problem, "resolution_direction", "") or "담당 기관의 제도 개선과 현장 조치"

    if len(base) >= 450 and not _is_qa_format(base) and ("1." in base or "현황" in base):
        return base

    return (
        "1. 현황 및 문제 인식\n"
        f"{base}\n\n"
        "2. 문제 원인\n"
        f"본 사안의 핵심 원인은 {cause}로 정리된다. 단순한 개별 불편이 아니라 반복적으로 발생할 경우 행정 신뢰도, 시민 안전, 생활 편의에 영향을 줄 수 있는 공공 문제로 볼 수 있다.\n\n"
        "3. 영향 대상과 공공성\n"
        f"주요 영향 대상은 {subjects}이다. 해당 대상은 직접적인 불편을 겪는 시민뿐 아니라 같은 생활권을 이용하는 주민, 방문자, 취약계층까지 확장될 수 있으므로 공공 개입 필요성이 있다.\n\n"
        "4. 제도 개선 필요성\n"
        f"해결 방향은 {direction}이다. 이를 위해 담당 기관은 현황 확인, 관련 법령 검토, 예산 및 집행 가능성 검토, 단계별 개선 계획 수립을 함께 추진할 필요가 있다. 정확한 피해 규모와 빈도는 추가 행정조사 또는 공개 통계 확인을 통해 보완하는 것이 바람직하다."
    )


def _structured_core_requests(existing: str, structured_problem, responsible_dept: str) -> str:
    clean = existing.strip()
    if not _needs_expansion(clean, 450) and clean.count("\n") >= 3:
        return clean

    cause = getattr(structured_problem, "cause", "") or "현장 문제"
    direction = getattr(structured_problem, "resolution_direction", "") or "제도 개선"
    subjects = getattr(structured_problem, "affected_subjects", "") or "시민"

    return (
        "1. 현황 조사 및 실태 확인\n"
        f"- {responsible_dept} 또는 관계 기관은 {cause}와 관련된 현장 현황, 민원 발생 빈도, 피해 대상, 기존 조치 이력을 우선 조사해야 한다.\n\n"
        "2. 관련 법령 및 지침 정비\n"
        f"- {direction}이 실제 행정 조치로 이어질 수 있도록 관련 법령, 조례, 내부 지침, 예산 집행 기준을 함께 검토하고 필요한 경우 개정안을 마련해야 한다.\n\n"
        "3. 단계별 실행 계획 수립\n"
        "- 즉시 조치가 가능한 사항은 단기 과제로 분리하고, 예산·시설·인력 확보가 필요한 사항은 6개월 및 1년 단위의 중장기 과제로 나누어 추진해야 한다.\n\n"
        "4. 시민 안내 및 의견 수렴 체계 마련\n"
        f"- {subjects}이 처리 상황을 확인할 수 있도록 접수 번호, 담당 부서, 예상 처리 기간, 후속 조치 계획을 안내하고 추가 의견을 제출할 수 있는 창구를 제공해야 한다.\n\n"
        "5. 성과 관리 및 재발 방지\n"
        "- 조치 이후에는 처리 결과, 만족도, 재발 여부를 확인하고 동일 유형의 민원이 반복되지 않도록 정기 점검 기준을 마련해야 한다."
    )


def _structured_expected_effects(existing: str, structured_problem) -> str:
    clean = existing.strip()
    if not _needs_expansion(clean, 320) and clean.count("\n") >= 3:
        return clean

    subjects = getattr(structured_problem, "affected_subjects", "") or "시민"
    direction = getattr(structured_problem, "resolution_direction", "") or "제도 개선"

    return (
        "1. 직접 효과\n"
        f"- {subjects}이 겪는 불편과 위험을 줄이고, 문제 해결 과정의 예측 가능성을 높일 수 있다.\n"
        f"- {direction}이 제도화되면 담당 기관의 처리 기준이 명확해져 유사 사안의 대응 속도가 개선된다.\n"
        "- 접수, 검토, 조치, 결과 안내가 하나의 흐름으로 정리되어 시민의 반복 문의와 행정 부담을 줄일 수 있다.\n\n"
        "2. 간접 효과\n"
        "- 동일 유형의 문제가 축적될 경우 정책 개선 의제로 발전시킬 수 있어 단발성 민원을 구조적 개선으로 연결할 수 있다.\n"
        "- 처리 과정과 근거가 문서화되므로 행정 투명성, 정책 신뢰도, 시민 참여 효능감을 높일 수 있다.\n\n"
        "3. 성과 확인 방식\n"
        "- 처리 완료 건수, 재발 민원 수, 시민 만족도, 조치 소요 기간, 관련 예산 집행 여부를 기준으로 개선 효과를 사후 점검할 수 있다."
    )


def _fallback_summary(proposal_title: str, structured_problem) -> str:
    direction = getattr(structured_problem, "resolution_direction", "") or "제도 개선"
    subjects = getattr(structured_problem, "affected_subjects", "") or "시민"
    return (
        f"{proposal_title}은 {subjects}이 겪는 불편을 줄이기 위해 {direction}을 추진하도록 요청하는 제안이다. "
        "현황 조사, 법령 검토, 단계별 실행계획, 사후 점검을 함께 마련해 실질적인 개선으로 연결하는 것이 핵심이다."
    )[:220]


def _fallback_proof_points(user_input: str, structured_problem) -> list[str]:
    original = user_input.split("[추가 정보]")[0].strip()
    points = []
    if original:
        points.append(f"사용자 제출 내용: {original[:120]}")
    if getattr(structured_problem, "affected_subjects", None):
        points.append(f"영향 대상: {structured_problem.affected_subjects}")
    if getattr(structured_problem, "resolution_direction", None):
        points.append(f"해결 방향: {structured_problem.resolution_direction}")
    return points[:5]


def _extract_json(text: str) -> dict:
    """텍스트에서 JSON 블록 추출 (Anthropic 등 plain-text 응답 파싱용)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise


class LLM1Structurer:
    """정책 제안 입력을 구조화하고 정책 제안서를 생성하는 LLM 에이전트."""

    # ── 구조화 ──────────────────────────────────────────────────────────────

    async def structure(
        self, user_input: str, classification: str, responsible_dept: str
    ) -> StructuredProblem:
        """사용자 입력을 구조화된 문제로 변환 (APMP Win Theme 추출 포함).

        OpenAI → Anthropic → 기본값 순으로 폴백.
        """
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

        data: dict | None = None
        # 1) OpenAI 시도
        try:
            resp_text = await self._call_openai(_STRUCTURE_SYSTEM, prompt, max_tokens=800, temperature=0.3)
            data = json.loads(resp_text)
        except Exception as e1:
            logger.warning("LLM1 structure OpenAI 실패, Anthropic 폴백: %s: %s", type(e1).__name__, e1)
            # 2) Anthropic 폴백
            try:
                resp_text = await self._call_anthropic(_STRUCTURE_SYSTEM, prompt, max_tokens=800)
                data = _extract_json(resp_text)
            except Exception as e2:
                logger.warning("LLM1 structure Anthropic도 실패 (기본값): %s: %s", type(e2).__name__, e2)

        if data is None:
            return self._default_structured_problem(user_input)

        return StructuredProblem(
            cause=data.get("cause", user_input),
            affected_subjects=data.get("affected_subjects", "일반국민"),
            resolution_direction=data.get("resolution_direction", "개선 필요"),
            keywords=data.get("keywords", ["민원", "정책", "제안"]),
            win_theme=data.get("win_theme") or None,
            discriminators=data.get("discriminators") or None,
        )

    def _default_structured_problem(self, user_input: str) -> StructuredProblem:
        return StructuredProblem(
            cause=user_input,
            affected_subjects="일반국민",
            resolution_direction="개선 필요",
            keywords=["민원", "정책", "제안"],
            win_theme=None,
            discriminators=None,
        )

    # ── 공통 LLM 호출 헬퍼 ──────────────────────────────────────────────────

    async def _call_openai(
        self,
        system: str,
        prompt: str,
        max_tokens: int,
        temperature: float = 0.3,
    ) -> str:
        """OpenAI Chat Completions API 호출 (JSON mode). API key 없으면 RuntimeError."""
        api_key = _get_api_key()
        if not api_key:
            raise RuntimeError("OpenAI API key 미설정")
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                _OPENAI_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": _get_model(),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def _call_anthropic(self, system: str, prompt: str, max_tokens: int) -> str:
        """Anthropic Claude API 호출 (OpenAI 폴백용). API key 없으면 RuntimeError."""
        ant_key = (settings.anthropic_api_key or "").strip()
        if not ant_key:
            raise RuntimeError("Anthropic API key 미설정")
        import anthropic as _ant  # 지연 임포트
        client = _ant.AsyncAnthropic(api_key=ant_key)
        msg = await client.messages.create(
            model=getattr(settings, "anthropic_model_name", None) or "claude-3-5-sonnet-20241022",
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    # ── 제안서 생성 ──────────────────────────────────────────────────────────

    async def generate_proposal(
        self,
        user_input: str,
        structured_problem: StructuredProblem,
        responsible_dept: str,
        web_context: list[dict] | None = None,
    ) -> PolicyProposal:
        """구조화된 문제에서 APMP 방법론 기반 정책 제안서 생성.

        OpenAI → Anthropic → 기본값 순으로 폴백.
        """

        discriminators_str = ", ".join(structured_problem.discriminators or []) or "없음"

        # ── 웹 검색 컨텍스트 블록 구성 ────────────────────────────────────────
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
        else:
            # 검색 결과 없음 → 수치 날조 절대 금지
            web_block = (
                "[검색 결과 없음]\n"
                "⚠️ 웹 검색 결과가 제공되지 않았습니다. "
                "background, proof_points, expected_effects 등 모든 필드에서 "
                "구체적인 수치·통계·사례·날짜를 절대 생성하지 마세요. "
                "사용자가 직접 제공한 정보만 사용하고, 수치가 필요한 자리는 "
                "'(관련 통계 확인 필요)' 또는 '구체적 수치는 담당 기관 확인 필요'로 대체하세요.\n\n"
            )

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
- 반드시 "1. 현황 및 문제 인식", "2. 문제 원인", "3. 영향 대상과 공공성", "4. 제도 개선 필요성"의 4개 소제목으로 구성하세요.
- 위 [실제 검색 결과]에서 확인된 통계·수치만 포함하세요.
- 검색 결과에 없는 구체적 숫자는 추정하지 말고 서술형으로 대체하세요.
  예: "정확한 규모는 관련 기관 통계 확인이 필요하나, 검색 결과에 따르면..."
- 현황 및 문제점 서술 (검색 결과 인용 시 출처 명시)
- 문제의 심각성과 사회적 파급 효과
- 현행 법령·제도의 한계 및 공백 분석
- 문제 발생 장소, 시간, 규모 등 Q&A에서 얻은 사실 정보를 자연스러운 문장으로 통합

core_requests (600자 이상):
- 최소 5개의 구체적 정책 요청 사항
- 반드시 번호 목록으로 작성하고, 각 항목은 "요청 내용 - 실행 방식 - 담당 주체"가 드러나야 합니다.
- 각 요청에 "○○법 제○조에 따라..." 형식으로 법적 근거 명시
- 단계별 이행 방안 포함

expected_effects (400자 이상):
- 반드시 "1. 직접 효과", "2. 간접 효과", "3. 성과 확인 방식"의 3개 소제목으로 구성하세요.
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

        data: dict | None = None
        # 1) OpenAI 시도
        try:
            resp_text = await self._call_openai(_GENERATE_SYSTEM, prompt, max_tokens=3500, temperature=0.4)
            data = json.loads(resp_text)
        except Exception as e1:
            logger.warning("LLM1 generate_proposal OpenAI 실패, Anthropic 폴백: %s: %s", type(e1).__name__, e1)
            # 2) Anthropic 폴백
            try:
                resp_text = await self._call_anthropic(_GENERATE_SYSTEM, prompt, max_tokens=4096)
                data = _extract_json(resp_text)
            except Exception as e2:
                logger.warning("LLM1 generate_proposal Anthropic도 실패 (기본값): %s: %s", type(e2).__name__, e2)
                return self._default_proposal(user_input, responsible_dept, structured_problem)

        # ── 품질 검증: Q&A 형식 또는 너무 짧은 필드는 정제된 값으로 교체 ────────
        bg = data.get("background") or ""
        cr = data.get("core_requests") or ""
        ee = data.get("expected_effects") or ""

        if _needs_expansion(bg, 450):
            logger.info("LLM1: background 품질 미달 → 구조화 배경으로 확장")
        if _needs_expansion(cr, 450):
            logger.info("LLM1: core_requests 품질 미달 → 구조화 요청사항으로 확장")
        if _needs_expansion(ee, 320):
            logger.info("LLM1: expected_effects 품질 미달 → 구조화 기대효과로 확장")

        bg = _structured_background(bg, user_input, structured_problem)
        cr = _structured_core_requests(cr, structured_problem, responsible_dept)
        ee = _structured_expected_effects(ee, structured_problem)

        related_laws = [
            item.get("title", "") if isinstance(item, dict) else str(item)
            for item in (data.get("related_laws") or [])
            if item
        ]
        if len(related_laws) < 5:
            related_laws = list(dict.fromkeys(related_laws + _default_laws_for_dept(responsible_dept)))

        title = data.get("title") or "정책 개선 제안"
        executive_summary = data.get("executive_summary") or _fallback_summary(title, structured_problem)
        win_theme = data.get("win_theme") or structured_problem.win_theme
        proof_points = data.get("proof_points") or _fallback_proof_points(user_input, structured_problem)
        # ─────────────────────────────────────────────────────────────────────

        return PolicyProposal(
            title=title,
            background=bg,
            core_requests=cr,
            expected_effects=ee,
            responsible_dept=data.get("responsible_dept", responsible_dept),
            related_laws=related_laws,
            executive_summary=executive_summary,
            win_theme=win_theme,
            proof_points=proof_points,
        )

    def _default_proposal(
        self,
        user_input: str,
        responsible_dept: str,
        structured_problem=None,
    ) -> PolicyProposal:
        """LLM 호출 실패 시 최소한의 가독성을 갖춘 fallback 제안서 반환.

        background: Q&A raw 텍스트 대신 structured_problem + 원문에서 prose 생성.
        core_requests / expected_effects: 빈 문자열 대신 기본 bullet 3개 제공.
        """
        title = "정책 개선 제안"
        background = _structured_background("", user_input, structured_problem)
        core_requests = _structured_core_requests("", structured_problem, responsible_dept)
        expected_effects = _structured_expected_effects("", structured_problem)
        return PolicyProposal(
            title=title,
            background=background,
            core_requests=core_requests,
            expected_effects=expected_effects,
            responsible_dept=responsible_dept,
            related_laws=_default_laws_for_dept(responsible_dept),
            executive_summary=_fallback_summary(title, structured_problem),
            win_theme=getattr(structured_problem, "win_theme", None),
            proof_points=_fallback_proof_points(user_input, structured_problem),
        )
