"""
Realtime analytics service for analytics.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from analytics.cache.analytics_cache_service import AnalyticsCacheService
from analytics.cache.cache_keys import realtime_key
from analytics.constants import REALTIME_WINDOW_MINUTES
from analytics.repositories.activity_repository import ActivityRepository
from analytics.services.analytics.dto import RealtimeAnalyticsDTO
from analytics.typing import ActivityRepositoryProtocol, CacheServiceProtocol

logger = logging.getLogger(__name__)


class RealtimeAnalyticsService:
    """
    Provides near-real-time analytics based on a rolling time window.

    The window defaults to the last 5 minutes from the moment of the call.
    Results are cached with a short TTL (configured via
    ``analytics_REALTIME_CACHE_TIMEOUT``).

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

    def get_realtime_stats(self) -> RealtimeAnalyticsDTO:
        """
        Return realtime statistics for the last :data:`REALTIME_WINDOW_MINUTES`
        minutes.

        Returns
        -------
        RealtimeAnalyticsDTO
        """
        key = realtime_key()
        return self._cache.get_or_set_realtime(key, self._compute)

    def _compute(self) -> RealtimeAnalyticsDTO:
        """Query repository for realtime metrics."""
        since = timezone.now() - timedelta(minutes=REALTIME_WINDOW_MINUTES)
        repo = self._repo

        return RealtimeAnalyticsDTO(
            visits_last_5_minutes=repo.count_recent_visits(since),
            unique_ips_last_5_minutes=repo.count_recent_unique_ips(since),
            average_response_time_last_5_minutes=repo.get_recent_avg_response_time(
                since
            ),
        )
