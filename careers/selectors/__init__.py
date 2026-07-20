# ── careers/selectors/__init__.py ──────────────────────────────
"""
Read-only query layer. Nothing in this package writes to the database
or contains scoring/business logic — see careers/services/ for that.

Submodules are imported here so callers can do:
    from careers.selectors import evidence, tags, recommendations, engine
without needing to know the internal file layout.
"""
from . import evidence
from . import tags
from . import recommendations
from . import engine

__all__ = ["evidence", "tags", "recommendations", "engine"]
