"""
Summary analytics service for analytics.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from analytics.cache.analytics_cache_service import AnalyticsCacheService
from analytics.cache.cache_keys import summary_key
from analytics.repositories.activity_repository import ActivityRepository
from analytics.services.analytics.dto import SummaryAnalyticsDTO
from analytics.settings.defaults import get_cache_timeout
from analytics.typing import ActivityRepositoryProtocol, CacheServiceProtocol

logger = logging.getLogger(__name__)


class SummaryAnalyticsService:
    """
    Provides summary metrics for today and the current week.

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

    def analytics_summary(self) -> SummaryAnalyticsDTO:
        """
        Return summary metrics for today and the current ISO week.

        Returns
        -------
        SummaryAnalyticsDTO
        """
        key = summary_key()
        return self._cache.get_or_set(
            key,
            self._compute,
            timeout=get_cache_timeout(),
        )

    def _compute(self) -> SummaryAnalyticsDTO:
        """Query repository for today and weekly summary metrics."""
        now = timezone.now()
        repo = self._repo

        # Today: midnight to now
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now

        # Week: last 7 days
        week_start = now - timedelta(days=7)
        week_end = now

        today_visits = repo.count_total_visits(today_start, today_end)
        today_unique_ips = repo.count_unique_ips(today_start, today_end)
        today_rt = repo.get_response_time_stats(today_start, today_end)
        today_avg_rt = today_rt.get("avg")

        week_visits = repo.count_total_visits(week_start, week_end)
        week_unique_ips = repo.count_unique_ips(week_start, week_end)

        return SummaryAnalyticsDTO(
            today_visits=today_visits,
            today_unique_ips=today_unique_ips,
            today_average_response_time=round(today_avg_rt, 2)
            if today_avg_rt is not None
            else None,
            week_total_visits=week_visits,
            week_total_unique_ips=week_unique_ips,
        )
