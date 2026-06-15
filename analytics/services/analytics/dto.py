"""
Data Transfer Objects (DTOs) for analytics service return values.

All analytics services return strongly typed, immutable dataclass instances
rather than raw dicts.  This enforces a stable contract between the
analytics layer and its consumers (APIs, management commands, tasks, etc.).

All DTOs are frozen (``frozen=True``) to prevent accidental mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DailyVisitPoint:
    """A single data point in a daily visit trend series."""

    date: str
    """ISO 8601 date string (YYYY-MM-DD)."""

    count: int
    """Number of visits on this date."""


@dataclass(frozen=True)
class OverviewAnalyticsDTO:
    """Return value of :meth:`OverviewAnalyticsService.get_overview_data`."""

    total_visits: int
    unique_visitors: int
    unique_users: int
    new_visitors: int
    returning_visitors: int
    average_response_time_ms: Optional[float]
    max_response_time_ms: Optional[int]
    min_response_time_ms: Optional[int]
    authenticated_visits: int
    anonymous_visits: int
    daily_visits_trend: List[DailyVisitPoint]
    visitor_type_distribution: Dict[str, int]
    """Keys: ``authenticated``, ``anonymous``."""


# ---------------------------------------------------------------------------
# Traffic
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageVisitRow:
    """A single page in the top pages list."""

    path: str
    count: int


@dataclass(frozen=True)
class DistributionRow:
    """A generic distribution entry with a label, count, and percentage."""

    label: str
    count: int
    percentage: float


@dataclass(frozen=True)
class TrafficAnalyticsDTO:
    """Return value of :meth:`TrafficAnalyticsService.get_traffic_data`."""

    top_10_pages: List[PageVisitRow]
    http_method_distribution: List[DistributionRow]
    geographic_distribution: List[DistributionRow]
    device_type_distribution: List[DistributionRow]
    top_5_referrers: List[PageVisitRow]


# ---------------------------------------------------------------------------
# Behavior
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HourlyActivityPoint:
    """Request count for a single hour of the day (0–23)."""

    hour: int
    count: int


@dataclass(frozen=True)
class BehaviorAnalyticsDTO:
    """Return value of :meth:`BehaviorAnalyticsService.get_behavior_data`."""

    top_5_browsers: List[DistributionRow]
    top_5_operating_systems: List[DistributionRow]
    activity_by_hour: List[HourlyActivityPoint]
    average_session_duration_seconds: float
    average_page_views_per_session: float
    average_unique_paths_per_session: float
    ajax_vs_regular_requests: Dict[str, int]
    """Keys: ``ajax``, ``regular``."""


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HourlyResponseTimePoint:
    """Average response time for a single truncated-hour bucket."""

    hour: str
    """ISO 8601 datetime string of the truncated hour."""

    avg_ms: float


@dataclass(frozen=True)
class StatusCodeRow:
    """HTTP status code count."""

    status_code: int
    count: int


@dataclass(frozen=True)
class EndpointPerformanceRow:
    """Performance stats for a single endpoint path."""

    path: str
    average_response_time_ms: float
    max_response_time_ms: int
    request_count: int
    error_rate_percentage: float


@dataclass(frozen=True)
class PathPerformanceRow:
    """Per-path performance stats including P95."""

    path: str
    average_response_time_ms: float
    request_count: int
    p95_response_time_ms: Optional[int]


@dataclass(frozen=True)
class ErrorRow:
    """A frequently occurring error entry."""

    path: str
    status_code: int
    count: int


@dataclass(frozen=True)
class PerformanceAnalyticsDTO:
    """Return value of :meth:`PerformanceAnalyticsService.get_performance_data`."""

    response_time_trends_by_hour: List[HourlyResponseTimePoint]
    status_code_distribution: List[StatusCodeRow]
    top_10_slowest_endpoints: List[EndpointPerformanceRow]
    top_20_path_performance: List[PathPerformanceRow]
    common_errors: List[ErrorRow]


# ---------------------------------------------------------------------------
# Realtime
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RealtimeAnalyticsDTO:
    """Return value of :meth:`RealtimeAnalyticsService.get_realtime_stats`."""

    visits_last_5_minutes: int
    unique_ips_last_5_minutes: int
    average_response_time_last_5_minutes: Optional[float]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SummaryAnalyticsDTO:
    """Return value of :meth:`SummaryAnalyticsService.analytics_summary`."""

    today_visits: int
    today_unique_ips: int
    today_average_response_time: Optional[float]
    week_total_visits: int
    week_total_unique_ips: int
