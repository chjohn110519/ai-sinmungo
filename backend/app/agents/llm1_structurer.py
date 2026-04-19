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
        )

    def _get_default_proposal(self, user_input: str, responsible_dept: str) -> PolicyProposal:
        return PolicyProposal(
            title="제안 법안",
            background=user_input,
            core_requests="개선 요청",
            expected_effects="정책 개선 및 국민 편의 증진",
            responsible_dept=responsible_dept,
            related_laws=[],
        )

    def structure(self, user_input: str, classification: str, responsible_dept: str) -> StructuredProblem:
        """사용자 입력을 구조화된 문제로 변환"""
        prompt = f"""다음 {classification} 내용을 분석하여 핵심 문제를 구조화하세요.

입력: {user_input}

cause 필드에는 문제의 근본 원인을,
affected_subjects에는 영향받는 대상 그룹을,
resolution_direction에는 해결 방향을,
keywords에는 관련 핵심 키워드 목록을 작성하세요."""

        if self.openai_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.openai_client.chat.completions.create(
                        model=settings.openai_model_name,
                        messages=[
                            {"role": "system", "content": "당신은 정부 정책 제안서 작성 전문가입니다."},
                            {"role": "user", "content": prompt},
                        ],
                        response_model=StructuredProblem,
                        max_tokens=512,
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
                        max_tokens=512,
                        messages=[{"role": "user", "content": prompt}],
                        response_model=StructuredProblem,
                    )
                else:
                    response = self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=512,
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
                {"role": "system", "content": "당신은 정부 정책 제안서 작성 전문가입니다."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=512,
            temperature=0.3,
        )
        return self._parse_structured_problem(response.choices[0].message.content, user_input)

    def _parse_structured_problem(self, text: str, user_input: str) -> StructuredProblem:
        result = {
            "cause": user_input,
            "affected_subjects": "일반국민",
            "resolution_direction": "개선 필요",
            "keywords": ["민원", "정책", "제안"],
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
        return StructuredProblem(**result)

    def generate_proposal(
        self, user_input: str, structured_problem: StructuredProblem, responsible_dept: str
    ) -> PolicyProposal:
        """구조화된 문제에서 정책 제안서 생성"""
        prompt = f"""다음 정보를 바탕으로 법안 형식의 정책 제안서를 작성하세요:

배경: {user_input}
원인: {structured_problem.cause}
영향받는 대상: {structured_problem.affected_subjects}
해결 방향: {structured_problem.resolution_direction}
담당 부처: {responsible_dept}

title에는 법안명(예: ○○법 제정안)을,
background에는 제안이유(1-2문단)를,
core_requests에는 주요내용(3-4가지 핵심 사항)을,
expected_effects에는 기대효과(3-4가지)를,
related_laws에는 관련 법령 이름 목록을 작성하세요.
responsible_dept는 "{responsible_dept}"로 설정하세요."""

        if self.openai_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.openai_client.chat.completions.create(
                        model=settings.openai_model_name,
                        messages=[
                            {"role": "system", "content": "당신은 대한민국 정책 입법 전문가입니다."},
                            {"role": "user", "content": prompt},
                        ],
                        response_model=PolicyProposal,
                        max_tokens=1024,
                        temperature=0.3,
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
                        max_tokens=1024,
                        messages=[{"role": "user", "content": prompt}],
                        response_model=PolicyProposal,
                    )
                else:
                    response = self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=1024,
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
                {"role": "system", "content": "당신은 대한민국 정책 입법 전문가입니다."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.3,
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
        return PolicyProposal(**result)
