# ── NEW FILE: careers/services/engine/v1_rule_based.py ───────────────────
"""
Engine V1: deterministic, weighted-graph / rule-based scoring — the
approach justified in Part 1 of the architecture doc. Pure orchestration:
every actual computation is delegated to services/* so those functions
stay independently testable and independently reusable by later engine
versions (a V3 learning-to-rank engine still calls
aggregation.aggregate_tag_evidence(), for example — it just does
something different at the ranking stage).
"""
from __future__ import annotations

from django.utils import timezone

from careers.selectors.tags import get_all_career_tag_vectors
from careers.services.aggregation import aggregate_tag_evidence, persist_user_tag_vector
from careers.services.scoring import rank_careers
from careers.services.engine.base import BaseRecommendationEngine
from careers.services.types import EngineResult

ENGINE_VERSION = "v1.0.0"


class RuleBasedEngineV1(BaseRecommendationEngine):
    version = ENGINE_VERSION
    engine_type = "RULE_BASED"

    def generate(self, profile, *, is_shadow: bool = False) -> EngineResult:
        from careers.selectors.evidence import collect_all_evidence
        # Stage 1-2: input sources + normalization happen inside the
        # evidence selectors (selectors/evidence.py normalizes as it reads).
        evidence = collect_all_evidence(profile)

        # Stage 3-4: feature extraction (already done by selectors) + aggregation.
        aggregated = aggregate_tag_evidence(evidence)

        # Persist the materialized UserTagVector — this is the cache every
        # future engine version reads instead of re-running aggregation.
        persist_user_tag_vector(profile, aggregated, self.version)

        # Stage 5-7: weighting (baked into aggregation), confidence, ranking.
        career_vectors = get_all_career_tag_vectors()
        if not career_vectors:
            raise RuntimeError(
                "No CareerTag rows exist — cannot rank careers. Seed CareerTag "
                "before running the recommendation engine."
            )
        ranked = rank_careers(aggregated, career_vectors)

        return EngineResult(
            profile_id=profile.id,
            algorithm_version=self.version,
            ranked_careers=ranked,
            generated_at_iso=timezone.now().isoformat(),
            is_shadow=is_shadow,
        )
