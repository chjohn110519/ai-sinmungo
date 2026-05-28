"""
가결 확률 예측 어댑터 (KoBERT 임베딩 + Logistic Regression)

Approve_Probability/pass_probability_model.joblib과
skt/kobert-base-v1 (HuggingFace) 모델을 사용하여
법안 텍스트의 국회 가결 확률(0.0~1.0)을 반환합니다.

KoBERTEmbedder 클래스는 Approve_Probability/embedding.py에서
경로 앵커만 변경하여 가져왔습니다 (원본 로직 동일).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

import numpy as np

logger = logging.getLogger(__name__)

_ASSET_DIR = Path(__file__).resolve().parent.parent / "ml_assets"
_HANDOFF_DIR = _ASSET_DIR / "kobert_embedding_handoff_v2"
_DEFAULT_MODEL_PATH = _ASSET_DIR / "pass_probability_model.joblib"
_DEFAULT_MAX_LENGTH = 512


# ── KoBERT 임베더 (Approve_Probability/embedding.py에서 가져옴, 경로만 변경) ──────────

def _load_manifest(handoff_dir: Path) -> dict:
    manifest_path = handoff_dir / "embedding_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"KoBERT manifest 파일 없음: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _import_torch_and_transformers():
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise ImportError(
            "KoBERT 임베딩을 위한 패키지가 없습니다.\n"
            "  pip install torch transformers sentencepiece\n"
            "또는 ML_ENABLE_KOBERT=false 환경변수로 KoBERT를 비활성화하세요."
        ) from exc
    return torch, AutoModel, AutoTokenizer


def _choose_device(device: str | None = None) -> str:
    if device:
        return device
    torch, _, _ = _import_torch_and_transformers()
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _mean_pool(last_hidden_state, attention_mask):
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


class KoBERTEmbedder:
    """KoBERT(skt/kobert-base-v1) 기반 한국어 법안 텍스트 임베더 (768차원, L2 정규화)"""

    def __init__(
        self,
        handoff_dir: str | Path = _HANDOFF_DIR,
        device: str | None = None,
        max_length: int = _DEFAULT_MAX_LENGTH,
    ):
        self.handoff_dir = Path(handoff_dir)
        self.manifest = _load_manifest(self.handoff_dir)
        self.model_name: str = self.manifest.get("model_name", "skt/kobert-base-v1")
        self.max_length = max_length

        self.torch, AutoModel, AutoTokenizer = _import_torch_and_transformers()
        self.device = _choose_device(device)
        logger.info("KoBERT 모델 로딩: %s (device=%s)", self.model_name, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name)
        self.model.to(self.device)
        self.model.eval()
        logger.info("KoBERT 모델 로드 완료")

    def embed(self, texts: str | Iterable[str], batch_size: int = 16) -> np.ndarray:
        """텍스트(들)을 768차원 L2-정규화 벡터로 변환한다."""
        single_input = isinstance(texts, str)
        text_list = [texts] if single_input else list(texts)
        if not text_list:
            return np.empty((0, 768), dtype=np.float32)

        vectors: list[np.ndarray] = []
        with self.torch.no_grad():
            for start in range(0, len(text_list), batch_size):
                batch = text_list[start : start + batch_size]
                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                encoded = {k: v.to(self.device) for k, v in encoded.items()}
                output = self.model(**encoded)
                pooled = _mean_pool(output.last_hidden_state, encoded["attention_mask"])
                normalized = self.torch.nn.functional.normalize(pooled, p=2, dim=1)
                vectors.append(normalized.cpu().numpy().astype("float32"))

        result = np.vstack(vectors)
        if result.shape[1] != 768:
            raise ValueError(f"임베딩 차원 오류: 기대 768, 실제 {result.shape[1]}")
        return result


# ── 가결 예측기 ────────────────────────────────────────────────────────────────

class ApprovePredictor:
    """가결 확률 예측기: KoBERT 임베딩 → LogisticRegression"""

    def __init__(
        self,
        model_path: Path = _DEFAULT_MODEL_PATH,
        handoff_dir: Path = _HANDOFF_DIR,
    ):
        import joblib
        self.artifact = joblib.load(model_path)
        expected_dim: int = self.artifact.get("embedding_dim", 768)
        if expected_dim != 768:
            raise ValueError(
                f"모델이 {expected_dim}차원 임베딩을 기대하지만 KoBERT는 768차원입니다."
            )
        self.embedder = KoBERTEmbedder(handoff_dir=handoff_dir)
        logger.info(
            "ApprovePredictor 로드 완료 (학습 데이터: %d건, 모델: %s)",
            self.artifact.get("num_rows", 0),
            model_path.name,
        )

    def predict(self, text: str) -> float:
        """
        법안 텍스트의 가결 확률을 반환한다.

        Args:
            text: 법안 요약/제안 내용 텍스트

        Returns:
            가결 확률 float (0.0~1.0)
        """
        embedding = self.embedder.embed(text)  # shape: (1, 768)
        models = self.artifact["models"]
        passed_model = models["passed"]
        passed_class_idx = list(passed_model.classes_).index(1)
        return float(passed_model.predict_proba(embedding)[0, passed_class_idx])

    def predict_detailed(self, text: str) -> dict:
        """
        가결 확률 외 상세 예측 결과 반환 (진행 단계, 처리 결과 등).

        Returns:
            {
                "pass_probability": float,
                "pass_probability_percent": float,
                "predicted_progress_stage": str,
                "predicted_proc_result": str,
                "predicted_cmt_result": str,
                "predicted_law_result": str,
                "top_progress_stages": [{"label": str, "probability": float}, ...],
            }
        """
        embedding = self.embedder.embed(text)
        models = self.artifact["models"]

        passed_model = models["passed"]
        passed_class_idx = list(passed_model.classes_).index(1)
        pass_prob = float(passed_model.predict_proba(embedding)[0, passed_class_idx])

        def _top_k(model, top_k: int = 5) -> list[dict]:
            proba = model.predict_proba(embedding)[0]
            order = np.argsort(proba)[::-1][:top_k]
            return [
                {"label": str(model.classes_[i]), "probability": round(float(proba[i]), 4)}
                for i in order
            ]

        return {
            "pass_probability": round(pass_prob, 4),
            "pass_probability_percent": round(pass_prob * 100, 2),
            "predicted_progress_stage": str(models["progress_stage"].predict(embedding)[0]),
            "predicted_proc_result": str(models["proc_result"].predict(embedding)[0]),
            "predicted_cmt_result": str(models["cmt_result"].predict(embedding)[0]),
            "predicted_law_result": str(models["law_result"].predict(embedding)[0]),
            "top_progress_stages": _top_k(models["progress_stage"]),
        }
