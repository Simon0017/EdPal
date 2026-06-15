"""
Traffic analytics service for analytics.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from analytics.cache.analytics_cache_service import AnalyticsCacheService
from analytics.cache.cache_keys import traffic_key
from analytics.repositories.activity_repository import ActivityRepository
from analytics.services.analytics.aggregations.geography import (
    compute_geographic_distribution,
)
from analytics.services.analytics.aggregations.traffic import (
    compute_total_from_distribution,
    normalise_distribution_percentages,
)
from analytics.services.analytics.dto import (
    DistributionRow,
    PageVisitRow,
    TrafficAnalyticsDTO,
)
from analytics.settings.defaults import get_cache_timeout
from analytics.typing import ActivityRepositoryProtocol, CacheServiceProtocol

logger = logging.getLogger(__name__)


class TrafficAnalyticsService:
    """
    Computes traffic-related analytics for a given date range.

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

    def get_traffic_data(
        self, start: datetime, end: datetime
    ) -> TrafficAnalyticsDTO:
        """
        Return traffic analytics for [*start*, *end*].

        Parameters
        ----------
        start:
            Period start (timezone-aware).
        end:
            Period end (timezone-aware).
        """
        key = traffic_key(start, end)
        return self._cache.get_or_set(
            key,
            lambda: self._compute(start, end),
            timeout=get_cache_timeout(),
        )

    def _compute(self, start: datetime, end: datetime) -> TrafficAnalyticsDTO:
        repo = self._repo

        # Top 10 pages
        raw_pages = repo.get_top_paths(start, end, limit=10)
        top_pages = [
            PageVisitRow(path=row["path"], count=row["count"]) for row in raw_pages
        ]

        # HTTP method distribution
        raw_methods = repo.get_method_distribution(start, end)
        total_methods = compute_total_from_distribution(raw_methods)
        method_rows = normalise_distribution_percentages(raw_methods, total_methods)
        http_methods = [
            DistributionRow(
                label=row["method"],
                count=row["count"],
                percentage=row["percentage"],
            )
            for row in method_rows
        ]

        # Geographic distribution
        raw_geo = compute_geographic_distribution(repo, start, end)
        geo_rows = [
            DistributionRow(
                label=row["country_code"],
                count=row["count"],
                percentage=row.get("percentage", 0.0),
            )
            for row in raw_geo
        ]

        # Device type distribution
        raw_devices = repo.get_device_type_distribution(start, end)
        total_devices = compute_total_from_distribution(raw_devices)
        device_rows = normalise_distribution_percentages(raw_devices, total_devices)
        devices = [
            DistributionRow(
                label=row["device_type"] or "unknown",
                count=row["count"],
                percentage=row["percentage"],
            )
            for row in device_rows
        ]

        # Top 5 referrers
        raw_referrers = repo.get_top_referrers(start, end, limit=5)
        referrers = [
            PageVisitRow(path=row["referer"], count=row["count"])
            for row in raw_referrers
        ]

        return TrafficAnalyticsDTO(
            top_10_pages=top_pages,
            http_method_distribution=http_methods,
            geographic_distribution=geo_rows,
            device_type_distribution=devices,
            top_5_referrers=referrers,
        )
