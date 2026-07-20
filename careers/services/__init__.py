# ── NEW FILE: careers/services/__init__.py ───────────────────────────────
"""
Write/business-logic layer. Each submodule maps to one or more stages of
the recommendation pipeline documented in the architecture doc (Part 3).

Submodules are imported here so callers can do:
    from careers.services import normalization, aggregation, scoring, explanation, persistence, emails
    from careers.services.engine import get_engine, RuleBasedEngineV1
"""
from . import types
from . import normalization
from . import aggregation
from . import scoring
from . import explanation
from . import persistence
from . import emails
from . import engine

__all__ = [
    "types",
    "normalization",
    "aggregation",
    "scoring",
    "explanation",
    "persistence",
    "emails",
    "engine",
]
