# ── NEW FILE: careers/selectors/engine.py ────────────────────────────────
"""
Read-only queries over the EngineVersion registry.
"""
from __future__ import annotations

from careers.models import EngineVersion


def get_active_engine_version() -> EngineVersion:
    """
    The single engine version used for user-facing recommendation jobs.
    Raises EngineVersion.DoesNotExist if nothing is marked active — this
    is intentional: a misconfigured registry should fail loudly rather
    than silently falling back to an arbitrary version.
    """
    return EngineVersion.objects.get(is_active=True)


def get_shadow_engine_versions() -> list[EngineVersion]:
    """Engine versions running in parallel for evaluation, never user-facing."""
    return list(EngineVersion.objects.filter(is_shadow=True))


def get_engine_version(version_number: str) -> EngineVersion:
    return EngineVersion.objects.get(version_number=version_number)
