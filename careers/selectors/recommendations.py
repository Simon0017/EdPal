# ── NEW FILE: careers/selectors/recommendations.py ───────────────────────
"""
Read-only queries over CareerRecommendation history and feedback.
"""
from __future__ import annotations

from careers.models import CareerRecommendation


def get_latest_recommendation(profile, algorithm_version: str | None = None):
    """
    Latest recommendation for a profile, optionally scoped to a specific
    engine version (useful for shadow-mode comparisons).

    ADJUST: assumes CareerRecommendation has `profile` (or `user`) and
    `generated_at` (or `created_at`) fields — align with Part 1's
    MIGRATION_NOTES.md index snippet, which assumes the same names.
    """
    qs = CareerRecommendation.objects.filter(user=profile)
    if algorithm_version:
        qs = qs.filter(algorithm_version=algorithm_version)
    return qs.order_by("-generated_at").first()


def get_recommendation_history(profile, limit: int = 20):
    return (
        CareerRecommendation.objects
        .filter(profile=profile)
        .order_by("-generated_at")[:limit]
    )


def get_pending_recommendations(limit: int = 100):
    """Used by monitoring/retry tooling — jobs stuck in a non-terminal state."""
    return (
        CareerRecommendation.objects
        .filter(processing_status__in=["PENDING", "PROCESSING"])
        .order_by("generated_at")[:limit]
    )
