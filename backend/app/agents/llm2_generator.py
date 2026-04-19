from app.schemas.proposal import PolicyProposal, StructuredProblem


class LLM2Generator:
    """구조화된 문제를 법안 형식 제안서로 변환"""

    def generate(self, structured_problem: StructuredProblem) -> PolicyProposal:
        return PolicyProposal(
            title="JUT_AI신문고 제안서 예시 제목",
            background=structured_problem.cause,
            core_requests="핵심 요청 사항을 명확히 기술합니다.",
            expected_effects="예상 효과와 공공 이익을 설명합니다.",
            responsible_dept="행정안전부",
            related_laws=["제목 없음"],
        )
