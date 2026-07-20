# ── NEW FILE: careers/services/persistence.py ────────────────────────────
"""
Pipeline stage 9 (Recommendation Persistence) from the architecture doc.

Writes are wrapped in a single transaction: a recommendation run either
fully lands (CareerRecommendation + its RecommendationExplanation rows)
or not at all — a partially-written recommendation is worse than a
missing one, since downstream code (email, analytics) assumes
completeness once processing_status == COMPLETED.

ADJUST: field names on CareerRecommendation (`profile`, `generated_at`,
`processing_status`, `confidence_score`, `recommendation_details`,
`email_status`) are assumed per the original architecture brief —
align with your actual model.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from careers.models import CareerRecommendation, RecommendationExplanation, ExplanationType
from careers.services.types import EngineResult
from careers.services.explanation import top_contributing_tags, build_narrative_summary
from careers.selectors.tags import get_all_career_tag_vectors


EXPLAIN_TOP_N = 5  # only the top N careers get a full explanation breakdown


@transaction.atomic
def persist_recommendation(
    profile,
    engine_result: EngineResult,
    user_vector,
) -> CareerRecommendation:
    """
    Persists an EngineResult as a CareerRecommendation row plus
    RecommendationExplanation rows for the top N careers.

    Overall confidence_score on the CareerRecommendation row is the
    top-ranked career's confidence — representing "how confident are we
    in THE recommendation", i.e. the headline result, not an average
    across the full ranked list.
    """
    from careers.models import Career  # local import to avoid app-loading order issues

    ranked = engine_result.ranked_careers
    top_confidence = ranked[0].confidence_score if ranked else 0

    recommendation = CareerRecommendation.objects.create(
        user=profile,
        algorithm_version=engine_result.algorithm_version,
        confidence_score=top_confidence,
        processing_status="COMPLETED",
        recommendation_details={
            "generated_at": engine_result.generated_at_iso,
            "is_shadow": engine_result.is_shadow,
            "ranked_careers": [
                {
                    "career_id": rc.career_id,
                    "rank": rc.rank,
                    "fit_score": float(rc.fit_score),
                    "confidence_score": float(rc.confidence_score),
                }
                for rc in ranked
            ],
        },
        generated_at=timezone.now(),
    )

    if not engine_result.is_shadow and ranked:
        career_vectors = get_all_career_tag_vectors()
        career_titles = dict(
            Career.objects.filter(id__in=[rc.career_id for rc in ranked[:EXPLAIN_TOP_N]]).values_list("id", "title")
        )

        explanation_rows = []
        for rc in ranked[:EXPLAIN_TOP_N]:
            career_vector = career_vectors.get(rc.career_id, {})
            top_tags = top_contributing_tags(user_vector, career_vector, limit=5)
            narrative = build_narrative_summary(top_tags, career_titles.get(rc.career_id, "this career"))

            explanation_rows.append(
                RecommendationExplanation(
                    recommendation=recommendation,
                    explanation_type=ExplanationType.TAG_CONTRIBUTION,
                    explanation_data={
                        "career_id": rc.career_id,
                        "rank": rc.rank,
                        "top_tags": top_tags,
                    },
                    explanation_version="1.0.0",
                )
            )
            explanation_rows.append(
                RecommendationExplanation(
                    recommendation=recommendation,
                    explanation_type=ExplanationType.NARRATIVE,
                    explanation_data={"career_id": rc.career_id, "text": narrative},
                    explanation_version="1.0.0",
                )
            )

        RecommendationExplanation.objects.bulk_create(explanation_rows)

    return recommendation
