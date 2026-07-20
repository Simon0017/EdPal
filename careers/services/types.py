# ── NEW FILE: careers/services/types.py ──────────────────────────────────
"""
Shared data contracts used across selectors, services, and every engine
version. These are the "seam" described in Part 7 of the architecture
doc: every engine version (V1 rule-based today, V3 learning-to-rank or
V4 embedding-based later) must produce an EngineResult — nothing
downstream (persistence, email, Celery orchestration) is allowed to
depend on how that result was produced.

Deliberately plain dataclasses, not Django models — these are in-memory
transfer objects for a single pipeline run, not persisted rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class TagEvidence:
    """
    One piece of raw evidence linking a profile to a tag, before
    aggregation. Produced by selectors/evidence.py, consumed by
    services/aggregation.py.
    """
    tag_id: int
    raw_signal: Decimal          # 0.0-1.0, already normalized (see normalization.py)
    source_type: str             # matches core.TagSourceType choices
    source_id: int
    source_confidence: Decimal   # 0.0-1.0 — how much to trust this particular evidence row
    source_weight: Decimal = Decimal("1.0")  # e.g. QuestionnaireTag.coupling_strength


@dataclass(frozen=True)
class AggregatedTagScore:
    """
    One tag's aggregated affinity for a profile, after aggregation +
    weighting. Maps 1:1 onto a UserTagVector row.
    """
    tag_id: int
    affinity_score: Decimal
    confidence: Decimal
    evidence_count: int


@dataclass(frozen=True)
class RankedCareer:
    """One scored, ranked career for a single recommendation run."""
    career_id: int
    rank: int
    fit_score: Decimal
    confidence_score: Decimal
    top_contributing_tags: list[dict] = field(default_factory=list)
    # e.g. [{"tag_id": 5, "tag_title": "Statistics", "contribution": 0.31}, ...]


@dataclass(frozen=True)
class EngineResult:
    """
    The ONE output contract every engine version must return from
    .generate(profile). Persistence, email generation, and Celery
    orchestration are written against this contract only — never
    against a specific engine's internals (Part 5 / Part 7).
    """
    profile_id: int
    algorithm_version: str
    ranked_careers: list[RankedCareer]
    generated_at_iso: str
    is_shadow: bool = False
