# ── NEW FILE: careers/services/explanation.py ────────────────────────────
"""
Pipeline stage 8 (Explanation Generation) from the architecture doc.

Deliberately derived from the SAME vectors used for scoring — no
separate black-box explainer is needed because the scoring mechanism is
itself interpretable (Part 1's central argument for choosing a
weighted-graph approach). This module just formats that interpretation.
"""
from __future__ import annotations

from decimal import Decimal

from core.models import Tag
from careers.services.types import AggregatedTagScore


def top_contributing_tags(
    user_vector: dict[int, AggregatedTagScore],
    career_vector: dict[int, Decimal],
    limit: int = 5,
) -> list[dict]:
    """
    Ranks the tags shared between user and career by their CONTRIBUTION
    to the match — user_affinity * career_weight — not just by raw user
    affinity or raw career weight alone, since a tag the user is strong
    in but the career barely cares about shouldn't top the explanation.
    """
    shared_tag_ids = set(user_vector) & set(career_vector)
    if not shared_tag_ids:
        return []

    contributions = []
    for tag_id in shared_tag_ids:
        user_score = user_vector[tag_id]
        career_weight = career_vector[tag_id]
        contribution = user_score.affinity_score * career_weight
        contributions.append((tag_id, contribution, user_score))

    contributions.sort(key=lambda triple: triple[1], reverse=True)
    top = contributions[:limit]

    tag_titles = dict(Tag.objects.filter(id__in=[t[0] for t in top]).values_list("id", "title"))

    return [
        {
            "tag_id": tag_id,
            "tag_title": tag_titles.get(tag_id, "Unknown"),
            "contribution": float(contribution.quantize(Decimal("0.0001"))),
            "user_affinity": float(user_score.affinity_score),
            "evidence_count": user_score.evidence_count,
        }
        for tag_id, contribution, user_score in top
    ]


def build_narrative_summary(top_tags: list[dict], career_title: str) -> str:
    """
    Short, deterministic natural-language summary — a template, not an
    LLM call. Part 7 of the architecture doc explicitly scopes LLM
    reasoning to an OPTIONAL, separate explanation_type layered on top
    of this structured data later, not a replacement for it.
    """
    if not top_tags:
        return f"Limited overlapping evidence was found for {career_title}."
    names = [t["tag_title"] for t in top_tags[:3]]
    if len(names) == 1:
        joined = names[0]
    elif len(names) == 2:
        joined = f"{names[0]} and {names[1]}"
    else:
        joined = f"{', '.join(names[:-1])}, and {names[-1]}"
    return f"This match is driven primarily by your evidenced strength in {joined}."
