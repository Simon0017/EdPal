# ── NEW FILE: careers/services/engine/__init__.py ────────────────────────
from .base import BaseRecommendationEngine
from .v1_rule_based import RuleBasedEngineV1
from .registry import get_active_engine, get_shadow_engines, get_engine, EngineNotRegisteredError

__all__ = [
    "BaseRecommendationEngine",
    "RuleBasedEngineV1",
    "get_active_engine",
    "get_shadow_engines",
    "get_engine",
    "EngineNotRegisteredError",
]
