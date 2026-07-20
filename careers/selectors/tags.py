# ── NEW FILE: careers/selectors/tags.py ──────────────────────────────────
"""
Read-only queries for career-side and tag-side data used during scoring:
career tag vectors, tag relationships, and the cached UserTagVector.
"""
from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache

from careers.models import CareerTag, UserTagVector
from core.models import TagRelationship

ALL_CAREER_VECTORS_CACHE_KEY = "recsys:all_career_tag_vectors"
ALL_CAREER_VECTORS_CACHE_TTL = 60 * 60 * 6  # 6 hours — invalidated sooner on CareerTag change, see signals.py


def get_career_tag_vector(career_id: int) -> dict[int, Decimal]:
    """Returns {tag_id: recommendation_weight} for a single career."""
    rows = CareerTag.objects.filter(career_id=career_id).values_list("tag_id", "recommendation_weight")
    return {tag_id: Decimal(str(weight)) for tag_id, weight in rows}


def get_all_career_tag_vectors() -> dict[int, dict[int, Decimal]]:
    """
    Returns {career_id: {tag_id: recommendation_weight}} for every
    career in one query — used by the ranking stage instead of N+1
    querying get_career_tag_vector() per career.

    Cache-aside: this is read on every single recommendation job but
    changes only when an admin edits CareerTag weights, so it's cached
    for ALL_CAREER_VECTORS_CACHE_TTL and explicitly invalidated by a
    signal on CareerTag save/delete (see careers/signals.py) rather than
    relying on the TTL alone — Part 8 of the architecture doc flagged
    this exact query as a scalability risk if recomputed per job.

    Cached values are stored as {career_id: {tag_id: str(weight)}} —
    Decimal isn't JSON-serializable by django-redis's default pickle
    backend it usually is fine, but str() round-tripping keeps this
    cache-backend-agnostic (works with non-pickle backends too).
    """
    cached = cache.get(ALL_CAREER_VECTORS_CACHE_KEY)
    if cached is not None:
        return {
            career_id: {tag_id: Decimal(w) for tag_id, w in tag_map.items()}
            for career_id, tag_map in cached.items()
        }

    result: dict[int, dict[int, Decimal]] = {}
    rows = CareerTag.objects.select_related(None).values_list("career_id", "tag_id", "recommendation_weight")
    for career_id, tag_id, weight in rows:
        result.setdefault(career_id, {})[tag_id] = Decimal(str(weight))

    serializable = {cid: {tid: str(w) for tid, w in tmap.items()} for cid, tmap in result.items()}
    cache.set(ALL_CAREER_VECTORS_CACHE_KEY, serializable, timeout=ALL_CAREER_VECTORS_CACHE_TTL)
    return result


def invalidate_career_tag_vector_cache() -> None:
    cache.delete(ALL_CAREER_VECTORS_CACHE_KEY)


def get_cached_user_tag_vector(profile) -> dict[int, tuple[Decimal, Decimal, int]]:
    """
    Returns the CURRENTLY PERSISTED UserTagVector for a profile as
    {tag_id: (affinity_score, confidence, evidence_count)}.

    This is a READ of the cache — use this when you only need to rank
    against the last-computed vector (e.g. for a shadow engine
    comparison) without re-running aggregation.
    """
    rows = UserTagVector.objects.filter(profile=profile).values_list(
        "tag_id", "affinity_score", "confidence", "evidence_count"
    )
    return {tag_id: (Decimal(str(a)), Decimal(str(c)), n) for tag_id, a, c, n in rows}


def get_tag_relationship_strengths(tag_ids: list[int]) -> dict[tuple[int, int], Decimal]:
    """
    Returns {(from_tag_id, to_tag_id): strength} for RELATED/COMPLEMENTARY
    relationships among the given tags — used by explanation generation
    to surface "and related to X" context, and optionally by scoring to
    give partial credit for adjacent tags (not enabled by default in V1;
    see services/scoring.py for the extension point).
    """
    rows = (
        TagRelationship.objects
        .filter(from_tag_id__in=tag_ids, to_tag_id__in=tag_ids)
        .values_list("from_tag_id", "to_tag_id", "strength")
    )
    return {(f, t): Decimal(str(s)) for f, t, s in rows}
