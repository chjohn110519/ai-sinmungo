"""
위원회 추천 어댑터 (TF-IDF + Logistic Regression)

committee_classification/committee_classifier.joblib을 로드하여
법안 요약 텍스트로부터 소관 위원회 후보 리스트를 반환합니다.

Note: classification_model.py는 임포트하지 않음.
  해당 파일이 모듈 레벨에서 matplotlib.font_manager를 초기화하여
  워커 시작 시 불필요한 오버헤드(~200ms)를 유발하기 때문.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)

_ASSET_DIR = Path(__file__).resolve().parent.parent / "ml_assets"
_DEFAULT_MODEL_PATH = _ASSET_DIR / "committee_classifier.joblib"

CONFIDENCE_THRESHOLD = 0.10  # 이 확률 미만 후보는 결과에서 제외
# committee_classifier.joblib은 scikit-learn 1.7.2로 저장됨
_MIN_SKLEARN_VERSION = (1, 7, 0)


def _check_sklearn_version() -> None:
    """scikit-learn 버전이 최소 요구 버전 이상인지 확인한다."""
    try:
        import sklearn
        parts = tuple(int(x) for x in sklearn.__version__.split(".")[:3] if x.isdigit())
        if parts < _MIN_SKLEARN_VERSION:
            min_str = ".".join(str(x) for x in _MIN_SKLEARN_VERSION)
            raise RuntimeError(
                f"committee_classifier.joblib은 scikit-learn {min_str}+ 필요 "
                f"(현재: {sklearn.__version__}). "
                f"업그레이드: pip install 'scikit-learn>={min_str}'"
            )
    except ImportError:
        raise ImportError("scikit-learn 미설치. 설치: pip install 'scikit-learn>=1.7.0'")


def _clean_text(text: str) -> str:
    """법안 텍스트 정규화 (classification_model.py의 clean_text와 동일 로직)"""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s가-힣]", " ", text)
    return text.strip()


class CommitteeRecommender:
    """위원회 추천기: TF-IDF 파이프라인 + LabelEncoder 래퍼"""

    def __init__(self, model_path: Path = _DEFAULT_MODEL_PATH):
        import joblib  # 런타임에 임포트 (설치 안 된 환경 대비)
        _check_sklearn_version()  # 버전 불일치를 로드 시점에 조기 감지
        obj = joblib.load(model_path)
        self.pipe: Pipeline = obj["pipeline"]
        self.le: LabelEncoder = obj["label_encoder"]
        # 로드 후 간단한 smoke test — 버전 불일치로 인한 idf 오류 조기 감지
        try:
            self.pipe.predict_proba(["테스트"])
        except Exception as smoke_exc:
            raise RuntimeError(
                f"committee_classifier 로드 후 smoke test 실패 "
                f"(scikit-learn 버전 불일치 가능성): {smoke_exc}"
            ) from smoke_exc
        logger.info(
            "CommitteeRecommender 로드 완료: %d개 위원회 클래스 (모델: %s)",
            len(self.le.classes_),
            model_path.name,
        )

    def recommend(
        self,
        text: str,
        top_k: int = 5,
        threshold: float = CONFIDENCE_THRESHOLD,
    ) -> list[dict]:
        """
        법안 요약 텍스트를 받아 위원회 후보를 확률 순으로 반환한다.

        Args:
            text: 법안 요약 또는 제안 내용 텍스트
            top_k: 반환할 최대 후보 수
            threshold: 이 확률 미만 후보는 결과에서 제외

        Returns:
            [
                {"rank": 1, "committee": "보건복지위원회", "confidence": 0.87, "confident": True},
                ...
            ]
        """
        cleaned = _clean_text(text)
        if not cleaned:
            return []

        proba = self.pipe.predict_proba([cleaned])[0]
        top_idx = np.argsort(proba)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(top_idx, 1):
            prob = float(proba[idx])
            if prob < threshold:
                break
            results.append(
                {
                    "rank": rank,
                    "committee": str(self.le.classes_[idx]),
                    "confidence": round(prob, 4),
                    "confident": prob >= 0.5,
                }
            )
        return results
