"""LLM 질문 생성 에이전트.

민원/제안/청원 내용을 분석해 그 내용에만 맞는 맞춤형 명확화 질문을 생성합니다.
각 질문에는 답변 예시 힌트가 함께 제공됩니다.
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


class ClarifyingQuestion(BaseModel):
    question: str  # 질문 내용 (50자 이내)
    hint: str      # 답변 유도 힌트 (예: "예: 2023년 3월부터, 주 3회 이상")


class ClarifyingQuestions(BaseModel):
    questions: List[ClarifyingQuestion]


_SYSTEM = "당신은 대한민국 국민신문고 전문 접수 담당관입니다."

_PROMPT = """당신은 대한민국 국민신문고 전문 접수 담당관입니다.
사용자가 다음 {classification}을 접수했습니다.

[접수 내용]
{message}

위 {classification}을 꼼꼼히 읽고, 행정기관이 실제로 처리하기 위해 반드시 필요한데
아직 언급되지 않은 정보를 파악하세요.

질문 생성 규칙:
- 이미 접수 내용에 언급된 정보(장소, 날짜, 인원 등)는 절대 다시 묻지 마세요
- 이 민원의 특수한 상황에만 해당하는 구체적인 질문을 하세요
- 일반적이거나 모든 민원에 공통된 질문은 피하세요
- 각 질문은 50자 이내의 명확한 한 문장으로 작성하세요
- hint는 사용자가 쉽게 답변할 수 있도록 구체적 예시를 포함하세요 (예: "예: ○○동 ○○로 3구간, 버스정류장 앞")

질문 {n}개를 생성하세요."""


class LLMQuestioner:
    def __init__(self) -> None:
        self._client = None
        api_key = (settings.openai_api_key or "").strip()
        if _INSTRUCTOR and api_key:
            try:
                self._client = instructor.from_openai(OpenAI(api_key=api_key))
            except Exception:
                pass
        elif not _INSTRUCTOR and OpenAI and api_key:
            try:
                self._raw = OpenAI(api_key=api_key)
            except Exception:
                pass

    def generate(self, message: str, classification: str, n: int = 4) -> List[dict]:
        """민원 내용 기반 맞춤형 질문 생성.

        Returns:
            List[{"question": str, "hint": str}]
        """
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
                    max_tokens=800,
                    temperature=0.4,
                )
                return [
                    {"question": q.question, "hint": q.hint}
                    for q in result.questions[:n]
                ]
            except Exception as e:
                print(f"[Questioner] 오류: {e}")

        # 폴백: 분류별 기본 질문 (hint 포함)
        defaults = {
            "민원": [
                {"question": "구체적으로 어느 지역/기관에서 발생한 문제인가요?", "hint": "예: 서울 강남구 ○○동 ○○로, ○○구청 민원실"},
                {"question": "이 문제로 피해를 입는 분들이 몇 명 정도인가요?", "hint": "예: 인근 주민 약 200명, 통학 학생 50명"},
                {"question": "해당 문제가 처음 발생한 시기는 언제인가요?", "hint": "예: 2022년 10월경, 공사 시작 이후"},
                {"question": "이전에 관련 기관에 민원을 넣어보신 적이 있나요?", "hint": "예: 작년에 구청에 전화했으나 '검토 중'이라는 답변만 받음"},
            ],
            "제안": [
                {"question": "이 제안이 필요한 배경이 된 구체적인 사례가 있나요?", "hint": "예: 작년에 ○○사고가 발생했는데 해당 제도가 있었다면 예방 가능했음"},
                {"question": "제안이 시행되면 혜택을 받을 대상이 누구인가요?", "hint": "예: 65세 이상 노인 인구 약 300만 명, 저소득 1~2인 가구"},
                {"question": "유사한 제도가 다른 지역이나 나라에 있나요?", "hint": "예: 일본 ○○현에서 2019년 도입, 독일 ○○법에 유사 조항 있음"},
                {"question": "예상 소요 예산 규모가 어느 정도일까요?", "hint": "예: 연간 약 5억 원, 초기 시스템 구축비 10억 원 예상"},
            ],
            "청원": [
                {"question": "현행 법률·제도의 어떤 부분이 문제라고 보시나요?", "hint": "예: ○○법 제3조 2항이 ○○권을 침해함"},
                {"question": "청원이 수용되지 않을 경우 예상되는 피해는?", "hint": "예: 매년 ○○명이 피해를 입고, 연간 ○억 원의 사회적 비용 발생"},
                {"question": "청원의 핵심 요구 사항을 한 문장으로 표현하면?", "hint": "예: ○○법 폐지 또는 제○조 개정을 통한 ○○권 보장"},
                {"question": "이 청원에 공감하는 시민이 얼마나 있을 것 같나요?", "hint": "예: 온라인 서명 2만 명 달성, 관련 커뮤니티 회원 5만 명"},
            ],
        }
        return defaults.get(classification, defaults["민원"])
