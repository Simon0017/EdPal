# ── NEW FILE: careers/services/engine/registry.py ────────────────────────
"""
Registry mapping EngineVersion.version_number -> engine implementation
class (Part 5 of the architecture doc).

Adding a future engine version is a two-step, additive change:
  1. Implement a new BaseRecommendationEngine subclass (e.g. v3_ltr.py).
  2. Add one line to _ENGINE_CLASSES below.
No existing code path changes — Celery tasks call get_active_engine()
and never reference a class name directly.
"""
from __future__ import annotations

from careers.services.engine.base import BaseRecommendationEngine
from careers.services.engine.v1_rule_based import RuleBasedEngineV1
from careers.selectors.engine import get_active_engine_version, get_shadow_engine_versions, get_engine_version

# version_number (as stored on EngineVersion / CareerRecommendation.algorithm_version)
# -> engine class. Register every future version here (V2, V3, V4...).
_ENGINE_CLASSES: dict[str, type[BaseRecommendationEngine]] = {
    RuleBasedEngineV1.version: RuleBasedEngineV1,
}


class EngineNotRegisteredError(Exception):
    """Raised when an EngineVersion row exists in the DB with no matching code."""


def _instantiate(version_number: str) -> BaseRecommendationEngine:
    engine_class = _ENGINE_CLASSES.get(version_number)
    if engine_class is None:
        raise EngineNotRegisteredError(
            f"EngineVersion '{version_number}' has no corresponding class in "
            f"careers.services.engine.registry._ENGINE_CLASSES. Register it "
            f"before activating this version in the admin."
        )
    return engine_class()


def get_active_engine() -> BaseRecommendationEngine:
    """The engine used for real, user-facing recommendation jobs."""
    version = get_active_engine_version()
    return _instantiate(version.version_number)


def get_shadow_engines() -> list[BaseRecommendationEngine]:
    """Engines running in parallel for evaluation, never user-facing."""
    versions = get_shadow_engine_versions()
    return [_instantiate(v.version_number) for v in versions]


def get_engine(version_number: str) -> BaseRecommendationEngine:
    """Fetch a specific engine version by its version string (e.g. for backtesting)."""
    get_engine_version(version_number)  # raises EngineVersion.DoesNotExist if unknown to the DB
    return _instantiate(version_number)
