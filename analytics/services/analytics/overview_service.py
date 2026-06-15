"""
Overview analytics service for analytics.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from analytics.cache.analytics_cache_service import AnalyticsCacheService
from analytics.cache.cache_keys import overview_key
from analytics.repositories.activity_repository import ActivityRepository
from analytics.services.analytics.aggregations.visitors import (
    compute_visitor_novelty,
    compute_visitor_type_distribution,
)
from analytics.services.analytics.dto import (
    DailyVisitPoint,
    OverviewAnalyticsDTO,
)
from analytics.settings.defaults import get_cache_timeout
from analytics.typing import ActivityRepositoryProtocol, CacheServiceProtocol

logger = logging.getLogger(__name__)


class OverviewAnalyticsService:
    """
    Computes overview-level analytics for a given date range.

    Parameters
    ----------
    repository:
        Activity repository.  Defaults to :class:`ActivityRepository`.
    cache_service:
        Cache service.  Defaults to :class:`AnalyticsCacheService`.
    """

    def __init__(
        self,
        repository: Optional[ActivityRepositoryProtocol] = None,
        cache_service: Optional[CacheServiceProtocol] = None,
    ) -> None:
        self._repo: ActivityRepositoryProtocol = repository or ActivityRepository()
        self._cache: CacheServiceProtocol = cache_service or AnalyticsCacheService()

    def get_overview_data(
        self, start: datetime, end: datetime
    ) -> OverviewAnalyticsDTO:
        """
        Return overview analytics for the period [*start*, *end*].

        Results are cached using the standard analytics cache timeout.

        Parameters
        ----------
        start:
            Period start (timezone-aware).
        end:
            Period end (timezone-aware).

        Returns
        -------
        OverviewAnalyticsDTO
        """
        key = overview_key(start, end)
        return self._cache.get_or_set(
            key,
            lambda: self._compute(start, end),
            timeout=get_cache_timeout(),
        )

    # ------------------------------------------------------------------
    # Internal computation
    # ------------------------------------------------------------------

    def _compute(self, start: datetime, end: datetime) -> OverviewAnalyticsDTO:
        """Perform all repository queries and assemble the DTO."""
        repo = self._repo

        total_visits = repo.count_total_visits(start, end)
        unique_visitors = repo.count_unique_ips(start, end)
        unique_users = repo.count_unique_users(start, end)
        auth_visits = repo.count_authenticated_visits(start, end)
        anon_visits = repo.count_anonymous_visits(start, end)

        rt_stats = repo.get_response_time_stats(start, end)
        avg_rt = rt_stats.get("avg")
        max_rt = rt_stats.get("max")
        min_rt = rt_stats.get("min")

        novelty = compute_visitor_novelty(repo, start, end)
        visitor_type = compute_visitor_type_distribution(repo, start, end)

        daily_raw = repo.get_daily_visit_counts(start, end)
        daily_trend = [
            DailyVisitPoint(
                date=row["date"].strftime("%Y-%m-%d")
                if hasattr(row["date"], "strftime")
                else str(row["date"]),
                count=row["count"],
            )
            for row in daily_raw
        ]

        return OverviewAnalyticsDTO(
            total_visits=total_visits,
            unique_visitors=unique_visitors,
            unique_users=unique_users,
            new_visitors=novelty["new"],
            returning_visitors=novelty["returning"],
            average_response_time_ms=round(avg_rt, 2) if avg_rt is not None else None,
            max_response_time_ms=max_rt,
            min_response_time_ms=min_rt,
            authenticated_visits=auth_visits,
            anonymous_visits=anon_visits,
            daily_visits_trend=daily_trend,
            visitor_type_distribution=visitor_type,
        )
