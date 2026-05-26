from app.schemas.proposal import StructuredProblem, PolicyProposal
from app.config import settings

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

_STRUCTURE_SYSTEM = (
    "당신은 정부 정책 제안서 작성 전문가이자 APMP 인증 제안 관리 전문가입니다. "
    "제안서의 핵심 승리 메시지(Win Theme)를 도출하고 의사결정자 중심으로 문제를 구조화합니다."
)

_GENERATE_SYSTEM = (
    "당신은 대한민국 국회 입법조사처 수석 연구원으로, "
    "실제 통과된 법안 수준의 정책 제안서를 APMP 방법론에 따라 작성합니다."
)


class LLM1Structurer:
    """정책 제안 입력을 구조화하고 정책 제안서를 생성하는 LLM 에이전트"""

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

    def _get_default_structured_problem(self, user_input: str) -> StructuredProblem:
        return StructuredProblem(
            cause=user_input,
            affected_subjects="일반국민",
            resolution_direction="개선 필요",
            keywords=["민원", "정책", "제안"],
            win_theme=None,
            discriminators=None,
        )

    def _get_default_proposal(self, user_input: str, responsible_dept: str) -> PolicyProposal:
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

    def structure(self, user_input: str, classification: str, responsible_dept: str) -> StructuredProblem:
        """사용자 입력을 구조화된 문제로 변환 (APMP Win Theme 추출 포함)"""
        prompt = f"""다음 {classification} 내용을 분석하여 핵심 문제를 구조화하세요.

입력: {user_input}

cause 필드: 문제의 근본 원인
affected_subjects 필드: 영향받는 대상 그룹
resolution_direction 필드: 해결 방향
keywords 필드: 관련 핵심 키워드 목록 (3~5개)

win_theme 필드: 이 제안이 반드시 승인되어야 하는 단 하나의 핵심 이유를 1~2문장.
  형식: "○○문제로 인해 [피해 대상]이 [피해 내용]을 겪고 있으므로, [해결책]을 통해 [핵심 이익]을 실현해야 합니다."

discriminators 필드: 이 제안을 차별화하는 핵심 요소 3가지 리스트.
  예: ["긴급성: 연간 ○만명 영향", "선례: ○○국 시행 성공", "법적 공백: 현행 ○○법 미규정"]"""

        if self.openai_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.openai_client.chat.completions.create(
                        model=settings.openai_model_name,
                        messages=[
                            {"role": "system", "content": _STRUCTURE_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        response_model=StructuredProblem,
                        max_tokens=768,
                        temperature=0.3,
                    )
                else:
                    return self._openai_structure_fallback(prompt, user_input)
            except Exception as e:
                print(f"LLM1 구조화 오류(OpenAI): {e}")

        if self.anthropic_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=768,
                        system=_STRUCTURE_SYSTEM,
                        messages=[{"role": "user", "content": prompt}],
                        response_model=StructuredProblem,
                    )
                else:
                    response = self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=768,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return self._parse_structured_problem(response.content[0].text, user_input)
            except Exception as e:
                print(f"LLM1 구조화 오류(Anthropic): {e}")

        return self._get_default_structured_problem(user_input)

    def _openai_structure_fallback(self, prompt: str, user_input: str) -> StructuredProblem:
        response = self.openai_client.chat.completions.create(
            model=settings.openai_model_name,
            messages=[
                {"role": "system", "content": _STRUCTURE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=768,
            temperature=0.3,
        )
        return self._parse_structured_problem(response.choices[0].message.content, user_input)

    def _parse_structured_problem(self, text: str, user_input: str) -> StructuredProblem:
        result = {
            "cause": user_input,
            "affected_subjects": "일반국민",
            "resolution_direction": "개선 필요",
            "keywords": ["민원", "정책", "제안"],
            "win_theme": None,
            "discriminators": None,
        }
        for line in text.split("\n"):
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "cause":
                result["cause"] = val
            elif key == "affected_subjects":
                result["affected_subjects"] = val
            elif key == "resolution_direction":
                result["resolution_direction"] = val
            elif key == "keywords":
                result["keywords"] = [k.strip() for k in val.split(",") if k.strip()]
            elif key == "win_theme":
                result["win_theme"] = val
            elif key == "discriminators":
                result["discriminators"] = [d.strip() for d in val.split(",") if d.strip()]
        return StructuredProblem(**result)

    def generate_proposal(
        self, user_input: str, structured_problem: StructuredProblem, responsible_dept: str
    ) -> PolicyProposal:
        """구조화된 문제에서 APMP 방법론 기반 정책 제안서 생성"""
        discriminators_str = ", ".join(structured_problem.discriminators or []) or "없음"
        prompt = f"""[입력 정보]
민원/제안 내용: {user_input}
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
- 예: "연간 ○만명이 ○○문제로 피해를 입고 있습니다. ○○법 개정을 통해 ○○을 실현하면 ○○의 효과가 기대됩니다."

win_theme: 위 핵심 승리 메시지를 그대로 유지하거나 보다 설득력 있게 개선하여 작성.

proof_points (5개 이상 리스트):
- 각 항목은 반드시 구체적 수치·통계·사례 기반.
- 형식: "○○에 따르면 연간 ○건 발생 (출처: ○○부 통계, ○○년)"
- "상당히 많은", "크게 증가" 같은 막연한 표현 금지. 수치로 대체.

background (500자 이상):
- 현황 및 문제점을 구체적 수치·통계와 함께 서술
- 문제의 심각성과 사회적 파급 효과
- 현행 법령·제도의 한계 및 공백 분석
- 유사 선진국(일본, 독일, 영국 등) 제도 비교 가능시 포함
- 개선이 시급한 이유를 다각도로 논거

core_requests (500자 이상):
- 최소 5개의 구체적 정책 요청 사항
- 각 요청에 대해 "○○법 제○조에 따라..." 형식으로 법적 근거 명시
- 단계별 이행 방안(1단계: 즉시 조치, 2단계: 6개월 내, 3단계: 1년 내) 포함
- 예산 규모나 인원 등 구체적 실행 방안 제시

expected_effects (300자 이상):
- 직접 효과 3가지 이상 (정량적 목표 포함, 예: "연간 피해 건수 30% 감소")
- 간접 효과 2가지 이상 (사회적·경제적 파급효과)
- 수혜 대상별 기대 효과 구분

related_laws: 관련 한국 법령 7개 이상 (실제 법령명)
responsible_dept: "{responsible_dept}"

[필수 작성 원칙 — APMP Buyer-Centric Writing]
- "우리가 제안한다" → "시민은 ○○의 혜택을 받게 됩니다" (독자 중심)
- 모든 수치에 출처 또는 산정 근거를 괄호로 명시
- 의사결정자(장관/위원)가 승인했을 때 얻는 이익 중심으로 서술
- 수동형/관료적 언어 배제"""

        if self.openai_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.openai_client.chat.completions.create(
                        model=settings.openai_model_name,
                        messages=[
                            {"role": "system", "content": _GENERATE_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        response_model=PolicyProposal,
                        max_tokens=3000,
                        temperature=0.4,
                    )
                else:
                    return self._openai_proposal_fallback(prompt, user_input, structured_problem, responsible_dept)
            except Exception as e:
                print(f"LLM1 제안서 생성 오류(OpenAI): {e}")

        if self.anthropic_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=3000,
                        system=_GENERATE_SYSTEM,
                        messages=[{"role": "user", "content": prompt}],
                        response_model=PolicyProposal,
                    )
                else:
                    response = self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=3000,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return self._parse_policy_proposal(
                        response.content[0].text, user_input, structured_problem, responsible_dept
                    )
            except Exception as e:
                print(f"LLM1 제안서 생성 오류(Anthropic): {e}")

        return self._get_default_proposal(user_input, responsible_dept)

    def _openai_proposal_fallback(
        self, prompt: str, user_input: str, structured_problem: StructuredProblem, responsible_dept: str
    ) -> PolicyProposal:
        response = self.openai_client.chat.completions.create(
            model=settings.openai_model_name,
            messages=[
                {"role": "system", "content": _GENERATE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=3000,
            temperature=0.4,
        )
        return self._parse_policy_proposal(
            response.choices[0].message.content, user_input, structured_problem, responsible_dept
        )

    def _parse_policy_proposal(
        self, text: str, user_input: str, structured_problem: StructuredProblem, responsible_dept: str
    ) -> PolicyProposal:
        result = {
            "title": "○○개선안",
            "background": structured_problem.cause,
            "core_requests": structured_problem.resolution_direction,
            "expected_effects": "국민 편의 증진 및 정책 개선",
            "responsible_dept": responsible_dept,
            "related_laws": [],
            "executive_summary": None,
            "win_theme": structured_problem.win_theme,
            "proof_points": None,
        }
        for line in text.split("\n"):
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "title":
                result["title"] = val
            elif key == "background":
                result["background"] = val
            elif key == "core_requests":
                result["core_requests"] = val
            elif key == "expected_effects":
                result["expected_effects"] = val
            elif key == "related_laws":
                result["related_laws"] = [l.strip() for l in val.split(",") if l.strip()]
            elif key == "executive_summary":
                result["executive_summary"] = val
            elif key == "win_theme":
                result["win_theme"] = val
            elif key == "proof_points":
                result["proof_points"] = [p.strip() for p in val.split(",") if p.strip()]
        return PolicyProposal(**result)
