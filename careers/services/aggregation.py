# ── NEW FILE: careers/services/aggregation.py ────────────────────────────
"""
Pipeline stages 3-4 (Feature Extraction / Tag Aggregation) from the
architecture doc.

Feature extraction is actually done by the evidence selectors (they
already emit TagEvidence, i.e. extracted features) — this module's job
is AGGREGATION: merging potentially-many TagEvidence rows per tag into
one AggregatedTagScore per tag, using a weighted average (not a sum) so
a tag with 10 low-signal questions doesn't drown out a tag with 1
high-signal one.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from careers.models import UserTagVector
from careers.services.types import TagEvidence, AggregatedTagScore

ZERO = Decimal("0")


def aggregate_tag_evidence(evidence: list[TagEvidence]) -> dict[int, AggregatedTagScore]:
    """
    Merges TagEvidence rows into one AggregatedTagScore per tag_id.

    affinity_score = weighted average of (raw_signal * source_weight),
    weighted by source_confidence — i.e. more-trusted sources pull the
    average toward themselves more.

    confidence for the merged tag score is NOT just an average of the
    individual confidences: it also rewards agreement (low variance)
    across sources and evidence volume. See services/scoring.py's
    compute_confidence() for the full recommendation-level confidence
    methodology (Part 4) — this is the tag-level building block for it.
    """
    grouped: dict[int, list[TagEvidence]] = defaultdict(list)
    for item in evidence:
        grouped[item.tag_id].append(item)

    result: dict[int, AggregatedTagScore] = {}
    for tag_id, items in grouped.items():
        weighted_values = []
        weights = []
        for e in items:
            effective_signal = clamp01(e.raw_signal * e.source_weight)
            trust = e.source_confidence
            weighted_values.append(effective_signal * trust)
            weights.append(trust)

        total_weight = sum(weights, ZERO)
        if total_weight == ZERO:
            affinity = ZERO
        else:
            affinity = sum(weighted_values, ZERO) / total_weight

        agreement = _agreement_factor(items)
        volume = _volume_factor(len(items))
        tag_confidence = clamp01(agreement * volume)

        result[tag_id] = AggregatedTagScore(
            tag_id=tag_id,
            affinity_score=affinity.quantize(Decimal("0.0001")),
            confidence=tag_confidence.quantize(Decimal("0.0001")),
            evidence_count=len(items),
        )
    return result


def _agreement_factor(items: list[TagEvidence]) -> Decimal:
    """
    1.0 when all sources for this tag agree closely, lower when they
    diverge. Single-source tags get a neutral 0.75 rather than 1.0 —
    one source alone shouldn't look as trustworthy as several agreeing
    sources.
    """
    if len(items) == 1:
        return Decimal("0.75")
    values = [float(clamp01(e.raw_signal * e.source_weight)) for e in items]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    # variance in [0, 0.25] roughly for values in [0,1]; map to [1.0, 0.4]
    penalty = min(Decimal(str(variance)) * Decimal("2.4"), Decimal("0.6"))
    return clamp01(Decimal("1.0") - penalty)


def _volume_factor(evidence_count: int) -> Decimal:
    """
    Bayesian-style shrinkage toward caution for low evidence volume.
    Saturates at 5+ independent sources for a single tag.
    """
    saturation_point = 5
    return clamp01(Decimal(min(evidence_count, saturation_point)) / Decimal(saturation_point))


def clamp01(value: Decimal) -> Decimal:
    return max(ZERO, min(Decimal("1"), value))


@transaction.atomic
def persist_user_tag_vector(profile, aggregated: dict[int, AggregatedTagScore], algorithm_version: str) -> None:
    """
    Upserts UserTagVector rows for a profile. Uses bulk_create with
    update_conflicts so this stays a single round-trip regardless of
    how many tags the user has evidence for (Postgres 13+/MySQL 8+;
    Django 4.1+ required for update_conflicts).

    Tags with NO current evidence are intentionally left untouched
    rather than zeroed out — a tag that had strong evidence a year ago
    and none since should decay via recency weighting upstream (in a
    future version), not be silently wiped by an unrelated aggregation
    run that simply didn't touch it this time.
    """
    now = timezone.now()
    rows = [
        UserTagVector(
            profile=profile,
            tag_id=tag_id,
            affinity_score=score.affinity_score,
            confidence=score.confidence,
            evidence_count=score.evidence_count,
            algorithm_version=algorithm_version,
            last_updated=now,
        )
        for tag_id, score in aggregated.items()
    ]
    if not rows:
        return

    UserTagVector.objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=["profile", "tag"],
        update_fields=["affinity_score", "confidence", "evidence_count", "algorithm_version", "last_updated"],
    )
