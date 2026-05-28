import logging

from app.schemas.proposal import PolicyProposal, ProposalReview
from app.config import settings

logger = logging.getLogger(__name__)

try:
    import instructor
    from anthropic import Anthropic
    from openai import OpenAI
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False
    try:
        from openai import OpenAI
    except ImportError:
        OpenAI = None
    try:
        from anthropic import Anthropic
    except ImportError:
        Anthropic = None

_REVIEW_SYSTEM = (
    "당신은 APMP(Association of Proposal Management Professionals) 인증 레드팀 검토자입니다. "
    "정부 제안서를 심사위원(의사결정자)의 관점에서 APMP 기준으로 엄격하게 평가합니다."
)

_DEFAULT_APMP_COMPLIANCE = {
    "win_theme_present": False,
    "proof_points_count": 0,
    "has_executive_summary": False,
    "buyer_centric": False,
    "compliance_matrix_complete": True,
}


class LLM3Reviewer:
    """생성된 제안서를 APMP Red Team 기준으로 검토하고 타당성을 분석"""

    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None

        if INSTRUCTOR_AVAILABLE:
            if settings.openai_api_key:
                try:
                    self.openai_client = instructor.from_openai(
                        OpenAI(api_key=settings.openai_api_key)
                    )
                except Exception as exc:
                    logger.warning("LLM3Reviewer OpenAI 클라이언트 초기화 실패: %s", exc)
            if settings.anthropic_api_key:
                try:
                    self.anthropic_client = instructor.from_anthropic(
                        Anthropic(api_key=settings.anthropic_api_key)
                    )
                except Exception as exc:
                    logger.warning("LLM3Reviewer Anthropic 클라이언트 초기화 실패: %s", exc)
        else:
            if OpenAI and settings.openai_api_key:
                try:
                    self.openai_client = OpenAI(api_key=settings.openai_api_key)
                except Exception as exc:
                    logger.warning("LLM3Reviewer OpenAI 클라이언트 초기화 실패 (instructor 없음): %s", exc)
            if Anthropic and settings.anthropic_api_key:
                try:
                    self.anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
                except Exception as exc:
                    logger.warning("LLM3Reviewer Anthropic 클라이언트 초기화 실패 (instructor 없음): %s", exc)

    def _default_review(self) -> ProposalReview:
        return ProposalReview(
            validity_score=0.70,
            strengths=["논리적 구조", "실현 가능성 고려", "명확한 목표"],
            weaknesses=["세부 운영 계획 미흡", "예산 검토 필요"],
            revision_suggestions=["관련 법령을 명시적으로 추가", "시행 계획 상세화", "부작용 분석 강화"],
            needs_revision=True,
            apmp_compliance=_DEFAULT_APMP_COMPLIANCE,
            proof_point_score=0.5,
            buyer_centric_score=0.5,
        )

    def review(self, proposal: PolicyProposal) -> ProposalReview:
        """제안서 APMP Red Team 검토 및 타당성 분석"""
        proof_str = ", ".join(proposal.proof_points or []) or "없음"
        prompt = f"""다음 정책 제안서를 APMP Red Team 기준으로 검토하세요.

[제안서]
제목: {proposal.title}
핵심 메시지(Win Theme): {proposal.win_theme or "없음"}
의사결정자 요약: {proposal.executive_summary or "없음"}
배경: {proposal.background}
주요내용: {proposal.core_requests}
기대효과: {proposal.expected_effects}
근거 데이터: {proof_str}
담당부처: {proposal.responsible_dept}

[APMP Red Team 체크리스트]
1. Win Theme 명확성: 단일하고 설득력 있는 핵심 메시지가 있는가?
2. 증거 기반(Proof Points): 모든 주장이 수치/통계/사례로 뒷받침되는가?
3. 독자 중심 언어(Buyer-Centric): "우리" 아닌 "시민/의사결정자" 중심으로 작성되었는가?
4. Executive Summary 품질: 의사결정자가 30초 내 핵심을 파악할 수 있는가?
5. 준수 매트릭스: 제목/배경/요청/효과/법령 5개 필수 항목이 모두 충실한가?

[출력 필드]
validity_score: 0.0~1.0 (APMP 기준 전체 점수. 5개 체크리스트 평균)
strengths: APMP 관점의 장점 3가지 목록
weaknesses: 구체적 단점 2-3가지 (예: "Win Theme이 불명확함", "수치 출처 미명시")
revision_suggestions: APMP 기준 구체적 수정 지시 2-3가지
needs_revision: APMP 기준 70점(0.70) 미만 시 true
apmp_compliance: {{"win_theme_present": bool, "proof_points_count": int, "has_executive_summary": bool, "buyer_centric": bool, "compliance_matrix_complete": bool}}
proof_point_score: 0.0~1.0 (증거 충실도)
buyer_centric_score: 0.0~1.0 (독자 중심 언어 점수)"""

        if self.openai_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.openai_client.chat.completions.create(
                        model=settings.openai_model_name,
                        messages=[
                            {"role": "system", "content": _REVIEW_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        response_model=ProposalReview,
                        max_tokens=1024,
                        temperature=0.3,
                    )
                else:
                    return self._openai_review_fallback(prompt)
            except Exception as e:
                logger.warning("LLM3 검토 오류(OpenAI): %s", e)

        if self.anthropic_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=1024,
                        system=_REVIEW_SYSTEM,
                        messages=[{"role": "user", "content": prompt}],
                        response_model=ProposalReview,
                    )
                else:
                    response = self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=1024,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return self._parse_review(response.content[0].text)
            except Exception as e:
                logger.warning("LLM3 검토 오류(Anthropic): %s", e)

        return self._default_review()

    def _openai_review_fallback(self, prompt: str) -> ProposalReview:
        response = self.openai_client.chat.completions.create(
            model=settings.openai_model_name,
            messages=[
                {"role": "system", "content": _REVIEW_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.3,
        )
        return self._parse_review(response.choices[0].message.content)

    def _parse_review(self, text: str) -> ProposalReview:
        result = {
            "validity_score": 0.7,
            "strengths": [],
            "weaknesses": [],
            "revision_suggestions": [],
            "needs_revision": True,
            "apmp_compliance": _DEFAULT_APMP_COMPLIANCE,
            "proof_point_score": 0.5,
            "buyer_centric_score": 0.5,
        }
        for line in text.split("\n"):
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "validity_score":
                try:
                    result["validity_score"] = float(val)
                except ValueError:
                    pass
            elif key == "strengths":
                result["strengths"] = [i.strip() for i in val.split(",") if i.strip()]
            elif key == "weaknesses":
                result["weaknesses"] = [i.strip() for i in val.split(",") if i.strip()]
            elif key == "revision_suggestions":
                result["revision_suggestions"] = [i.strip() for i in val.split(",") if i.strip()]
            elif key == "needs_revision":
                result["needs_revision"] = val.lower() in ("true", "yes", "예", "y")
            elif key == "proof_point_score":
                try:
                    result["proof_point_score"] = float(val)
                except ValueError:
                    pass
            elif key == "buyer_centric_score":
                try:
                    result["buyer_centric_score"] = float(val)
                except ValueError:
                    pass
        return ProposalReview(**result)
