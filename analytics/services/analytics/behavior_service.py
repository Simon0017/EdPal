"""
Behavior analytics service for analytics.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from analytics.cache.analytics_cache_service import AnalyticsCacheService
from analytics.cache.cache_keys import behavior_key
from analytics.repositories.activity_repository import ActivityRepository
from analytics.services.analytics.aggregations.sessions import (
    compute_session_metrics,
)
from analytics.services.analytics.aggregations.traffic import (
    compute_total_from_distribution,
    normalise_distribution_percentages,
)
from analytics.services.analytics.dto import (
    BehaviorAnalyticsDTO,
    DistributionRow,
    HourlyActivityPoint,
)
from analytics.settings.defaults import get_cache_timeout
from analytics.typing import ActivityRepositoryProtocol, CacheServiceProtocol

logger = logging.getLogger(__name__)

# Behavior analytics uses a slightly longer TTL (10 minutes)
_BEHAVIOR_CACHE_TIMEOUT = 600


class BehaviorAnalyticsService:
    """
    Computes user behavior analytics for a given date range.

    Parameters
    ----------
    repository:
        Activity repository.
    cache_service:
        Cache service.
    """

    def __init__(
        self,
        repository: Optional[ActivityRepositoryProtocol] = None,
        cache_service: Optional[CacheServiceProtocol] = None,
    ) -> None:
        self._repo: ActivityRepositoryProtocol = repository or ActivityRepository()
        self._cache: CacheServiceProtocol = cache_service or AnalyticsCacheService()

    def get_behavior_data(
        self, start: datetime, end: datetime
    ) -> BehaviorAnalyticsDTO:
        """
        Return user behavior analytics for [*start*, *end*].

        Parameters
        ----------
        start:
            Period start (timezone-aware).
        end:
            Period end (timezone-aware).
        """
        key = behavior_key(start, end)
        return self._cache.get_or_set(
            key,
            lambda: self._compute(start, end),
            timeout=_BEHAVIOR_CACHE_TIMEOUT,
        )

    def _compute(self, start: datetime, end: datetime) -> BehaviorAnalyticsDTO:
        repo = self._repo

        # Top 5 browsers
        raw_browsers = repo.get_browser_distribution(start, end, limit=5)
        total_browsers = compute_total_from_distribution(raw_browsers)
        browser_rows = normalise_distribution_percentages(raw_browsers, total_browsers)
        browsers = [
            DistributionRow(
                label=row["browser_family"],
                count=row["count"],
                percentage=row["percentage"],
            )
            for row in browser_rows
        ]

        # Top 5 operating systems
        raw_os = repo.get_os_distribution(start, end, limit=5)
        total_os = compute_total_from_distribution(raw_os)
        os_rows = normalise_distribution_percentages(raw_os, total_os)
        operating_systems = [
            DistributionRow(
                label=row["os_family"],
                count=row["count"],
                percentage=row["percentage"],
            )
            for row in os_rows
        ]

        # Hourly activity
        raw_hourly = repo.get_hourly_activity(start, end)
        hourly = [
            HourlyActivityPoint(hour=row["hour"], count=row["count"])
            for row in raw_hourly
        ]

        # Session metrics
        session_metrics = compute_session_metrics(repo, start, end)

        # AJAX vs regular
        ajax_dist = repo.get_ajax_distribution(start, end)

        return BehaviorAnalyticsDTO(
            top_5_browsers=browsers,
            top_5_operating_systems=operating_systems,
            activity_by_hour=hourly,
            average_session_duration_seconds=round(
                session_metrics["average_session_duration_seconds"], 2
            ),
            average_page_views_per_session=round(
                session_metrics["average_page_views_per_session"], 2
            ),
            average_unique_paths_per_session=round(
                session_metrics["average_unique_paths_per_session"], 2
            ),
            ajax_vs_regular_requests=ajax_dist,
        )
