# ── NEW FILE: careers/services/scoring.py ────────────────────────────────
"""
Pipeline stages 5-7 (Weighting / Confidence Computation / Career Ranking)
from the architecture doc.

Similarity: weighted cosine similarity between the user's tag vector and
each career's tag vector. Chosen over a plain dot product because it's
invariant to a career simply having more/heavier tags overall — a
career with 30 well-weighted tags shouldn't automatically outrank one
with 8 tightly-relevant ones purely on vector magnitude.

Confidence: implements the Part 4 methodology as a geometric mean of
independent factors, so any single badly-deficient factor (e.g. zero
tag coverage) meaningfully suppresses the result rather than being
averaged away by the others.
"""
from __future__ import annotations

import math
from decimal import Decimal

import numpy as np

from careers.services.types import AggregatedTagScore, RankedCareer

ZERO = Decimal("0")
ONE = Decimal("1")


def clamp01(value: Decimal) -> Decimal:
    return max(ZERO, min(ONE, value))


def weighted_cosine_similarity(
    user_vector: dict[int, AggregatedTagScore],
    career_vector: dict[int, Decimal],
) -> Decimal:
    """
    Cosine similarity over the union of tags referenced by either side.
    Missing tags on either side contribute 0, which is exactly what
    cosine similarity needs (no imputation required).
    """
    tag_ids = set(user_vector) | set(career_vector)
    if not tag_ids:
        return ZERO

    ordered = sorted(tag_ids)
    u = np.array([float(user_vector[t].affinity_score) if t in user_vector else 0.0 for t in ordered])
    c = np.array([float(career_vector[t]) if t in career_vector else 0.0 for t in ordered])

    denom = np.linalg.norm(u) * np.linalg.norm(c)
    if denom == 0:
        return ZERO
    similarity = float(np.dot(u, c) / denom)
    return clamp01(Decimal(str(round(similarity, 6))))


def compute_confidence(
    user_vector: dict[int, AggregatedTagScore],
    career_vector: dict[int, Decimal],
    fit_score: Decimal,
    all_fit_scores: list[Decimal],
) -> Decimal:
    """
    Part 4 confidence methodology. Factors:

    1. coverage_factor   — fraction of this career's tags the user has ANY evidence for
    2. agreement_factor  — average per-tag confidence (already encodes source
                            agreement + evidence volume — see aggregation.py)
    3. career_density_factor — thinly-tagged careers (<8 tags) get penalized,
                            since a sparse career-side vector is itself a
                            weaker basis for a confident match
    4. margin_factor     — how much this career's score stands out from the
                            next-best alternative

    Combined via geometric mean so a single very-low factor drags the
    whole result down, rather than being diluted by the others.
    """
    tag_ids = list(career_vector.keys())
    if not tag_ids:
        return ZERO

    covered = [t for t in tag_ids if t in user_vector]
    coverage_factor = Decimal(len(covered)) / Decimal(len(tag_ids))

    if covered:
        agreement_factor = sum((user_vector[t].confidence for t in covered), ZERO) / Decimal(len(covered))
    else:
        agreement_factor = ZERO

    career_density_factor = clamp01(Decimal(len(tag_ids)) / Decimal("8"))
    margin_factor = _margin_factor(fit_score, all_fit_scores)

    return _geometric_mean([coverage_factor, agreement_factor, career_density_factor, margin_factor])


def _margin_factor(fit_score: Decimal, all_fit_scores: list[Decimal]) -> Decimal:
    if len(all_fit_scores) < 2:
        return Decimal("1.0")
    top_two = sorted(all_fit_scores, reverse=True)[:2]
    gap = top_two[0] - top_two[1]
    # A tie (gap=0) still gets a 0.5 baseline — being ranked #1 among a
    # tie isn't meaningless, just less distinctive. Gaps of 0.3+ saturate to 1.0.
    return clamp01(Decimal("0.5") + gap)


def _geometric_mean(factors: list[Decimal]) -> Decimal:
    floats = [max(float(f), 0.0) for f in factors]
    if any(f == 0.0 for f in floats):
        return ZERO
    product = math.prod(floats)
    result = product ** (1 / len(floats))
    return clamp01(Decimal(str(round(result, 6))))


def rank_careers(
    user_vector: dict[int, AggregatedTagScore],
    career_vectors: dict[int, dict[int, Decimal]],
) -> list[RankedCareer]:
    """
    Scores every career, then ranks. Returns RankedCareer objects with
    fit_score and confidence_score populated but top_contributing_tags
    left empty — the engine fills that in only for the top N results via
    services/explanation.py, since computing per-tag contribution
    breakdowns for every career (not just the ones shown to the user)
    would be wasted work.
    """
    scored: list[tuple[int, Decimal]] = []
    for career_id, career_vector in career_vectors.items():
        fit_score = weighted_cosine_similarity(user_vector, career_vector)
        scored.append((career_id, fit_score))

    all_scores = [s for _, s in scored]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    ranked = []
    for rank, (career_id, fit_score) in enumerate(scored, start=1):
        confidence = compute_confidence(user_vector, career_vectors[career_id], fit_score, all_scores)
        ranked.append(
            RankedCareer(
                career_id=career_id,
                rank=rank,
                fit_score=fit_score,
                confidence_score=confidence,
                top_contributing_tags=[],
            )
        )
    return ranked
