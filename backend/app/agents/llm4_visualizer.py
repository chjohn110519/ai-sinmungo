from app.schemas.proposal import PolicyProposal, ProposalReview
from app.schemas.analysis import VisualAnalysis

CLASSIFICATION_DURATION = {"민원": 45, "제안": 120, "청원": 270}


class LLM4Visualizer:
    """LLM3 검토 결과 기반 휴리스틱 분석 및 시각화 데이터 생성"""

    def visualize(
        self,
        proposal: PolicyProposal,
        review: ProposalReview,
        similar_cases: list[dict],
        classification: str = "민원",
    ) -> VisualAnalysis:
        law_count = len(proposal.related_laws)
        feasibility_score = round(
            review.validity_score * 0.8 + min(law_count / 10.0, 1.0) * 0.2,
            3,
        )
        pass_probability = round(max(0.30, min(0.95, feasibility_score)), 3)

        base_days = CLASSIFICATION_DURATION.get(classification, 120)
        dept = proposal.responsible_dept.lower()
        multiplier = 1.2 if any(kw in dept for kw in ("국토", "건설", "교통", "인프라")) else 1.0
        expected_duration_days = int(base_days * multiplier)

        review_days = int(expected_duration_days * 0.20)
        legislation_days = int(expected_duration_days * 0.50)
        execution_days = expected_duration_days - review_days - legislation_days

        chart_data = {
            "timeline": [
                {"name": "검토", "value": review_days},
                {"name": "입법", "value": legislation_days},
                {"name": "집행", "value": execution_days},
            ],
            "feasibility": feasibility_score,
            "pass_probability": pass_probability,
        }

        formatted_cases = []
        for case in similar_cases[:3]:
            formatted_cases.append({
                "case_id": case.get("case_id", case.get("doc_id", "")),
                "similarity": round(case.get("similarity", case.get("relevance", 0.5)), 3),
                "title": case.get("title", "유사 사례"),
            })

        if not formatted_cases:
            formatted_cases = [{"case_id": "sample-001", "similarity": 0.65, "title": "유사 민원 사례"}]

        return VisualAnalysis(
            similar_cases=formatted_cases,
            feasibility_score=feasibility_score,
            pass_probability=pass_probability,
            expected_duration_days=expected_duration_days,
            chart_data=chart_data,
        )
