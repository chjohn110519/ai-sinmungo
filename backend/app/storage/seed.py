"""DB 초기 예시 데이터. ProposalCluster가 비어 있을 때만 삽입."""

import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.storage.models import ProposalCluster, StructuredProposal, AnalysisResult


_SEED_CLUSTERS = [
    {
        "topic": "주거",
        "keywords": ["청년", "주거", "전세대출", "LH", "임대"],
        "responsible_dept": "국토교통부",
        "classification": "제안",
        "count": 127,
        "threshold": 50,
        "triggered": True,
        "days_ago": 14,
    },
    {
        "topic": "교통",
        "keywords": ["대중교통", "지하철", "버스", "교통비", "요금"],
        "responsible_dept": "국토교통부",
        "classification": "제안",
        "count": 89,
        "threshold": 100,
        "triggered": False,
        "days_ago": 10,
    },
    {
        "topic": "환경",
        "keywords": ["미세먼지", "공기질", "환경", "차량", "배출가스"],
        "responsible_dept": "환경부",
        "classification": "청원",
        "count": 74,
        "threshold": 100,
        "triggered": False,
        "days_ago": 8,
    },
    {
        "topic": "경제",
        "keywords": ["소상공인", "자영업", "세금", "경제", "지원"],
        "responsible_dept": "중소벤처기업부",
        "classification": "제안",
        "count": 63,
        "threshold": 100,
        "triggered": False,
        "days_ago": 7,
    },
    {
        "topic": "교육",
        "keywords": ["급식", "학교", "식재료", "교육", "영양"],
        "responsible_dept": "교육부",
        "classification": "제안",
        "count": 45,
        "threshold": 100,
        "triggered": False,
        "days_ago": 5,
    },
    {
        "topic": "복지",
        "keywords": ["노인", "의료비", "요양", "복지", "건강보험"],
        "responsible_dept": "보건복지부",
        "classification": "청원",
        "count": 38,
        "threshold": 100,
        "triggered": False,
        "days_ago": 4,
    },
    {
        "topic": "노동",
        "keywords": ["최저임금", "노동", "임금", "근로", "청년"],
        "responsible_dept": "고용노동부",
        "classification": "제안",
        "count": 31,
        "threshold": 100,
        "triggered": False,
        "days_ago": 3,
    },
    {
        "topic": "디지털",
        "keywords": ["AI", "디지털", "행정", "전자정부", "민원"],
        "responsible_dept": "행정안전부",
        "classification": "제안",
        "count": 22,
        "threshold": 100,
        "triggered": False,
        "days_ago": 2,
    },
]

_TRIGGERED_PROPOSAL = {
    "title": "청년 주거 안정을 위한 전세대출 한도 상향 및 LH 공공임대 공급 확대 제안",
    "background": (
        "최근 수도권을 중심으로 전세가격이 급등하면서 청년층의 주거 불안이 심화되고 있습니다. "
        "현행 청년 전세대출 한도(최대 1억원)는 평균 전세가 대비 턱없이 부족하며, "
        "LH 공공임대 공급 물량도 수요에 비해 현저히 부족한 실정입니다. "
        "127명의 시민이 같은 방향의 의견을 제출하며 정책 개선을 촉구하고 있습니다."
    ),
    "core_requests": (
        "1. 청년 전세대출 한도를 현행 1억원에서 2억원으로 상향 조정\n"
        "2. LH 공공임대 청년 쿼터를 현행 20%에서 35%로 확대\n"
        "3. 역세권 청년주택 공급 목표 연 3만호 달성을 위한 인허가 절차 간소화\n"
        "4. 월세 세액공제 대상 확대 및 공제율 상향(현행 10~12% → 15~17%)"
    ),
    "expected_effects": (
        "· 청년층 주거비 부담 연평균 12~18% 경감 예상\n"
        "· 수도권 집중화 완화 및 지방 이전 청년 인구 유입 촉진\n"
        "· 1~2인 가구 주거 안정으로 혼인율·출생률 개선 기여\n"
        "· 공공임대 확대에 따른 건설경기 부양 효과"
    ),
    "responsible_dept": "국토교통부",
    "related_laws": ["주택법", "한국토지주택공사법", "민간임대주택에 관한 특별법", "조세특례제한법"],
    "pass_probability": 0.72,
    "expected_duration_days": 180,
    "feasibility_score": 0.68,
}


def seed_if_empty(db: DBSession) -> None:
    """ProposalCluster 테이블이 비어 있을 때만 예시 데이터를 삽입."""
    if db.query(ProposalCluster).count() > 0:
        return

    now = datetime.utcnow()
    triggered_cluster_id = str(uuid.uuid4())

    # 트리거된 클러스터의 제안서를 먼저 저장 (FK 제약 때문)
    proposal_id = str(uuid.uuid4())
    db_proposal = StructuredProposal(
        proposal_id=proposal_id,
        session_id=f"seed-{triggered_cluster_id}",
        title=_TRIGGERED_PROPOSAL["title"],
        background=_TRIGGERED_PROPOSAL["background"],
        core_requests=_TRIGGERED_PROPOSAL["core_requests"],
        expected_effects=_TRIGGERED_PROPOSAL["expected_effects"],
        responsible_dept=_TRIGGERED_PROPOSAL["responsible_dept"],
        related_laws=_TRIGGERED_PROPOSAL["related_laws"],
        created_at=now - timedelta(days=14),
    )
    db.add(db_proposal)
    db.flush()

    db.add(AnalysisResult(
        analysis_id=str(uuid.uuid4()),
        proposal_id=proposal_id,
        similar_cases=[],
        pass_probability=_TRIGGERED_PROPOSAL["pass_probability"],
        expected_duration_days=_TRIGGERED_PROPOSAL["expected_duration_days"],
        feasibility_score=_TRIGGERED_PROPOSAL["feasibility_score"],
        visualization_data={},
        created_at=now - timedelta(days=14),
    ))

    # 클러스터 삽입
    for i, data in enumerate(_SEED_CLUSTERS):
        cluster_id = triggered_cluster_id if i == 0 else str(uuid.uuid4())
        created = now - timedelta(days=data["days_ago"])
        cluster = ProposalCluster(
            cluster_id=cluster_id,
            topic=data["topic"],
            keywords=data["keywords"],
            responsible_dept=data["responsible_dept"],
            classification=data["classification"],
            count=data["count"],
            threshold=data["threshold"],
            triggered=data["triggered"],
            proposal_id=proposal_id if i == 0 else None,
            created_at=created,
            updated_at=created,
        )
        db.add(cluster)

    db.commit()
