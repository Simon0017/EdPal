# ── NEW FILE: careers/services/engine/base.py ────────────────────────────
"""
The engine contract from Part 5 / Part 7 of the architecture doc.

Every recommendation engine version — today's rule-based V1, tomorrow's
hybrid V3, eventually an embedding-based V4 — must subclass this and
implement .generate(). Nothing outside this file (Celery tasks,
persistence, email) is allowed to depend on which subclass is running.
This is the seam that lets the engine evolve without touching business
logic elsewhere.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from careers.services.types import EngineResult


class BaseRecommendationEngine(ABC):
    """
    version and engine_type are set by subclasses and should correspond
    exactly to an EngineVersion.version_number / engine_type row — the
    registry (registry.py) is what enforces that correspondence.
    """
    version: str
    engine_type: str

    @abstractmethod
    def generate(self, profile, *, is_shadow: bool = False) -> EngineResult:
        """
        Runs the full pipeline for one profile and returns an
        EngineResult. MUST NOT persist anything itself — persistence is
        the caller's responsibility (services/persistence.py), so the
        same engine can be used for a real run, a shadow run, or a
        dry-run preview without behavioral duplication.
        """
        raise NotImplementedError
