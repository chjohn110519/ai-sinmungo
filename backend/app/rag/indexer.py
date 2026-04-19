from __future__ import annotations
from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from app.config import settings

SAMPLE_DOCUMENTS = [
    # ── 도로·교통 ──────────────────────────────────────────────────────────
    {"id": "law_road_001", "title": "도로교통법", "type": "law", "department": "경찰청",
     "content": "도로에서의 교통안전 및 질서 유지를 위한 법률. 운전면허, 신호위반, 음주운전, 보행자 보호 규정을 포함합니다."},
    {"id": "law_road_002", "title": "도로법", "type": "law", "department": "국토교통부",
     "content": "도로의 노선 지정, 관리, 보전 및 비용 부담에 관한 사항을 규정합니다. 도로 구조와 기준, 통행 제한 등이 포함됩니다."},
    {"id": "law_road_003", "title": "교통안전법", "type": "law", "department": "국토교통부",
     "content": "교통안전에 관한 국가 및 지방자치단체의 책무, 교통안전 계획 수립, 교통사고 조사 등에 관한 법률입니다."},
    {"id": "law_road_004", "title": "보행안전 및 편의증진에 관한 법률", "type": "law", "department": "행정안전부",
     "content": "보행자의 안전하고 편리한 보행 환경 조성을 위한 법률. 보행우선구역 지정, 보행안전시설 설치 기준 포함."},
    {"id": "case_road_001", "title": "도로 포장 개선 민원", "type": "petition", "department": "시청 도로과",
     "content": "주거지역 도로에 포트홀이 다수 발생하여 차량 손상 및 보행자 위험이 우려됩니다. 즉각적인 보수 공사 요청."},
    {"id": "case_road_002", "title": "스쿨존 교통안전 강화 제안", "type": "bill", "department": "교육부",
     "content": "어린이보호구역 내 무인단속카메라 확대 설치 및 과속방지턱 추가 설치로 어린이 교통사고 예방 강화 제안."},
    {"id": "case_road_003", "title": "스마트 신호등 시스템 도입 제안", "type": "bill", "department": "국토교통부",
     "content": "교통량에 따라 자동으로 조절되는 AI 기반 스마트 신호등 도입으로 교통 정체 감소 및 에너지 절감 기대."},
    {"id": "case_road_004", "title": "자전거 도로 확충 청원", "type": "petition", "department": "지방자치단체",
     "content": "탄소중립 실현을 위한 자전거 전용 도로 확충 및 공유 자전거 시스템 전국 확대 청원."},
    {"id": "case_road_005", "title": "불법 주정차 단속 강화 민원", "type": "petition", "department": "경찰청",
     "content": "이면도로 불법 주정차로 인한 통행 불편 및 화재차량 진입 장애 문제 해소를 위한 단속 강화 요청."},
    {"id": "case_road_006", "title": "대중교통 노선 신설 제안", "type": "bill", "department": "국토교통부",
     "content": "신규 택지지구 주민의 교통 편의를 위한 버스 노선 신설 및 환승 체계 개선 제안."},
    # ── 환경·소음 ──────────────────────────────────────────────────────────
    {"id": "law_env_001", "title": "환경분쟁조정법", "type": "law", "department": "환경부",
     "content": "환경오염으로 인한 피해의 분쟁을 신속하고 공정하게 해결하기 위한 분쟁조정위원회 설치 및 절차를 규정."},
    {"id": "law_env_002", "title": "소음·진동관리법", "type": "law", "department": "환경부",
     "content": "소음·진동으로 인한 피해를 방지하고 생활환경을 보전하기 위해 배출허용기준, 규제지역 지정 등을 규정."},
    {"id": "law_env_003", "title": "대기환경보전법", "type": "law", "department": "환경부",
     "content": "대기오염으로 인한 국민건강 및 환경 피해를 예방하기 위해 배출허용기준, 총량 규제, 측정망 운영을 규정."},
    {"id": "case_env_001", "title": "공사장 소음 규제 강화 민원", "type": "petition", "department": "환경부",
     "content": "야간 공사 소음으로 인한 수면 장애 및 생활 불편 해소를 위한 주거지역 공사 시간 제한 강화 요청."},
    {"id": "case_env_002", "title": "미세먼지 대응 정책 강화 청원", "type": "petition", "department": "환경부",
     "content": "초미세먼지 저감을 위한 노후 경유차 조기 폐차 지원 확대 및 사업장 배출 기준 강화 청원."},
    {"id": "case_env_003", "title": "생활쓰레기 분리수거 개선 제안", "type": "bill", "department": "환경부",
     "content": "재활용 가능 자원의 분리배출 체계 개선 및 주민 교육 강화로 자원순환율 향상 제안."},
    {"id": "case_env_004", "title": "하천 수질 오염 신고", "type": "petition", "department": "환경부",
     "content": "인근 공장 폐수 불법 방류로 인한 하천 오염 발생. 즉각적인 현장 조사 및 원상 복구 요청."},
    {"id": "case_env_005", "title": "층간소음 분쟁 조정 제도 강화 제안", "type": "bill", "department": "국토교통부",
     "content": "공동주택 층간소음 분쟁 증가에 대응하기 위한 조정 기구 확대 및 소음 기준 강화 제도 개선 제안."},
    # ── 주거·건설 ──────────────────────────────────────────────────────────
    {"id": "law_house_001", "title": "주택법", "type": "law", "department": "국토교통부",
     "content": "주택의 건설·공급·관리를 위한 법률. 주택건설사업 등록, 사업계획 승인, 주택공급 규정 등을 포함."},
    {"id": "law_house_002", "title": "주택임대차보호법", "type": "law", "department": "법무부",
     "content": "주거용 건물 임대차에서 임차인의 권리를 보호하는 법률. 대항력, 우선변제권, 임대료 증액 제한 등 규정."},
    {"id": "law_house_003", "title": "건설기술진흥법", "type": "law", "department": "국토교통부",
     "content": "건설공사의 품질확보와 안전관리를 위한 기술기준, 건설사업관리, 안전점검 등을 규정."},
    {"id": "case_house_001", "title": "공공임대주택 공급 확대 청원", "type": "petition", "department": "국토교통부",
     "content": "저소득층 및 청년 1인 가구 주거 안정을 위한 공공임대주택 공급 물량 확대 및 입주 자격 완화 청원."},
    {"id": "case_house_002", "title": "노후 건축물 안전점검 강화 민원", "type": "petition", "department": "국토교통부",
     "content": "20년 이상 된 노후 아파트 외벽 균열 및 구조물 안전 위협 문제에 대한 긴급 안전점검 요청."},
    {"id": "case_house_003", "title": "전월세 신고제 실효성 강화 제안", "type": "bill", "department": "국토교통부",
     "content": "임대차 시장 투명성 제고를 위한 전월세 신고제 신고 범위 확대 및 위반 시 제재 강화 제안."},
    {"id": "case_house_004", "title": "빈집 정비 촉진 제도 도입 제안", "type": "bill", "department": "국토교통부",
     "content": "도심 내 방치된 빈집으로 인한 범죄·위생 문제 해소를 위한 강제정비 제도 및 소유자 지원책 마련 제안."},
    # ── 복지·의료 ──────────────────────────────────────────────────────────
    {"id": "law_welfare_001", "title": "국민건강보험법", "type": "law", "department": "보건복지부",
     "content": "전 국민 의료보장을 위한 건강보험 가입·급여·보험료에 관한 규정. 요양급여 기준 및 보험료 부과 체계 포함."},
    {"id": "law_welfare_002", "title": "사회복지사업법", "type": "law", "department": "보건복지부",
     "content": "사회복지 사업의 기본 원칙과 사회복지법인 설립·운영, 사회복지시설 기준 등을 규정하는 기본법."},
    {"id": "law_welfare_003", "title": "장애인복지법", "type": "law", "department": "보건복지부",
     "content": "장애인의 인간다운 삶과 권리 보장을 위한 복지 서비스, 재활, 직업 지원 등에 관한 법률."},
    {"id": "law_welfare_004", "title": "노인장기요양보험법", "type": "law", "department": "보건복지부",
     "content": "고령이나 노인성 질병으로 일상생활 수행이 어려운 노인에게 신체·가사 지원 서비스를 제공하는 법률."},
    {"id": "case_welfare_001", "title": "의료취약지역 공공의료 확충 청원", "type": "petition", "department": "보건복지부",
     "content": "농어촌 및 도서 지역의 의료 접근성 향상을 위한 공공의료원 신설 및 이동 진료 서비스 확대 청원."},
    {"id": "case_welfare_002", "title": "장애인 이동권 보장 강화 제안", "type": "bill", "department": "보건복지부",
     "content": "저상버스 도입 의무화 및 지하철 엘리베이터 설치 확대로 장애인 이동권 실질적 보장 강화 제안."},
    {"id": "case_welfare_003", "title": "아동 돌봄 공백 해소 제안", "type": "bill", "department": "보건복지부",
     "content": "맞벌이 가정 아동의 방과 후 돌봄 공백 해소를 위한 지역아동센터 확충 및 운영 시간 연장 지원 제안."},
    {"id": "case_welfare_004", "title": "정신건강 지역사회 서비스 강화 제안", "type": "bill", "department": "보건복지부",
     "content": "지역 정신건강복지센터 확대와 위기 개입 체계 강화로 자살 예방 및 정신건강 회복 지원 제안."},
    # ── 교육 ───────────────────────────────────────────────────────────────
    {"id": "law_edu_001", "title": "교육기본법", "type": "law", "department": "교육부",
     "content": "교육에 관한 국민의 권리와 의무, 국가 및 지방자치단체의 책임을 규정하는 교육 분야 기본법."},
    {"id": "law_edu_002", "title": "초중등교육법", "type": "law", "department": "교육부",
     "content": "초·중등 교육과정, 학교 설립·운영 기준, 교원 자격 및 학생 징계 등에 관한 법률."},
    {"id": "case_edu_001", "title": "과밀학급 해소 방안 청원", "type": "petition", "department": "교육부",
     "content": "학급당 학생 수 감축을 통한 교육의 질 향상 및 교사 1인당 학생 수 법정화 청원."},
    {"id": "case_edu_002", "title": "디지털 교육 격차 해소 제안", "type": "bill", "department": "교육부",
     "content": "저소득층 학생 대상 디지털 기기 보급 및 인터넷 무상 제공으로 디지털 교육 격차 해소 제안."},
    {"id": "case_edu_003", "title": "학교 급식 품질 개선 민원", "type": "petition", "department": "교육부",
     "content": "학교 급식 재료의 원산지 표시 강화 및 영양 기준 준수 여부 상시 모니터링 체계 구축 요청."},
    {"id": "case_edu_004", "title": "사교육비 경감 정책 강화 청원", "type": "petition", "department": "교육부",
     "content": "공교육 내실화를 통한 사교육비 경감 및 방과 후 학교 프로그램 다양화·내실화 강화 청원."},
    # ── 디지털·행정 ────────────────────────────────────────────────────────
    {"id": "law_digital_001", "title": "정보공개법", "type": "law", "department": "행정안전부",
     "content": "정부기관이 보유한 정보의 공개를 청구하는 방법과 예외 사항을 규정하여 행정의 투명성을 높이는 법률."},
    {"id": "law_digital_002", "title": "전자정부법", "type": "law", "department": "행정안전부",
     "content": "전자정부 구현을 위한 행정기관의 정보시스템 운영, 행정 정보 공동이용, 전자문서 유통 체계를 규정."},
    {"id": "law_digital_003", "title": "개인정보보호법", "type": "law", "department": "개인정보보호위원회",
     "content": "개인정보의 수집·이용·제공·파기 등에 관한 기준과 정보 주체의 권리 보장을 규정하는 기본법."},
    {"id": "law_digital_004", "title": "지방자치법", "type": "law", "department": "행정안전부",
     "content": "지방자치단체의 조직, 권한, 기능을 규정하는 법률. 주민참여, 민원처리, 주민소환, 도시계획 등 포함."},
    {"id": "law_digital_005", "title": "공직자윤리법", "type": "law", "department": "국가청렴위원회",
     "content": "공직자의 윤리기준, 재산공개, 부정청탁 금지 및 행동강령 등을 규정하는 공직자 청렴 법률."},
    {"id": "case_digital_001", "title": "행정서비스 온라인화 확대 제안", "type": "bill", "department": "행정안전부",
     "content": "민원 서류 발급 및 신청 절차의 완전 온라인화로 대면 방문 없이 행정 서비스 이용 가능하도록 개선 제안."},
    {"id": "case_digital_002", "title": "공공 데이터 개방 확대 제안", "type": "bill", "department": "행정안전부",
     "content": "정부 보유 데이터의 적극적 개방 및 API 제공으로 스타트업 및 연구자의 데이터 활용 활성화 제안."},
    {"id": "case_digital_003", "title": "개인정보 보호 강화 청원", "type": "petition", "department": "개인정보보호위원회",
     "content": "공공기관의 개인정보 과다 수집 관행 개선 및 개인정보 영향평가 의무 대상 확대 청원."},
    {"id": "case_digital_004", "title": "AI 행정 서비스 도입 제안", "type": "bill", "department": "행정안전부",
     "content": "AI 챗봇 기반 24시간 민원 상담 서비스 도입 및 자동화 처리 시스템 구축으로 행정 효율화 제안."},
    {"id": "case_digital_005", "title": "디지털 취약계층 지원 강화 제안", "type": "bill", "department": "과학기술정보통신부",
     "content": "고령층·장애인 등 디지털 소외계층 대상 디지털 리터러시 교육 및 디지털 기기 지원 확대 제안."},
]


def _get_ef():
    return OpenAIEmbeddingFunction(
        api_key=settings.openai_api_key or "dummy",
        model_name="text-embedding-3-small",
    )


class RAGIndexer:
    def __init__(self, persist_dir: str):
        self.persist_dir = persist_dir
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=Path(persist_dir))
        self._ef = _get_ef()

    def initialize_with_sample_data(self, collection_name: str = "legal_documents"):
        """샘플 법령 데이터로 컬렉션 초기화 (이미 충분한 문서가 있으면 스킵)"""
        collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

        existing_count = collection.count()
        if existing_count >= 50:
            print(f"✓ RAG 컬렉션 이미 초기화됨: {existing_count}개 문서")
            return collection

        try:
            self.client.delete_collection(name=collection_name)
        except Exception:
            pass
        collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

        ids = [doc["id"] for doc in SAMPLE_DOCUMENTS]
        documents = [doc["content"] for doc in SAMPLE_DOCUMENTS]
        metadatas = [
            {"title": doc["title"], "type": doc["type"], "department": doc["department"]}
            for doc in SAMPLE_DOCUMENTS
        ]

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"✓ RAG 샘플 데이터 초기화 완료: {len(ids)}개 문서 저장됨")
        return collection

    def create_collection(self, name: str = "legal_documents"):
        return self.client.get_or_create_collection(name=name, embedding_function=self._ef)

    def index_documents(self, documents: list[dict], collection_name: str = "legal_documents"):
        collection = self.client.get_collection(name=collection_name, embedding_function=self._ef)
        ids = [doc["doc_id"] for doc in documents]
        collection.add(
            ids=ids,
            documents=[doc["content"] for doc in documents],
            metadatas=documents,
        )
