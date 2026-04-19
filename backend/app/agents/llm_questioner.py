"""LLM 질문 생성 에이전트.

분류된 민원/제안/청원에 대해 제안서 품질을 높이기 위한
명확화 질문 3~5개를 생성합니다.
"""

from __future__ import annotations
from typing import List
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


class ClarifyingQuestions(BaseModel):
    questions: List[str]


_SYSTEM = "당신은 대한민국 국민신문고 전문 접수 담당관입니다."

_PROMPT = """당신은 대한민국 국민신문고 전문 접수 담당관입니다.
사용자가 다음 {classification}을 접수했습니다.

[접수 내용]
{message}

이 {classification}을 실제 행정기관에서 처리될 수 있는 상세한 공식 제안서로 만들기 위해,
제안서 품질을 크게 높이는 핵심 정보를 수집해야 합니다.
아래 기준으로 질문 {n}개를 생성하세요.

질문 작성 기준 (중요도 순):
1. 구체적 사실관계: 발생 장소·일시·빈도, 피해 규모(인원수, 면적, 금액 등)
2. 현황 및 심각성: 문제가 얼마나 오래됐는지, 얼마나 자주 발생하는지
3. 기존 시도: 이미 관련 기관에 문의하거나 민원을 넣은 적이 있는지, 답변은?
4. 요청 방향: 구체적으로 어떤 조치나 법령 개정을 원하는지
5. 영향 범위: 나만의 문제인지, 지역사회/특정 집단 전체의 문제인지

각 질문은 40자 이내의 명확하고 구체적인 한 문장으로 작성하세요.
사용자가 답변하기 쉽도록 실용적이고 직접적으로 질문하세요."""


class LLMQuestioner:
    def __init__(self) -> None:
        self._client = None
        if _INSTRUCTOR and settings.openai_api_key:
            try:
                self._client = instructor.from_openai(OpenAI(api_key=settings.openai_api_key))
            except Exception:
                pass
        elif not _INSTRUCTOR and OpenAI and settings.openai_api_key:
            try:
                self._raw = OpenAI(api_key=settings.openai_api_key)
            except Exception:
                pass

    def generate(self, message: str, classification: str, n: int = 4) -> List[str]:
        prompt = _PROMPT.format(classification=classification, message=message, n=n)

        if self._client is not None:
            try:
                result: ClarifyingQuestions = self._client.chat.completions.create(
                    model=settings.openai_model_name,
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    response_model=ClarifyingQuestions,
                    max_tokens=512,
                    temperature=0.4,
                )
                return result.questions[:n]
            except Exception as e:
                print(f"[Questioner] 오류: {e}")

        # 폴백: 분류별 기본 질문
        defaults = {
            "민원": [
                "구체적으로 어느 지역/기관에서 발생한 문제인가요?",
                "이 문제로 인해 불편을 겪는 분들이 몇 명 정도 되나요?",
                "해당 문제가 처음 발생한 시기는 언제인가요?",
                "이전에 관련 기관에 민원을 넣어보신 적이 있나요?",
            ],
            "제안": [
                "이 제안이 필요한 배경이 된 구체적인 사례가 있나요?",
                "제안이 시행되면 혜택을 받을 대상이 누구인가요?",
                "유사한 제도가 다른 지역/국가에 있나요?",
                "예상 소요 예산 규모가 어느 정도일까요?",
            ],
            "청원": [
                "이 청원의 핵심 요구 사항을 한 문장으로 표현하면?",
                "현행 법률/제도의 어떤 부분이 문제라고 보시나요?",
                "청원에 동의하는 시민이 얼마나 있나요?",
                "청원이 수용되지 않을 경우 예상되는 피해는?",
            ],
        }
        return defaults.get(classification, defaults["민원"])
