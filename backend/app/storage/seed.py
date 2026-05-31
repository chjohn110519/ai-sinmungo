"""DB 초기 예시 데이터. ProposalCluster가 비어 있을 때만 삽입."""

import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from app.storage.models import ProposalCluster, StructuredProposal, AnalysisResult, Session as SessionModel


_SEED_CLUSTERS = [
    {
        "topic": "주거",
        "keywords": ["청년", "주거", "전세대출", "LH", "임대"],
        "responsible_dept": "국토교통위원회",
        "classification": "제안",
        "count": 127,
        "threshold": 100,
        "triggered": True,
        "days_ago": 14,
        "opinions": [
            ("청년 전세대출 한도를 현실화해야 합니다. 현재 1억 원 한도로는 수도권 전세를 구할 수 없습니다.", "제안"),
            ("LH 공공임대주택 청년 쿼터를 현행 20%에서 35%로 확대해 주세요.", "제안"),
            ("전세 사기 피해 예방을 위한 임차인 보호 제도를 강화해야 합니다.", "제안"),
            ("역세권 청년주택 공급 목표를 연 3만 호로 늘려야 합니다.", "제안"),
            ("월세 세액공제율을 현행 10%에서 20%로 상향해 주세요.", "제안"),
            ("청년 1인 가구를 위한 소형 공공임대 공급을 확대해야 합니다.", "제안"),
            ("전세대출 이자 지원을 소득 하위 50%까지 확대해 주세요.", "제안"),
            ("빈집을 활용한 청년 임시주거 지원 제도를 도입해야 합니다.", "제안"),
            ("임대차 3법을 보완하여 세입자 권리를 더욱 강화해야 합니다.", "제안"),
            ("지방 청년 정착을 위한 공공임대주택 우선 배정이 필요합니다.", "제안"),
            ("반지하·고시원 청년을 위한 이주 지원 제도를 만들어야 합니다.", "제안"),
            ("청년 주거급여 지원 기준을 완화하고 지원 금액을 현실화해 주세요.", "제안"),
            ("주택도시기금 청년 대출 한도를 전세가 상승분에 맞게 조정해야 합니다.", "제안"),
            ("공공 매입임대주택 물량을 연간 5만 호 이상으로 확대해야 합니다.", "제안"),
            ("청년 주거 안정을 위한 임대료 인상률 상한제 도입이 필요합니다.", "제안"),
            ("사회초년생 보증금 대출 이자를 국가가 전액 지원해야 합니다.", "제안"),
            ("전세 보증 보험 가입을 집주인에게 의무화해야 합니다.", "제안"),
            ("청년 우선 분양 물량을 신규 아파트의 30% 이상으로 확대해야 합니다.", "제안"),
            ("주거 취약계층을 위한 긴급 임시 주거 지원 제도가 필요합니다.", "제안"),
            ("전월세 신고제를 전면 확대해 임대차 시장 투명성을 높여야 합니다.", "제안"),
            ("청년 주거 지원 정보를 원스톱으로 안내하는 통합 플랫폼을 만들어야 합니다.", "제안"),
            ("신혼부부 특별 공급 물량을 전체 분양의 20%로 의무화해야 합니다.", "제안"),
            ("주택 임대차 분쟁 조정 기간을 30일 이내로 단축해야 합니다.", "제안"),
        ],
    },
    {
        "topic": "교통",
        "keywords": ["대중교통", "버스", "지하철", "교통비", "요금"],
        "responsible_dept": "국토교통위원회",
        "classification": "제안",
        "count": 91,
        "threshold": 100,
        "triggered": False,
        "days_ago": 10,
        "opinions": [
            ("대중교통 요금 인상 없이 서비스 개선이 먼저입니다. 버스 배차 간격을 줄여주세요.", "제안"),
            ("지하철 노선을 신도시까지 연장해 교통 접근성을 높여야 합니다.", "제안"),
            ("버스·지하철 환승 할인을 확대하고 대중교통 요금 부담을 줄여야 합니다.", "제안"),
            ("심야 버스 노선을 확대해 야간 대중교통 이용 불편을 해소해 주세요.", "제안"),
            ("저상버스 도입을 확대해 교통약자 이동권을 보장해야 합니다.", "제안"),
            ("광역버스 좌석 수를 늘려 출퇴근 시간 혼잡을 해소해 주세요.", "제안"),
            ("자전거 전용 도로를 확충하고 공공 자전거 대여소를 늘려야 합니다.", "제안"),
            ("전기버스 도입 비율을 높여 대중교통 탄소 배출을 줄여야 합니다.", "제안"),
            ("GTX 노선을 확장해 수도권 외곽 주민의 교통 접근성을 높여야 합니다.", "제안"),
            ("버스 도착 정보 시스템을 개선하고 실시간 정보 제공을 강화해야 합니다.", "제안"),
            ("지하철 노인·장애인 할인 혜택을 유지하고 복지 교통카드 지원을 확대해야 합니다.", "제안"),
            ("카풀 및 공유 모빌리티 서비스를 제도화하여 교통비를 절감해야 합니다.", "제안"),
            ("지하철 냉방 서비스 시간을 연장하고 선택적 약냉방 칸을 늘려야 합니다.", "제안"),
            ("버스 정류장에 실시간 도착 정보 디스플레이를 전면 설치해야 합니다.", "제안"),
            ("전동 킥보드 등 개인형 이동장치 안전 규제를 더 강화해야 합니다.", "제안"),
            ("지방 소도시 주민을 위한 수요응답형 대중교통을 확대해야 합니다.", "제안"),
        ],
    },
    {
        "topic": "환경",
        "keywords": ["미세먼지", "공기질", "환경", "배출가스", "탄소"],
        "responsible_dept": "환경노동위원회",
        "classification": "청원",
        "count": 74,
        "threshold": 100,
        "triggered": False,
        "days_ago": 8,
        "opinions": [
            ("미세먼지 저감을 위한 노후 경유차 운행 제한을 강화하는 법 개정을 청원합니다.", "청원"),
            ("산업 시설 배출가스 기준을 대폭 강화하는 대기환경보전법 개정이 시급합니다.", "청원"),
            ("탄소 배출 업체에 대한 과징금을 현실화하는 법 개정을 요구합니다.", "청원"),
            ("플라스틱 일회용품 사용 금지를 확대하는 자원순환법 개정이 필요합니다.", "청원"),
            ("석탄발전소 조기 폐쇄를 의무화하는 특별법 제정을 청원합니다.", "청원"),
            ("탄소세 도입을 통해 기후 변화 대응 재원을 마련해야 합니다.", "청원"),
            ("화학물질 배출 사업장에 대한 실시간 모니터링 의무화 법안이 필요합니다.", "청원"),
            ("재생에너지 의무 사용 비율을 50% 이상으로 높이는 법 개정을 청원합니다.", "청원"),
            ("도시 열섬 현상 완화를 위한 녹지 의무 비율 강화 법안을 요구합니다.", "청원"),
            ("폐기물 불법 투기 처벌을 강화하는 폐기물관리법 개정을 청원합니다.", "청원"),
            ("녹지 조성 의무 비율을 신규 개발 사업에 50% 이상 적용하는 법을 만들어야 합니다.", "청원"),
            ("생태계 보전 구역 훼손 시 원상복구를 의무화하는 환경법 개정을 청원합니다.", "청원"),
            ("환경영향평가 대상을 중소 개발 사업까지 확대하는 법 개정이 필요합니다.", "청원"),
        ],
    },
    {
        "topic": "경제",
        "keywords": ["소상공인", "자영업", "세금", "창업", "지원"],
        "responsible_dept": "기획재정위원회",
        "classification": "제안",
        "count": 63,
        "threshold": 100,
        "triggered": False,
        "days_ago": 7,
        "opinions": [
            ("소상공인 임대료 지원을 제도화하고 세금 부담을 줄여야 합니다.", "제안"),
            ("청년 창업 지원금을 확대하고 초기 3년간 세금 감면을 도입해 주세요.", "제안"),
            ("자영업자 폐업 후 재취업 지원 프로그램을 확대해야 합니다.", "제안"),
            ("소상공인 대출 이자 지원을 현재보다 2배 이상 늘려야 합니다.", "제안"),
            ("배달 플랫폼 수수료를 법적으로 제한해 자영업자 부담을 줄여야 합니다.", "제안"),
            ("지역화폐 사용을 더욱 확대해 소상공인 매출을 늘려야 합니다.", "제안"),
            ("전통 시장 현대화 지원 예산을 대폭 늘려야 합니다.", "제안"),
            ("창업 실패 후 재도전을 지원하는 제도를 더 확충해야 합니다.", "제안"),
            ("중소기업·소상공인 전용 디지털 전환 지원금을 마련해야 합니다.", "제안"),
            ("온누리상품권 사용처를 온라인까지 확대하여 소상공인 매출을 지원해야 합니다.", "제안"),
            ("가업 승계 세금 부담을 줄여 중소기업의 세대 전환을 돕는 제도가 필요합니다.", "제안"),
        ],
    },
    {
        "topic": "교육",
        "keywords": ["급식", "학교", "식재료", "영양", "친환경"],
        "responsible_dept": "교육위원회",
        "classification": "제안",
        "count": 47,
        "threshold": 100,
        "triggered": False,
        "days_ago": 5,
        "opinions": [
            ("급식 알레르기 영양 정보 표시 강화가 필요합니다.", "제안"),
            ("초등학교 급식에서 친환경 유기농 식재료 사용 비율을 높여야 합니다.", "제안"),
            ("학교 영양사 배치 기준을 강화하고 급식 품질 관리를 개선해야 합니다.", "제안"),
            ("중학교까지 무상급식을 전면 확대해야 합니다.", "제안"),
            ("학교 급식 식재료 원산지 표시 기준을 더 엄격히 해야 합니다.", "제안"),
            ("채식 선택권을 급식에 도입해 다양한 식단을 제공해야 합니다.", "제안"),
            ("급식 조리원 처우를 개선하고 고용 안정성을 높여야 합니다.", "제안"),
            ("학교 영양 교육 시간을 늘려 어릴 때부터 식습관을 바로잡아야 합니다.", "제안"),
            ("방과 후 프로그램 식사 지원도 학교 급식과 동일한 기준으로 관리해야 합니다.", "제안"),
            ("학교 급식 공급업체 선정 시 지역 농가 우선 계약을 의무화해야 합니다.", "제안"),
            ("아토피·알레르기 학생을 위한 대체 식단 제공을 의무화해야 합니다.", "제안"),
        ],
    },
    {
        "topic": "복지",
        "keywords": ["노인", "의료비", "요양", "돌봄", "건강보험"],
        "responsible_dept": "보건복지위원회",
        "classification": "청원",
        "count": 38,
        "threshold": 100,
        "triggered": False,
        "days_ago": 4,
        "opinions": [
            ("노인 요양 서비스 비용 지원을 확대하는 법 개정을 청원합니다.", "청원"),
            ("독거노인 돌봄 서비스를 전국으로 확대하는 노인복지법 개정이 필요합니다.", "청원"),
            ("건강보험 보장 범위를 노인 의료비 중심으로 강화해야 합니다.", "청원"),
            ("치매 환자 돌봄 지원을 위한 특별법 제정을 청원합니다.", "청원"),
            ("요양보호사 처우 개선 및 급여 인상을 의무화하는 법이 필요합니다.", "청원"),
            ("노인 기초연금 지급 대상을 확대하고 금액을 현실화해야 합니다.", "청원"),
            ("아동 돌봄 공백 해소를 위한 국공립 돌봄 시설 확대 법안이 필요합니다.", "청원"),
            ("장애인 활동 지원 서비스 시간을 현실에 맞게 대폭 늘려야 합니다.", "청원"),
            ("저소득층 아동 의료비 100% 국가 지원을 위한 특별법 제정을 청원합니다.", "청원"),
        ],
    },
    {
        "topic": "노동",
        "keywords": ["최저임금", "노동", "임금", "근로시간", "청년"],
        "responsible_dept": "환경노동위원회",
        "classification": "제안",
        "count": 31,
        "threshold": 100,
        "triggered": False,
        "days_ago": 3,
        "opinions": [
            ("최저임금을 현실화하고 생활임금 제도를 도입해야 합니다.", "제안"),
            ("청년 노동자 권리 보호를 위한 표준 근로계약서 사용을 의무화해야 합니다.", "제안"),
            ("주 52시간제 적용 범위를 중소기업까지 확대해야 합니다.", "제안"),
            ("플랫폼 노동자 산재보험 적용 의무화가 시급합니다.", "제안"),
            ("직장 내 괴롭힘 피해 근로자 보호 제도를 강화해야 합니다.", "제안"),
            ("육아휴직 사용을 강제할 수 있는 제도적 장치가 필요합니다.", "제안"),
            ("청년 실업급여 수급 기간을 연장하고 금액을 높여야 합니다.", "제안"),
            ("비정규직·계약직 근로자의 정규직 전환 기회를 늘리는 정책이 필요합니다.", "제안"),
            ("야간·휴일 근로 수당 기준을 명확히 하고 미지급 시 처벌을 강화해야 합니다.", "제안"),
        ],
    },
    {
        "topic": "디지털",
        "keywords": ["AI", "디지털", "행정", "전자정부", "개인정보"],
        "responsible_dept": "과학기술정보방송통신위원회",
        "classification": "제안",
        "count": 22,
        "threshold": 100,
        "triggered": False,
        "days_ago": 2,
        "opinions": [
            ("AI 기반 민원 처리 시스템 도입으로 행정 효율을 높여야 합니다.", "제안"),
            ("전자정부 서비스 접근성을 노인 및 장애인 친화적으로 개선해야 합니다.", "제안"),
            ("개인정보 보호 강화를 위한 데이터 처리 투명성 의무화가 필요합니다.", "제안"),
            ("디지털 소외 계층을 위한 IT 교육 지원을 확대해야 합니다.", "제안"),
            ("공공 데이터 개방을 확대하여 민간 혁신 생태계를 육성해야 합니다.", "제안"),
            ("AI 윤리 가이드라인을 법제화하여 국민 권리를 보호해야 합니다.", "제안"),
            ("스마트시티 인프라 확충을 통해 디지털 행정 서비스를 고도화해야 합니다.", "제안"),
            ("사이버 범죄 피해 신고 및 지원 체계를 강화하는 디지털 안전 정책이 필요합니다.", "제안"),
        ],
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
    "responsible_dept": "국토교통위원회",
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

    # 클러스터 + 소속 의견 세션 삽입
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
        db.flush()

        # 각 클러스터에 샘플 의견 세션 추가
        for j, (opinion_text, classification) in enumerate(data.get("opinions", [])):
            opinion_time = created + timedelta(hours=j * 4 + 1)
            session = SessionModel(
                session_id=str(uuid.uuid4()),
                final_classification=classification,
                status="completed",
                cluster_id=cluster_id,
                conversation_stage="complete",
                conversation_context={
                    "initial_message": opinion_text,
                    "classification": classification,
                    "responsible_dept": data["responsible_dept"],
                    "topic": data["topic"],
                    "keywords": data["keywords"],
                },
                created_at=opinion_time,
            )
            db.add(session)

    db.commit()
