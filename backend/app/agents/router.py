from app.config import settings
from app.schemas.routing import RoutingResult

try:
    import instructor
    from anthropic import Anthropic
    from openai import OpenAI
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False
    try:
        from anthropic import Anthropic
    except ImportError:
        Anthropic = None
    try:
        from openai import OpenAI
    except ImportError:
        OpenAI = None


SYSTEM_PROMPT = "당신은 국민신문고 민원 분류 전문가입니다."

CLASSIFY_PROMPT = """사용자 입력을 분석하여 아래 정보를 추출하세요.

분류 기준:
- 민원: 행정기관에 특정 행위를 요구하거나 불편함을 신고하는 내용
- 제안: 정책이나 제도의 개선 또는 새로운 아이디어를 제안하는 내용
- 청원: 법률·제도의 제정/개폐 또는 공공 문제 해결을 국가에 청원하는 내용

추출 항목:
- classification: 민원/제안/청원 중 하나
- confidence: 분류 확신도 (0.0~1.0)
- responsible_dept: 관할 부처명 (예: 국토교통부, 환경부, 행정안전부)
- reasoning: 분류 이유 한 문장
- topic: 대주제 한 단어 (교통, 환경, 주거, 복지, 교육, 의료, 경제, 노동, 안전, 기타 중 선택)
- keywords: 핵심 키워드 3~5개 (리스트)

사용자 입력: {message}"""


class AIRouter:
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
            if settings.openai_api_key:
                try:
                    self.openai_client = OpenAI(api_key=settings.openai_api_key)
                except Exception:
                    pass
            if Anthropic and settings.anthropic_api_key:
                try:
                    self.anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
                except Exception:
                    pass

    def route_message(self, message: str) -> RoutingResult:
        """사용자 메시지를 민원/제안/청원으로 분류"""
        prompt = CLASSIFY_PROMPT.format(message=message)

        if self.openai_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.openai_client.chat.completions.create(
                        model=settings.openai_model_name,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        response_model=RoutingResult,
                        max_tokens=512,
                        temperature=0.2,
                    )
                else:
                    response = self.openai_client.chat.completions.create(
                        model=settings.openai_model_name,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=512,
                        temperature=0.2,
                    )
                    result = self._fallback_parse(response.choices[0].message.content)
                    # fallback parse가 기본값을 반환하면 키워드 분류로 보완
                    if result.confidence <= 0.55:
                        kw_result = _keyword_classify(message)
                        if kw_result.classification != "민원":
                            result.classification = kw_result.classification
                            result.topic = kw_result.topic
                            result.keywords = result.keywords or kw_result.keywords
                    return result
            except Exception as exc:
                print(f"OpenAI 라우터 오류: {exc}")

        if self.anthropic_client is not None:
            try:
                if INSTRUCTOR_AVAILABLE:
                    return self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=512,
                        messages=[{"role": "user", "content": prompt}],
                        response_model=RoutingResult,
                    )
                else:
                    response = self.anthropic_client.messages.create(
                        model=settings.anthropic_model_name,
                        max_tokens=512,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    result = self._fallback_parse(response.content[0].text)
                    if result.confidence <= 0.55:
                        kw_result = _keyword_classify(message)
                        if kw_result.classification != "민원":
                            result.classification = kw_result.classification
                            result.topic = kw_result.topic
                            result.keywords = result.keywords or kw_result.keywords
                    return result
            except Exception as exc:
                print(f"Anthropic 라우터 오류: {exc}")

        return _keyword_classify(message)

    def _fallback_parse(self, text: str) -> RoutingResult:
        """Instructor 미사용 시 텍스트 파싱 폴백"""
        import json as _json
        result = {
            "classification": "민원",
            "confidence": 0.55,
            "responsible_dept": "행정안전부",
            "reasoning": text,
            "topic": "기타",
            "keywords": [],
        }
        for line in text.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip().strip('"')
            if key == "classification" and val in {"민원", "제안", "청원"}:
                result["classification"] = val
            elif key == "confidence":
                try:
                    result["confidence"] = float(val)
                except ValueError:
                    pass
            elif key == "responsible_dept":
                result["responsible_dept"] = val
            elif key == "reasoning":
                result["reasoning"] = val
            elif key == "topic":
                result["topic"] = val
            elif key == "keywords":
                try:
                    kws = _json.loads(val)
                    if isinstance(kws, list):
                        result["keywords"] = kws
                except Exception:
                    result["keywords"] = [k.strip() for k in val.strip("[]").split(",") if k.strip()]
        return RoutingResult(**result)


# ── 키워드 기반 분류 (LLM 실패 시 fallback) ─────────────────────────────────

_PETITION_KW = [
    "청원", "법 개정", "법률 개정", "입법", "제정", "폐지", "법안", "조항 삭제",
    "헌법", "개헌", "법령", "규정 개정", "국회",
]
_PROPOSAL_KW = [
    "제안", "제안합니다", "개선", "도입", "확대", "강화", "신설", "개편",
    "바꿔", "바꾸", "해주면", "했으면", "필요합니다", "방안", "정책",
    "지원 확대", "지원해", "늘려", "늘렸으면", "만들어", "시행",
]

_TOPIC_KW: dict[str, tuple[list[str], str]] = {
    "교통": (["도로", "버스", "지하철", "주차", "신호", "교통", "자전거", "횡단보도", "택시"], "국토교통부"),
    "환경": (["환경", "쓰레기", "미세먼지", "공기", "소음", "하천", "오염", "재활용", "탄소"], "환경부"),
    "주거": (["주택", "아파트", "임대", "전세", "주거", "건물", "빈집", "층간"], "국토교통부"),
    "복지": (["복지", "장애", "노인", "아동", "청소년", "돌봄", "요양", "어르신"], "보건복지부"),
    "교육": (["교육", "학교", "학원", "교사", "급식", "입시", "대학", "학생", "수업"], "교육부"),
    "의료": (["의료", "병원", "의사", "약", "건강", "보건", "간호", "진료", "치료"], "보건복지부"),
    "경제": (["경제", "세금", "금융", "중소기업", "창업", "일자리", "물가", "소비"], "기획재정부"),
    "노동": (["노동", "근로", "임금", "고용", "실업", "직장", "알바", "최저임금"], "고용노동부"),
    "안전": (["안전", "범죄", "사고", "재난", "소방", "경찰", "화재", "보안"], "행정안전부"),
}


def _keyword_classify(message: str) -> RoutingResult:
    msg = message

    # 청원 우선 판단
    for kw in _PETITION_KW:
        if kw in msg:
            classification = "청원"
            break
    else:
        # 제안 판단
        for kw in _PROPOSAL_KW:
            if kw in msg:
                classification = "제안"
                break
        else:
            classification = "민원"

    # 주제 및 담당 부처 추출
    topic = "기타"
    dept = "행정안전부"
    keywords: list[str] = []
    for t, (kws, d) in _TOPIC_KW.items():
        matched = [kw for kw in kws if kw in msg]
        if matched:
            topic = t
            dept = d
            keywords = matched[:5]
            break

    return RoutingResult(
        classification=classification,
        confidence=0.60,
        responsible_dept=dept,
        reasoning="키워드 기반 분류 (LLM 미응답 시 fallback)",
        topic=topic,
        keywords=keywords,
    )
