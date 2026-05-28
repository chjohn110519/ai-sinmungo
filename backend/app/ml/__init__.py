"""
app.ml — ML 모델 패키지

외부에서는 get_registry()만 사용하면 됩니다.

    from app.ml import get_registry

    registry = get_registry()
    prob = registry.predict_pass_probability(text)   # float | None
    recs = registry.recommend_committees(text)       # list[dict]
"""

from app.ml.model_registry import get_registry, reset_registry

__all__ = ["get_registry", "reset_registry"]
