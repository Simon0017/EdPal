"""
Performance analytics service for analytics.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from analytics.cache.analytics_cache_service import AnalyticsCacheService
from analytics.cache.cache_keys import performance_key
from analytics.repositories.activity_repository import ActivityRepository
from analytics.services.analytics.aggregations.performance import (
    enrich_path_performance_with_p95,
)
from analytics.services.analytics.dto import (
    EndpointPerformanceRow,
    ErrorRow,
    HourlyResponseTimePoint,
    PathPerformanceRow,
    PerformanceAnalyticsDTO,
    StatusCodeRow,
)
from analytics.settings.defaults import get_cache_timeout
from analytics.typing import ActivityRepositoryProtocol, CacheServiceProtocol

logger = logging.getLogger(__name__)


class PerformanceAnalyticsService:
    """
    Computes performance-related analytics for a given date range.

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

    def get_performance_data(
        self, start: datetime, end: datetime
    ) -> PerformanceAnalyticsDTO:
        """
        Return performance analytics for [*start*, *end*].

        Parameters
        ----------
        start:
            Period start (timezone-aware).
        end:
            Period end (timezone-aware).
        """
        key = performance_key(start, end)
        return self._cache.get_or_set(
            key,
            lambda: self._compute(start, end),
            timeout=get_cache_timeout(),
        )

    def _compute(self, start: datetime, end: datetime) -> PerformanceAnalyticsDTO:
        repo = self._repo

        # Hourly response time trends
        raw_hourly = repo.get_hourly_response_time(start, end)
        hourly_trends = [
            HourlyResponseTimePoint(
                hour=row["hour"].isoformat()
                if hasattr(row["hour"], "isoformat")
                else str(row["hour"]),
                avg_ms=round(row["avg_ms"], 2) if row["avg_ms"] is not None else 0.0,
            )
            for row in raw_hourly
        ]

        # Status code distribution
        raw_status = repo.get_status_code_distribution(start, end)
        status_codes = [
            StatusCodeRow(status_code=row["status_code"], count=row["count"])
            for row in raw_status
        ]

        # Top 10 slowest endpoints
        raw_slowest = repo.get_slowest_endpoints(start, end, limit=10)
        slowest = []
        for row in raw_slowest:
            request_count = row.get("request_count", 0)
            error_count = row.get("error_count", 0)
            error_rate = (
                round((error_count / request_count) * 100, 2)
                if request_count > 0
                else 0.0
            )
            slowest.append(
                EndpointPerformanceRow(
                    path=row["path"],
                    average_response_time_ms=round(row.get("avg_ms") or 0.0, 2),
                    max_response_time_ms=row.get("max_ms") or 0,
                    request_count=request_count,
                    error_rate_percentage=error_rate,
                )
            )

        # Top 20 path performance with P95
        raw_paths = repo.get_path_performance(start, end, limit=20)
        enriched_paths = enrich_path_performance_with_p95(repo, raw_paths, start, end)
        path_perf = [
            PathPerformanceRow(
                path=row["path"],
                average_response_time_ms=round(row.get("avg_ms") or 0.0, 2),
                request_count=row.get("request_count", 0),
                p95_response_time_ms=row.get("p95_response_time_ms"),
            )
            for row in enriched_paths
        ]

        # Common errors
        raw_errors = repo.get_common_errors(start, end)
        errors = [
            ErrorRow(
                path=row["path"],
                status_code=row["status_code"],
                count=row["count"],
            )
            for row in raw_errors
        ]

        return PerformanceAnalyticsDTO(
            response_time_trends_by_hour=hourly_trends,
            status_code_distribution=status_codes,
            top_10_slowest_endpoints=slowest,
            top_20_path_performance=path_perf,
            common_errors=errors,
        )
