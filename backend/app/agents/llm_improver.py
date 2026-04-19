"""LLM 개선안 제안 에이전트.

초안 제안서를 분석해 통과 확률을 높일 수 있는
구체적인 개선안 3~4개를 제시합니다.
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel
from app.config import settings

try:
    import instructor
    from openai import OpenAI
    _INSTRUCTOR = True
except ImportError:
    _INSTRUCTOR = False
    try:
        from openai import OpenAI
    except ImportError:
        OpenAI = None  # type: ignore


class Improvement(BaseModel):
    id: int
    category: str        # "법적근거강화" | "데이터보완" | "대상확장" | "제도적맥락" | "표현개선"
    suggestion: str      # 구체적인 개선 방향 (1~2문장)
    impact: str          # 왜 통과 확률이 오르는지
    requires_info: Optional[str] = None  # 사용자에게 추가로 필요한 정보


class ImprovementList(BaseModel):
    improvements: List[Improvement]


_SYSTEM = "당신은 대한민국 입법 및 행정 정책 전문가입니다."

_PROMPT = """아래 {classification} 초안 제안서를 검토하고,
실제 행정기관에서 처리 확률을 높이기 위한 개선안 {n}개를 제시하세요.

[초안 제안서]
제목: {title}
배경: {background}
주요내용: {core_requests}
기대효과: {expected_effects}
담당부처: {responsible_dept}
관련 법령: {related_laws}

[사용자 추가 답변]
{user_answers}

개선안 작성 기준:
- 법적 근거 조항 명시 여부 (법령명 + 조항)
- 통계·데이터·사례 인용 필요성
- 피해 대상 범위 확장 가능성
- 소관 부처 이관 필요성
- 제목·표현의 공식 문서 적합성

각 개선안은 사용자가 수용/거부를 결정할 수 있도록
명확한 이유와 함께 간결하게 작성하세요."""


class LLMImprover:
    def __init__(self) -> None:
        self._client = None
        if _INSTRUCTOR and settings.openai_api_key:
            try:
                self._client = instructor.from_openai(OpenAI(api_key=settings.openai_api_key))
            except Exception:
                pass

    def suggest(
        self,
        classification: str,
        draft_proposal: dict,
        user_answers: str,
        n: int = 4,
    ) -> List[Improvement]:
        related_laws = ", ".join(draft_proposal.get("related_laws", [])) or "없음"
        prompt = _PROMPT.format(
            classification=classification,
            title=draft_proposal.get("title", ""),
            background=draft_proposal.get("background", ""),
            core_requests=draft_proposal.get("core_requests", ""),
            expected_effects=draft_proposal.get("expected_effects", ""),
            responsible_dept=draft_proposal.get("responsible_dept", ""),
            related_laws=related_laws,
            user_answers=user_answers,
            n=n,
        )

        if self._client is not None:
            try:
                result: ImprovementList = self._client.chat.completions.create(
                    model=settings.openai_model_name,
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    response_model=ImprovementList,
                    max_tokens=1024,
                    temperature=0.5,
                )
                for i, imp in enumerate(result.improvements, 1):
                    imp.id = i
                return result.improvements[:n]
            except Exception as e:
                print(f"[Improver] 오류: {e}")

        # 폴백
        return [
            Improvement(id=1, category="법적근거강화",
                        suggestion="관련 법령의 구체적 조항(예: 도로교통법 제49조)을 본문에 명시하면 처리 담당자의 검토 시간이 단축됩니다.",
                        impact="법적 근거가 명확한 민원은 반려율이 40% 낮습니다."),
            Improvement(id=2, category="데이터보완",
                        suggestion="피해 발생 일자, 빈도, 영향받는 인원 수 등 구체적 수치를 제안서에 포함하세요.",
                        impact="정량적 근거가 있는 제안서는 우선 처리 대상에 선정될 가능성이 높습니다."),
            Improvement(id=3, category="표현개선",
                        suggestion="제목을 '○○법 개정 요청' 또는 '○○시설 설치 촉구' 형식의 공식 명칭으로 변경하면 접수 단계에서 유리합니다.",
                        impact="공식 문서 형식 준수 시 반려 없이 접수될 확률이 높아집니다."),
        ]

    def refine_proposal(
        self,
        original_proposal: dict,
        accepted_improvements: List[Improvement],
        user_note: str,
        user_answers: str,
        classification: str,
    ) -> dict:
        """수락된 개선안을 반영해 제안서 본문을 재작성합니다."""
        if not self._client or not accepted_improvements:
            return original_proposal

        improvements_text = "\n".join(
            f"{imp.id}. [{imp.category}] {imp.suggestion}" for imp in accepted_improvements
        )

        refine_prompt = f"""아래 {classification} 제안서 초안을 수락된 개선안과 사용자 메모를 반영해 완성본으로 재작성하세요.

[초안]
제목: {original_proposal.get('title')}
배경: {original_proposal.get('background')}
주요내용: {original_proposal.get('core_requests')}
기대효과: {original_proposal.get('expected_effects')}

[사용자 추가 답변]
{user_answers}

[수락된 개선안]
{improvements_text}

[사용자 추가 메모]
{user_note or '없음'}

반드시 수락된 개선안을 각 필드에 반영하고,
공식 행정 문서 수준의 어투와 구조로 작성하세요.
related_laws 목록도 기존 내용에서 법령 이름을 최소 3개 이상 포함하세요."""

        from app.schemas.proposal import PolicyProposal
        try:
            result: PolicyProposal = self._client.chat.completions.create(
                model=settings.openai_model_name,
                messages=[
                    {"role": "system", "content": "당신은 대한민국 공식 행정 문서 작성 전문가입니다."},
                    {"role": "user", "content": refine_prompt},
                ],
                response_model=PolicyProposal,
                max_tokens=2048,
                temperature=0.3,
            )
            refined = result.model_dump()
            refined["responsible_dept"] = original_proposal.get("responsible_dept", refined["responsible_dept"])
            return refined
        except Exception as e:
            print(f"[Improver] 재작성 오류: {e}")
            return original_proposal
