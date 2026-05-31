from app.schemas.proposal import PolicyProposal, ProposalReview
from app.schemas.analysis import VisualAnalysis
from app.ml import get_registry

CLASSIFICATION_DURATION = {"민원": 45, "제안": 120, "청원": 270}


class LLM4Visualizer:
    """LLM3 검토 결과 기반 시각화 데이터 생성.

    - feasibility_score: 휴리스틱 공식 유지 (validity_score × 가중치)
    - pass_probability: ML 모델(KoBERT + LogReg)로 예측,
                        모델 미설치/오류 시 기존 휴리스틱으로 자동 fallback
    - committee_recommendations: 위원회 분류 ML 모델로 추천 리스트 생성,
                                  오류 시 빈 리스트로 fallback
    - expected_duration_days: 휴리스틱 공식 유지 (ML 모델이 예측하지 않는 값)
    """

    def visualize(
        self,
        proposal: PolicyProposal,
        review: ProposalReview,
        similar_cases: list[dict],
        classification: str = "민원",
        cluster_count: int = 0,
    ) -> VisualAnalysis:
        law_count = len(proposal.related_laws)
        # APMP 콘텐츠 품질 시그널 (proof_point_score, buyer_centric_score)
        proof_score = getattr(review, 'proof_point_score', None) or 0.6
        buyer_score = getattr(review, 'buyer_centric_score', None) or 0.6
        apmp_bonus = (proof_score * 0.5 + buyer_score * 0.5)
        feasibility_score = round(
            review.validity_score * 0.70
            + min(law_count / 10.0, 1.0) * 0.20
            + apmp_bonus * 0.10,
            3,
        )

        # ── ML 예측 ──────────────────────────────────────────────────────────
        proposal_text = f"{proposal.background}\n{proposal.core_requests}"
        registry = get_registry()

        # pass_probability + 진행단계: predict_detailed() 우선 호출 (KoBERT 활성화 시)
        stage_predictions: dict | None = None
        detailed = registry.predict_pass_detailed(proposal_text)
        if detailed is not None:
            pass_probability = round(float(detailed["pass_probability"]), 3)
            stage_predictions = {
                "predicted_progress_stage": detailed["predicted_progress_stage"],
                "predicted_proc_result": detailed["predicted_proc_result"],
                "predicted_cmt_result": detailed["predicted_cmt_result"],
                "predicted_law_result": detailed.get("predicted_law_result", ""),
                "top_progress_stages": detailed.get("top_progress_stages", []),
            }
        else:
            # 기존 휴리스틱 fallback (KoBERT 비활성화 또는 오류 시)
            crowd_bonus = min(cluster_count / 1000.0, 0.15) if cluster_count > 0 else 0.0
            pass_probability = round(max(0.30, min(0.95, feasibility_score + crowd_bonus)), 3)

        # committee_recommendations: ML 모델 사용, 오류 시 빈 리스트
        committee_recs = registry.recommend_committees(proposal_text, top_k=5)
        # ─────────────────────────────────────────────────────────────────────

        duration_source = "heuristic"
        predicted_days = registry.predict_approval_duration_days(proposal_text)
        if predicted_days is not None:
            expected_duration_days = max(1, int(round(predicted_days)))
            duration_source = "predicted_date_of_approval"
        else:
            base_days = CLASSIFICATION_DURATION.get(classification, 120)
            dept = proposal.responsible_dept.lower()
            multiplier = 1.2 if any(kw in dept for kw in ("국토", "건설", "교통", "인프라")) else 1.0
            expected_duration_days = int(base_days * multiplier)

        review_days = int(expected_duration_days * 0.20)
        legislation_days = int(expected_duration_days * 0.50)
        execution_days = expected_duration_days - review_days - legislation_days

        # 소관 위원회 → 담당부서 일치: 위원회 분류기 최상위 결과로 responsible_dept 오버라이드
        top_committee_name = committee_recs[0]["committee"] if committee_recs else None

        chart_data = {
            "timeline": [
                {"name": "검토", "value": review_days},
                {"name": "입법", "value": legislation_days},
                {"name": "집행", "value": execution_days},
            ],
            "feasibility": feasibility_score,
            "pass_probability": pass_probability,
            "committee_recommendations": [           # 프론트 키명에 맞게 정규화 (committee, relevance)
                {"committee": r["committee"], "relevance": r["confidence"]}
                for r in committee_recs
            ],
            "stage_predictions": stage_predictions,  # KoBERT 활성화 시 진행단계 예측
            "top_committee": top_committee_name,      # 소관 위원회 최상위 추천
            "duration_prediction_source": duration_source,
        }

        formatted_cases = []
        for case in similar_cases[:3]:
            formatted_cases.append({
                "case_id": case.get("case_id", case.get("doc_id", "")),
                "similarity": round(case.get("similarity", case.get("relevance", 0.5)), 3),
                "title": case.get("title", "유사 사례"),
            })
        # 유사 사례가 없으면 빈 리스트 반환 — 가짜 데이터를 주입하지 않음

        return VisualAnalysis(
            similar_cases=formatted_cases,
            feasibility_score=feasibility_score,
            pass_probability=pass_probability,
            expected_duration_days=expected_duration_days,
            chart_data=chart_data,
            committee_recommendations=committee_recs if committee_recs else None,
        )
