import logging

from app.config import settings
from app.schemas.routing import RoutingResult

logger = logging.getLogger(__name__)

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

[분류 기준]
- 민원: 행정기관에 특정 조치를 요구하거나 현재의 불편함을 신고. 즉각적·개인적·구체적.
- 제안: 정책·제도·서비스의 개선 아이디어 제안. 시스템 차원의 변화 요구이나 법 개정 없이 가능.
- 청원: 법률/조례의 제정·개정·폐지를 요구하거나 국회/지자체에 공식 청원. 입법 수준의 변화 요구.

[판단 힌트]
- 민원: "해주세요", "고쳐주세요", "처리해주세요" — 지금 당장 불편하고 행정 처리 요청
- 제안: "하면 어떨까요", "도입하면 좋겠습니다", "확대해야 합니다" — 정책 아이디어 제안
- 청원: "법을 개정", "조항 신설", "특별법 제정", "국회에 청원" — 법·제도 변경 요구
- 모호하면 제안 우선. 명확한 법 개정 요구가 있을 때만 청원으로 분류.

[분류 예시]
민원 예시:
- "우리 동네 가로등이 계속 꺼져 있습니다. 수리해 주세요." → 민원
- "버스 정류장에 쓰레기통이 없어서 불편합니다." → 민원
- "옆 공사장 새벽 소음이 너무 심해서 잠을 못 자겠습니다." → 민원
- "동네 공원 화장실이 고장나서 2주째 방치 중입니다." → 민원
- "지하철역 승강기가 자주 고장나 불편합니다." → 민원
- "가정폭력 문제가 심각합니다." → 민원 (즉각적 행정 조치 요청이 없으면 민원)

제안 예시:
- "공공 자전거 대여소를 지하철역 반경 300m 이내에 더 늘려주면 어떨까요." → 제안
- "노인 복지관에 디지털 교육 프로그램을 도입하면 좋겠습니다." → 제안
- "학교 급식 영양 기준을 강화하고 친환경 식재료 사용을 확대해야 합니다." → 제안
- "9급공무원 채용 인원을 늘리는 것을 제안합니다." → 제안
- "중소기업 창업자에 대한 초기 세금 감면 정책을 만들어줬으면 합니다." → 제안
- "대중교통 요금 체계를 통합하고 환승 할인을 늘려야 합니다." → 제안

청원 예시:
- "가정폭력처벌법 조항을 강화하는 법 개정을 청원합니다." → 청원
- "최저임금법에 생활임금 보장 조항을 신설해 주십시오." → 청원
- "개인정보 보호법에 AI 관련 규정을 명문화해야 합니다." → 청원
- "아동급식법을 개정하여 지원 대상을 중학생까지 확대해야 합니다." → 청원
- "소음 피해 근절을 위한 특별법 제정을 국회에 청원합니다." → 청원
- "교통 안전을 위한 도로교통법 개정을 요청합니다." → 청원

[추출 항목]
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
                except Exception as exc:
                    logger.warning("AIRouter OpenAI 클라이언트 초기화 실패: %s", exc)
            if settings.anthropic_api_key:
                try:
                    self.anthropic_client = instructor.from_anthropic(
                        Anthropic(api_key=settings.anthropic_api_key)
                    )
                except Exception as exc:
                    logger.warning("AIRouter Anthropic 클라이언트 초기화 실패: %s", exc)
        else:
            if settings.openai_api_key:
                try:
                    self.openai_client = OpenAI(api_key=settings.openai_api_key)
                except Exception as exc:
                    logger.warning("AIRouter OpenAI 클라이언트 초기화 실패 (instructor 없음): %s", exc)
            if Anthropic and settings.anthropic_api_key:
                try:
                    self.anthropic_client = Anthropic(api_key=settings.anthropic_api_key)
                except Exception as exc:
                    logger.warning("AIRouter Anthropic 클라이언트 초기화 실패 (instructor 없음): %s", exc)

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
                        kw_result = _ml_or_keyword_classify(message)
                        if kw_result.classification != "민원":
                            result.classification = kw_result.classification
                            result.topic = kw_result.topic
                            result.keywords = result.keywords or kw_result.keywords
                    return result
            except Exception as exc:
                logger.warning("AIRouter OpenAI 라우터 오류: %s", exc)

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
                        kw_result = _ml_or_keyword_classify(message)
                        if kw_result.classification != "민원":
                            result.classification = kw_result.classification
                            result.topic = kw_result.topic
                            result.keywords = result.keywords or kw_result.keywords
                    return result
            except Exception as exc:
                logger.warning("AIRouter Anthropic 라우터 오류: %s", exc)

        return _ml_or_keyword_classify(message)

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
    # 직접적인 청원 관련
    "청원합니다", "청원을", "청원드립니다",
    # 법 개정 관련
    "법 개정", "법률 개정", "법안 발의", "조항 신설", "조항 개정", "조항 삭제",
    "법률 제정", "법 제정", "특별법", "입법 청원", "입법을", "법제화",
    "개정안", "개정을 요청", "개정해야", "개정이 필요",
    # 헌법/국회 관련
    "헌법", "개헌", "국회에", "국회 청원", "발의",
    # 조례/시행령 관련
    "조례 제정", "조례 개정", "시행령", "규정 개정", "명문화",
    # 강한 법 요청 패턴
    "법에 명시", "법적 근거", "법령", "법률로",
]
_PROPOSAL_KW = [
    # 직접 제안 표현
    "제안합니다", "제안드립니다", "제안하고 싶습니다",
    # 개선/도입 관련
    "개선이 필요", "개선해야", "개선하면", "개선책",
    "도입하면", "도입해야", "도입을 제안",
    "확대해야", "확대하면", "확대가 필요",
    "강화해야", "강화하면", "강화가 필요",
    "신설해야", "신설하면", "신설이 필요",
    "확충해야", "개편해야", "체계화해야",
    # 제안 어투
    "어떨까요", "좋겠습니다", "좋을 것 같습니다",
    "하면 어떨까", "하면 좋겠", "하면 좋을",
    "했으면 합니다", "했으면 좋겠", "바랍니다",
    # 정책 관련
    "정책을 만들어", "정책 도입", "제도 개선", "제도 도입",
    "지원 확대", "지원 강화", "지원 정책",
    "프로그램 도입", "서비스 확대", "늘려주", "늘렸으면",
    # 제안/아이디어
    "제안", "의무화", "표준화", "활성화", "체계화",
    "시스템 개선", "방안", "대책 마련",
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


def _ml_or_keyword_classify(message: str) -> RoutingResult:
    """ML 모델 → 키워드 규칙 순으로 분류 (LLM fallback용)."""
    try:
        from app.ml import get_registry
        registry = get_registry()
        ml_result = registry.predict_classification(message)
        if ml_result and ml_result.get("confidence", 0) >= 0.60:
            classification = ml_result["classification"]
            confidence = round(float(ml_result["confidence"]), 3)
            # 주제/부처는 키워드 기반으로 보완
            kw = _keyword_classify(message)
            return RoutingResult(
                classification=classification,
                confidence=confidence,
                responsible_dept=kw.responsible_dept,
                reasoning=f"ML 모델 분류 (confidence={confidence})",
                topic=kw.topic,
                keywords=kw.keywords,
            )
    except Exception as exc:
        logger.debug("ML 분류 모델 미사용 (키워드 폴백): %s", exc)

    return _keyword_classify(message)
