"""민원/제안/청원 분류 예측기 (TF-IDF + LogisticRegression)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_ASSET_DIR = Path(__file__).resolve().parent.parent / "ml_assets"
_DEFAULT_MODEL_PATH = _ASSET_DIR / "classification_model.joblib"


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s가-힣]", " ", text)
    return text.strip()


class ClassificationPredictor:
    """민원/제안/청원 분류 모델 어댑터."""

    def __init__(self, model_path: Path = _DEFAULT_MODEL_PATH):
        import joblib
        artifact = joblib.load(model_path)
        self._pipeline = artifact["pipeline"]
        self._le = artifact["label_encoder"]
        logger.info("ClassificationPredictor 로드 완료: %s", model_path.name)
        # 로드 확인용 smoke test
        self._pipeline.predict_proba([_clean_text("테스트")])

    def predict(self, text: str) -> dict:
        """
        Returns:
            {"classification": "민원"|"제안"|"청원", "confidence": float}
        """
        cleaned = _clean_text(text)
        proba = self._pipeline.predict_proba([cleaned])[0]
        class_idx = int(proba.argmax())
        label = self._le.inverse_transform([class_idx])[0]
        confidence = round(float(proba[class_idx]), 4)
        return {"classification": label, "confidence": confidence}
