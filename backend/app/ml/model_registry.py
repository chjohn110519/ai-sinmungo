"""
ML 모델 싱글턴 레지스트리

서버 시작 시 한 번만 모델을 로드하고 이후 호출은 캐시된 인스턴스를 반환한다.
KoBERT 로딩 실패 시에도 서버가 정상 가동되도록 graceful fallback을 제공한다.

사용법:
    from app.ml import get_registry

    registry = get_registry()
    prob = registry.predict_pass_probability("법안 내용...")   # float | None
    recs = registry.recommend_committees("법안 내용...")       # list[dict]
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_ASSET_DIR = Path(__file__).resolve().parent.parent / "ml_assets"

_registry_instance: "ModelRegistry | None" = None
_registry_lock = threading.Lock()


def _resolve_asset_dir() -> Path:
    """config.ml_assets_dir 설정값이 있으면 해당 경로를, 없으면 기본 경로를 반환한다."""
    try:
        from app.config import settings
        if settings.ml_assets_dir:
            return Path(settings.ml_assets_dir)
    except Exception as exc:
        logger.debug("settings 로드 불가 — 기본 ml_assets 경로 사용: %s", exc)
    return _DEFAULT_ASSET_DIR


def _apply_hf_cache() -> None:
    """config.huggingface_cache_dir이 설정된 경우 HF_HOME 환경변수를 적용한다."""
    try:
        from app.config import settings
        if settings.huggingface_cache_dir:
            os.environ.setdefault("HF_HOME", settings.huggingface_cache_dir)
            logger.info("HuggingFace 캐시 경로 설정: %s", settings.huggingface_cache_dir)
    except Exception as exc:
        logger.debug("settings 로드 불가 — huggingface_cache_dir 미적용: %s", exc)


# ── 공개 API ──────────────────────────────────────────────────────────────────

def get_registry() -> "ModelRegistry":
    """
    ModelRegistry 싱글턴을 반환한다.
    최초 호출 시 모델을 로드하며, 이후 호출은 캐시된 인스턴스를 반환한다.
    thread-safe (double-checked locking).
    """
    global _registry_instance
    if _registry_instance is not None:
        return _registry_instance
    with _registry_lock:
        if _registry_instance is not None:
            return _registry_instance
        _registry_instance = _build_registry()
    return _registry_instance


def reset_registry() -> None:
    """테스트 전용: 싱글턴을 초기화한다."""
    global _registry_instance
    with _registry_lock:
        _registry_instance = None


# ── 내부 빌더 ─────────────────────────────────────────────────────────────────

def _build_registry() -> "ModelRegistry":
    _apply_hf_cache()  # HuggingFace 캐시 설정을 모델 로드 전에 적용
    asset_dir = _resolve_asset_dir()
    committee_rec = _try_load_committee_recommender(asset_dir)
    approve_pred = _try_load_approve_predictor(asset_dir)
    return ModelRegistry(committee_rec=committee_rec, approve_pred=approve_pred)


def _try_load_committee_recommender(asset_dir: Path):
    """위원회 추천 모델 로드 (실패해도 None 반환, 서버 중단 없음)"""
    model_path = asset_dir / "committee_classifier.joblib"
    try:
        import joblib  # noqa: F401 — 설치 여부 조기 확인
        from app.ml.committee_recommender import CommitteeRecommender
        if not model_path.exists():
            logger.warning(
                "위원회 추천 모델 파일 없음: %s — 위원회 추천 비활성화",
                model_path,
            )
            return None
        return CommitteeRecommender(model_path=model_path)
    except Exception as exc:
        logger.warning("위원회 추천 모델 로드 실패 (비활성화): %s", exc)
        return None


def _try_load_approve_predictor(asset_dir: Path):
    """가결 확률 예측 모델 로드 (실패해도 None 반환, 서버 중단 없음)"""
    # settings.ml_enable_kobert (= 환경변수 ML_ENABLE_KOBERT) 가 false이면 건너뜀
    enable_kobert = True
    try:
        from app.config import settings
        enable_kobert = settings.ml_enable_kobert
    except Exception:
        # settings 로드 실패 시 환경변수 직접 확인
        enable_kobert = os.environ.get("ML_ENABLE_KOBERT", "true").lower() not in ("false", "0", "no")

    if not enable_kobert:
        logger.info("ml_enable_kobert=false — KoBERT 가결 예측 비활성화")
        return None

    model_path = asset_dir / "pass_probability_model.joblib"
    handoff_dir = asset_dir / "kobert_embedding_handoff_v2"

    try:
        import joblib  # noqa: F401
        from app.ml.approve_predictor import ApprovePredictor
        if not model_path.exists():
            logger.warning(
                "가결 예측 모델 파일 없음: %s — 가결 예측 비활성화",
                model_path,
            )
            return None
        if not (handoff_dir / "embedding_manifest.json").exists():
            logger.warning(
                "KoBERT manifest 없음: %s — 가결 예측 비활성화",
                handoff_dir,
            )
            return None
        return ApprovePredictor(model_path=model_path, handoff_dir=handoff_dir)
    except ImportError as exc:
        logger.warning(
            "KoBERT 의존성 미설치 (가결 예측 비활성화): %s\n"
            "  설치: pip install torch transformers sentencepiece",
            exc,
        )
        return None
    except Exception as exc:
        logger.warning("가결 예측 모델 로드 실패 (비활성화): %s", exc)
        return None


# ── ModelRegistry 클래스 ───────────────────────────────────────────────────────

class ModelRegistry:
    """
    ML 모델 접근 인터페이스.

    Fallback 동작:
      - approve_pred가 None 이면 predict_pass_probability → None (호출자가 휴리스틱 사용)
      - committee_rec가 None 이면 recommend_committees → []
      - 예측 중 런타임 오류 시 경고 로그 후 None / [] 반환
    """

    def __init__(self, committee_rec, approve_pred):
        self._committee_rec = committee_rec
        self._approve_pred = approve_pred

        # 상태 로그
        committee_status = f"{len(self._committee_rec.le.classes_)}개 위원회 클래스" if committee_rec else "비활성화"
        approve_status = "활성화" if approve_pred else "비활성화"
        logger.info(
            "ModelRegistry 초기화 완료 | 위원회추천: %s | 가결예측: %s",
            committee_status,
            approve_status,
        )

    @property
    def committee_enabled(self) -> bool:
        return self._committee_rec is not None

    @property
    def approval_enabled(self) -> bool:
        return self._approve_pred is not None

    def predict_pass_probability(self, text: str) -> float | None:
        """
        가결 확률을 반환한다.

        Returns:
            float (0.0~1.0) — ML 예측값
            None — ML 모델 미사용 (호출자는 휴리스틱으로 fallback 해야 함)
        """
        if self._approve_pred is None:
            return None
        try:
            return self._approve_pred.predict(text)
        except Exception as exc:
            logger.warning("pass_probability 예측 중 오류 (휴리스틱 사용): %s", exc)
            return None

    def recommend_committees(self, text: str, top_k: int = 5) -> list[dict]:
        """
        위원회 후보 리스트를 반환한다.

        Returns:
            list[dict] — [{"rank", "committee", "confidence", "confident"}, ...]
            [] — 모델 미사용 또는 오류
        """
        if self._committee_rec is None:
            return []
        try:
            return self._committee_rec.recommend(text, top_k=top_k)
        except Exception as exc:
            logger.warning("위원회 추천 중 오류: %s", exc)
            return []
