# ── NEW FILE: careers/services/normalization.py ──────────────────────────
"""
Pipeline stage 2 (Normalization) from the architecture doc.

Evidence selectors already return values in a roughly 0-1 range (see
selectors/evidence.py), but this module is the single place where
normalization RULES live, so they can be tuned without touching query
code or aggregation code. Kept deliberately tiny and pure — no I/O.
"""
from __future__ import annotations

from decimal import Decimal

ZERO = Decimal("0")
ONE = Decimal("1")


def clamp(value: Decimal, low: Decimal = ZERO, high: Decimal = ONE) -> Decimal:
    return max(low, min(high, value))


def normalize_grade(grade: Decimal, max_grade: Decimal = Decimal("100")) -> Decimal:
    """Normalizes an academic grade to 0-1."""
    if max_grade == 0:
        return ZERO
    return clamp(grade / max_grade)


def normalize_percentage(percentage: Decimal) -> Decimal:
    """AttemptScore.percentage (0-100) -> 0-1."""
    return clamp(percentage / Decimal("100"))


def normalize_psychometric_weight(weight: Decimal, max_weight: Decimal = Decimal("1.0")) -> Decimal:
    """CareerPsychometricChoice.weight -> 0-1, in case source weights aren't pre-scaled."""
    if max_weight == 0:
        return ZERO
    return clamp(weight / max_weight)
