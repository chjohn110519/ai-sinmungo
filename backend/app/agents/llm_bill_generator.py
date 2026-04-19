"""정책 제안서를 정식 법안 형식으로 변환하는 에이전트."""

from pydantic import BaseModel
from typing import List
from app.schemas.proposal import PolicyProposal
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


class BillArticle(BaseModel):
    article_number: int   # 조 번호
    title: str            # 조 제목
    content: str          # 조 내용


class FormalBill(BaseModel):
    bill_number: str          # 의안번호 (임시)
    bill_title: str           # 법안명 (예: ○○법 제정안)
    purpose: str              # 제안이유
    main_content: str         # 주요내용
    articles: List[BillArticle]  # 조문
    supplementary_provisions: str  # 부칙
    proposer: str             # 제안자 (시민 제안)
    expected_committee: str   # 소관위원회
    related_laws: List[str]   # 관련 법령


class LLMBillGenerator:
    """PolicyProposal → 정식 법안(FormalBill) 변환."""

    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None

        if INSTRUCTOR_AVAILABLE:
            if settings.openai_api_key:
                try:
                    self.openai_client = instructor.from_openai(OpenAI(api_key=settings.openai_api_key))
                except Exception:
                    pass
            if settings.anthropic_api_key:
                try:
                    self.anthropic_client = instructor.from_anthropic(Anthropic(api_key=settings.anthropic_api_key))
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

    def generate_bill(self, proposal: PolicyProposal, classification: str = "제안") -> FormalBill:
        """PolicyProposal을 정식 법안으로 변환."""

        prompt = f"""다음 정책 제안서를 대한민국 국회 법안 형식으로 변환하세요.

[제안서]
제목: {proposal.title}
배경: {proposal.background}
주요내용: {proposal.core_requests}
기대효과: {proposal.expected_effects}
담당부처: {proposal.responsible_dept}
관련법령: {', '.join(proposal.related_laws)}

[작성 지침]
- bill_title: "○○법 일부개정법률안" 또는 "○○에 관한 법률안" 형식
- purpose: 제안이유 (왜 이 법이 필요한지, 현황과 문제점 포함, 2-3문단)
- main_content: 주요내용 요약 (3-5가지 핵심 사항, 번호 목록)
- articles: 법안 조문 5-8개 (제1조 목적, 제2조 정의, 제3조~제N조 본문, 마지막 조 벌칙/과태료)
- supplementary_provisions: "이 법은 공포 후 6개월이 경과한 날부터 시행한다." 형태
- expected_committee: 소관위원회 (예: 국토교통위원회, 행정안전위원회)
- proposer: "시민 제안 ({classification})"
- related_laws: 관련 법령 목록"""

        if self.openai_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.openai_client.chat.completions.create(
                        model=settings.openai_model_name,
                        messages=[
                            {"role": "system", "content": "당신은 대한민국 국회 입법조사처 전문위원입니다. 정확한 법안 형식으로 작성하세요."},
                            {"role": "user", "content": prompt},
                        ],
                        response_model=FormalBill,
                        max_tokens=2048,
                        temperature=0.3,
                    )
            except Exception as e:
                print(f"법안 생성 오류(OpenAI): {e}")

        if self.anthropic_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=2048,
                        messages=[{"role": "user", "content": prompt}],
                        response_model=FormalBill,
                    )
            except Exception as e:
                print(f"법안 생성 오류(Anthropic): {e}")

        # 폴백: 기본 법안 구조 반환
        return FormalBill(
            bill_number="2100000",
            bill_title=f"{proposal.title} 관련 법률안",
            purpose=proposal.background,
            main_content=proposal.core_requests,
            articles=[
                BillArticle(article_number=1, title="목적", content=f"이 법은 {proposal.background}을 위하여 필요한 사항을 규정함을 목적으로 한다."),
                BillArticle(article_number=2, title="정의", content="이 법에서 사용하는 용어의 뜻은 다음과 같다."),
                BillArticle(article_number=3, title="기본원칙", content=proposal.core_requests),
                BillArticle(article_number=4, title="국가 및 지방자치단체의 책무", content="국가 및 지방자치단체는 이 법의 목적을 달성하기 위하여 필요한 시책을 수립·시행하여야 한다."),
                BillArticle(article_number=5, title="시행", content=f"이 법에 따른 시책의 시행에 관하여 필요한 사항은 대통령령으로 정한다."),
            ],
            supplementary_provisions="이 법은 공포 후 6개월이 경과한 날부터 시행한다.",
            proposer=f"시민 제안 ({classification})",
            expected_committee=f"{proposal.responsible_dept} 소관 위원회",
            related_laws=proposal.related_laws,
        )
