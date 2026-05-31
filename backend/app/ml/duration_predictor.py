"""가결 예상 소요기간 예측 어댑터.

Predicted_date_of_approval/duration_regressor.joblib 모델을 백엔드에서
사용하기 위한 래퍼다. 모델 구조는 다음과 같다.

- KoBERT 768차원 임베딩
- joblib artifact 내부 PCA로 128차원 축소
- 발의자/대수/발의일 등 10차원 메타 피처 결합
- LightGBM regressor가 log1p(days)를 예측
"""

from __future__ import annotations

from datetime import date
import logging
from pathlib import Path

import numpy as np

from app.ml.approve_predictor import KoBERTEmbedder

logger = logging.getLogger(__name__)

_ASSET_DIR = Path(__file__).resolve().parent.parent / "ml_assets"
_HANDOFF_DIR = _ASSET_DIR / "kobert_embedding_handoff_v2"
_DEFAULT_MODEL_PATH = _ASSET_DIR / "duration_regressor.joblib"

PROPOSER_KINDS = ("위원장", "의원", "정부")


def _build_meta_features(
    proposer_kind: str = "의원",
    age: int = 21,
    propose_year: int | None = None,
    propose_month: int | None = None,
    is_modified: bool = False,
    cmt_score: float = 0.5,
    has_cmt: bool = False,
) -> np.ndarray:
    today = date.today()
    propose_year = propose_year or today.year
    propose_month = propose_month or today.month

    feat = np.zeros(10, dtype=np.float32)
    for k, kind in enumerate(PROPOSER_KINDS):
        feat[k] = 1.0 if proposer_kind == kind else 0.0
    feat[3] = float(age)
    feat[4] = 0.0  # 신규 입력에는 위원회 빈도 인코딩을 알 수 없으므로 0
    feat[5] = float(propose_year)
    feat[6] = float(propose_month)
    feat[7] = 1.0 if is_modified else 0.0
    feat[8] = float(cmt_score)
    feat[9] = 1.0 if has_cmt else 0.0
    return feat


class ApprovalDurationPredictor:
    """KoBERT 임베딩 기반 가결 예상 소요기간 예측기."""

    def __init__(
        self,
        model_path: Path = _DEFAULT_MODEL_PATH,
        handoff_dir: Path = _HANDOFF_DIR,
    ):
        import joblib

        artifact = joblib.load(model_path)
        if not isinstance(artifact, dict) or "model" not in artifact or "pca" not in artifact:
            raise ValueError("duration_regressor.joblib은 {'model', 'pca'} 구조여야 합니다.")

        self.model = artifact["model"]
        self.pca = artifact["pca"]
        self.embedder = KoBERTEmbedder(handoff_dir=handoff_dir)

        expected_features = getattr(self.model, "n_features_in_", None)
        if expected_features not in (None, 138):
            raise ValueError(f"기간 예측 모델 입력 차원 오류: 기대 138, 실제 {expected_features}")

        logger.info("ApprovalDurationPredictor 로드 완료: %s", model_path.name)

    def predict_days(
        self,
        text: str,
        *,
        proposer_kind: str = "의원",
        age: int = 21,
        propose_year: int | None = None,
        propose_month: int | None = None,
        is_modified: bool = False,
    ) -> float:
        if proposer_kind not in PROPOSER_KINDS:
            proposer_kind = "의원"

        embedding = self.embedder.embed(text).astype(np.float32)
        embedding_pca = self.pca.transform(embedding).astype(np.float32)
        meta = _build_meta_features(
            proposer_kind=proposer_kind,
            age=age,
            propose_year=propose_year,
            propose_month=propose_month,
            is_modified=is_modified,
        ).reshape(1, -1)
        features = np.concatenate([embedding_pca, meta], axis=1)
        pred_log = self.model.predict(features)
        days = float(np.expm1(pred_log[0]))
        if not np.isfinite(days):
            raise ValueError("기간 예측 결과가 유효하지 않습니다.")
        return max(days, 0.0)
