from app.schemas.proposal import PolicyProposal, ProposalReview
from app.config import settings
import random

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


class LLM3Reviewer:
    """생성된 제안서를 검토하고 타당성을 분석"""

    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None

        if INSTRUCTOR_AVAILABLE:
            if settings.openai_api_key:
                try:
                    self.openai_client = instructor.from_openai(
                        OpenAI(api_key=settings.openai_api_key)
                    )
                except Exception:
                    pass
            if settings.anthropic_api_key:
                try:
                    self.anthropic_client = instructor.from_anthropic(
                        Anthropic(api_key=settings.anthropic_api_key)
                    )
                except Exception:
                    pass
        else:
            if OpenAI and settings.openai_api_key:
                try:
                    self.openai_client = OpenAI(api_key=settings.openai_api_key)
                except Exception:
                    pass
            if Anthropic and settings.anthropic_api_key:
                try:
                    self.anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
                except Exception:
                    pass

    def _default_review(self) -> ProposalReview:
        return ProposalReview(
            validity_score=round(random.uniform(0.65, 0.85), 2),
            strengths=["논리적 구조", "실현 가능성 고려", "명확한 목표"],
            weaknesses=["세부 운영 계획 미흡", "예산 검토 필요"],
            revision_suggestions=["관련 법령을 명시적으로 추가", "시행 계획 상세화", "부작용 분석 강화"],
            needs_revision=True,
        )

    def review(self, proposal: PolicyProposal) -> ProposalReview:
        """제안서 타당성 검토 및 피드백"""
        prompt = f"""다음 정책 제안서를 전문가 관점에서 검토하세요:

제목: {proposal.title}
배경: {proposal.background}
주요내용: {proposal.core_requests}
기대효과: {proposal.expected_effects}
담당부처: {proposal.responsible_dept}

validity_score: 0.0~1.0 사이 타당성 점수
strengths: 장점 3가지 목록
weaknesses: 단점 2-3가지 목록
revision_suggestions: 개선 제안 2-3가지 목록
needs_revision: 수정 필요 여부(boolean)"""

        if self.openai_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.openai_client.chat.completions.create(
                        model=settings.openai_model_name,
                        messages=[
                            {"role": "system", "content": "당신은 정책 제안서 검토 및 타당성 평가 전문가입니다."},
                            {"role": "user", "content": prompt},
                        ],
                        response_model=ProposalReview,
                        max_tokens=1024,
                        temperature=0.4,
                    )
                else:
                    return self._openai_review_fallback(prompt)
            except Exception as e:
                print(f"LLM3 검토 오류(OpenAI): {e}")

        if self.anthropic_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=1024,
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
                print(f"LLM3 검토 오류(Anthropic): {e}")

        return self._default_review()

    def _openai_review_fallback(self, prompt: str) -> ProposalReview:
        response = self.openai_client.chat.completions.create(
            model=settings.openai_model_name,
            messages=[
                {"role": "system", "content": "당신은 정책 제안서 검토 및 타당성 평가 전문가입니다."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.4,
        )
        return self._parse_review(response.choices[0].message.content)

    def _parse_review(self, text: str) -> ProposalReview:
        result = {
            "validity_score": 0.7,
            "strengths": [],
            "weaknesses": [],
            "revision_suggestions": [],
            "needs_revision": True,
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
        return ProposalReview(**result)
