"""
Repository layer for SiteActivity records.

All ORM interaction is centralised here.  Analytics services and the
tracking service consume this class; no service constructs raw ORM
queries directly.

The repository exposes composable QuerySet-returning methods so callers
can chain additional filters without re-querying the database.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.db.models import (
    Avg,
    Count,
    Max,
    Min,
    Q,
    QuerySet,
)
from django.db.models.functions import ExtractHour, TruncDate, TruncHour

from analytics.models import SiteActivity
from analytics.typing import AggregationResult

logger = logging.getLogger(__name__)

_ERROR_FILTER = Q(status_code__gte=400)


class ActivityRepository:
    """
    Data-access object for :class:`~analytics.models.SiteActivity`.

    All methods return either a ``QuerySet`` (for further composition) or
    a concrete Python value / list (for aggregation results that are fully
    evaluated).

    The repository is stateless; each call operates on a fresh queryset.
    Dependency injection is supported by passing an alternative model class
    via the constructor (useful in tests).
    """

    def __init__(self, model: type = SiteActivity) -> None:
        """
        Initialise the repository.

        Parameters
        ----------
        model:
            The Django model class to operate on.  Defaults to
            :class:`~analytics.models.SiteActivity`.
        """
        self._model = model

    # ------------------------------------------------------------------
    # Base querysets
    # ------------------------------------------------------------------

    def get_queryset(self) -> QuerySet:
        """Return the base unfiltered queryset."""
        return self._model.objects.all()

    def filter_by_date_range(
        self, queryset: QuerySet, start: datetime, end: datetime
    ) -> QuerySet:
        """
        Filter *queryset* to records whose ``timestamp`` falls within
        [*start*, *end*] (inclusive).
        """
        return queryset.filter(timestamp__gte=start, timestamp__lte=end)

    def for_date_range(self, start: datetime, end: datetime) -> QuerySet:
        """Return a queryset pre-filtered to *start* ... *end*."""
        return self.filter_by_date_range(self.get_queryset(), start, end)

    # ------------------------------------------------------------------
    # Visitor / visit counts
    # ------------------------------------------------------------------

    def count_total_visits(self, start: datetime, end: datetime) -> int:
        """Return the total number of requests in the date range."""
        return self.for_date_range(start, end).count()

    def count_unique_ips(self, start: datetime, end: datetime) -> int:
        """Return the number of distinct IP addresses in the date range."""
        return (
            self.for_date_range(start, end)
            .values("ip_address")
            .distinct()
            .count()
        )

    def count_unique_users(self, start: datetime, end: datetime) -> int:
        """Return the number of distinct authenticated users in the date range."""
        return (
            self.for_date_range(start, end)
            .filter(user__isnull=False)
            .values("user_id")
            .distinct()
            .count()
        )

    def count_authenticated_visits(self, start: datetime, end: datetime) -> int:
        """Return visits made by authenticated users."""
        return self.for_date_range(start, end).filter(user__isnull=False).count()

    def count_anonymous_visits(self, start: datetime, end: datetime) -> int:
        """Return visits made by anonymous (unauthenticated) users."""
        return self.for_date_range(start, end).filter(user__isnull=True).count()

    # ------------------------------------------------------------------
    # Visitor novelty
    # ------------------------------------------------------------------

    def get_ip_first_seen_dates(
        self, start: datetime, end: datetime
    ) -> QuerySet:
        """
        Return a queryset of dicts with ``ip_address`` and ``first_seen``
        (the earliest timestamp for each IP across all time).

        Used to classify visitors as new or returning relative to the
        analysis window.
        """
        return (
            self._model.objects.values("ip_address")
            .annotate(first_seen=Min("timestamp"))
        )

    # ------------------------------------------------------------------
    # Response time aggregations
    # ------------------------------------------------------------------

    def get_response_time_stats(
        self, start: datetime, end: datetime
    ) -> Dict[str, Optional[float]]:
        """
        Return a dict with ``avg``, ``max``, and ``min`` response times
        (in milliseconds) for the given date range.

        NULL ``response_time_ms`` values are excluded from the aggregation.
        """
        result = (
            self.for_date_range(start, end)
            .filter(response_time_ms__isnull=False)
            .aggregate(
                avg=Avg("response_time_ms"),
                max=Max("response_time_ms"),
                min=Min("response_time_ms"),
            )
        )
        return result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Daily trends
    # ------------------------------------------------------------------

    def get_daily_visit_counts(
        self, start: datetime, end: datetime
    ) -> AggregationResult:
        """
        Return a list of ``{date, count}`` dicts representing visit
        counts per calendar day within the date range.
        """
        return list(
            self.for_date_range(start, end)
            .annotate(date=TruncDate("timestamp"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )

    # ------------------------------------------------------------------
    # Top pages / paths
    # ------------------------------------------------------------------

    def get_top_paths(
        self, start: datetime, end: datetime, limit: int = 10
    ) -> AggregationResult:
        """Return the *limit* most visited paths with their visit counts."""
        return list(
            self.for_date_range(start, end)
            .values("path")
            .annotate(count=Count("id"))
            .order_by("-count")[:limit]
        )

    # ------------------------------------------------------------------
    # HTTP method distribution
    # ------------------------------------------------------------------

    def get_method_distribution(
        self, start: datetime, end: datetime
    ) -> AggregationResult:
        """Return visit counts grouped by HTTP method."""
        return list(
            self.for_date_range(start, end)
            .values("method")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

    # ------------------------------------------------------------------
    # Geographic distribution
    # ------------------------------------------------------------------

    def get_country_distribution(
        self, start: datetime, end: datetime
    ) -> AggregationResult:
        """Return visit counts grouped by country code."""
        return list(
            self.for_date_range(start, end)
            .exclude(country_code="")
            .values("country_code")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

    # ------------------------------------------------------------------
    # Device / browser / OS distribution
    # ------------------------------------------------------------------

    def get_device_type_distribution(
        self, start: datetime, end: datetime
    ) -> AggregationResult:
        """Return visit counts grouped by device type."""
        return list(
            self.for_date_range(start, end)
            .values("device_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

    def get_browser_distribution(
        self, start: datetime, end: datetime, limit: int = 5
    ) -> AggregationResult:
        """Return visit counts grouped by browser family."""
        return list(
            self.for_date_range(start, end)
            .exclude(browser_family="")
            .values("browser_family")
            .annotate(count=Count("id"))
            .order_by("-count")[:limit]
        )

    def get_os_distribution(
        self, start: datetime, end: datetime, limit: int = 5
    ) -> AggregationResult:
        """Return visit counts grouped by OS family."""
        return list(
            self.for_date_range(start, end)
            .exclude(os_family="")
            .values("os_family")
            .annotate(count=Count("id"))
            .order_by("-count")[:limit]
        )

    # ------------------------------------------------------------------
    # Referrers
    # ------------------------------------------------------------------

    def get_top_referrers(
        self, start: datetime, end: datetime, limit: int = 5
    ) -> AggregationResult:
        """Return the top referrer URLs with their visit counts."""
        return list(
            self.for_date_range(start, end)
            .exclude(referer="")
            .values("referer")
            .annotate(count=Count("id"))
            .order_by("-count")[:limit]
        )

    # ------------------------------------------------------------------
    # Hourly activity
    # ------------------------------------------------------------------

    def get_hourly_activity(
        self, start: datetime, end: datetime
    ) -> AggregationResult:
        """Return visit counts broken down by hour of day (0-23)."""
        return list(
            self.for_date_range(start, end)
            .annotate(hour=ExtractHour("timestamp"))
            .values("hour")
            .annotate(count=Count("id"))
            .order_by("hour")
        )

    # ------------------------------------------------------------------
    # Hourly response time trends
    # ------------------------------------------------------------------

    def get_hourly_response_time(
        self, start: datetime, end: datetime
    ) -> AggregationResult:
        """Return average response time grouped by truncated hour."""
        return list(
            self.for_date_range(start, end)
            .filter(response_time_ms__isnull=False)
            .annotate(hour=TruncHour("timestamp"))
            .values("hour")
            .annotate(avg_ms=Avg("response_time_ms"))
            .order_by("hour")
        )

    # ------------------------------------------------------------------
    # Status code distribution
    # ------------------------------------------------------------------

    def get_status_code_distribution(
        self, start: datetime, end: datetime
    ) -> AggregationResult:
        """Return visit counts grouped by HTTP status code."""
        return list(
            self.for_date_range(start, end)
            .values("status_code")
            .annotate(count=Count("id"))
            .order_by("status_code")
        )

    # ------------------------------------------------------------------
    # Slowest endpoints
    # ------------------------------------------------------------------

    def get_slowest_endpoints(
        self, start: datetime, end: datetime, limit: int = 10
    ) -> AggregationResult:
        """
        Return the *limit* slowest endpoints by average response time,
        including average/max ms, request count, and error count.
        """
        return list(
            self.for_date_range(start, end)
            .filter(response_time_ms__isnull=False)
            .values("path")
            .annotate(
                avg_ms=Avg("response_time_ms"),
                max_ms=Max("response_time_ms"),
                request_count=Count("id"),
                error_count=Count("id", filter=_ERROR_FILTER),
            )
            .order_by("-avg_ms")[:limit]
        )

    def get_path_performance(
        self, start: datetime, end: datetime, limit: int = 20
    ) -> AggregationResult:
        """
        Return path-level performance statistics including avg, count, max.

        P95 enrichment is applied by the performance aggregation module.
        """
        return list(
            self.for_date_range(start, end)
            .filter(response_time_ms__isnull=False)
            .values("path")
            .annotate(
                avg_ms=Avg("response_time_ms"),
                request_count=Count("id"),
                max_ms=Max("response_time_ms"),
            )
            .order_by("-request_count")[:limit]
        )

    def get_response_times_for_path(
        self, path: str, start: datetime, end: datetime
    ) -> List[int]:
        """
        Return a sorted list of ``response_time_ms`` values for *path*
        within the date range.

        Used for in-memory percentile calculations.
        """
        return list(
            self.for_date_range(start, end)
            .filter(path=path, response_time_ms__isnull=False)
            .order_by("response_time_ms")
            .values_list("response_time_ms", flat=True)
        )

    def get_common_errors(
        self, start: datetime, end: datetime
    ) -> AggregationResult:
        """Return paths with the highest 4xx/5xx error counts."""
        return list(
            self.for_date_range(start, end)
            .filter(status_code__gte=400)
            .values("path", "status_code")
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        )

    # ------------------------------------------------------------------
    # AJAX flag
    # ------------------------------------------------------------------

    def get_ajax_distribution(
        self, start: datetime, end: datetime
    ) -> Dict[str, int]:
        """Return counts of AJAX vs regular (non-AJAX) requests."""
        result = (
            self.for_date_range(start, end)
            .values("is_ajax")
            .annotate(count=Count("id"))
        )
        distribution: Dict[str, int] = {"ajax": 0, "regular": 0}
        for row in result:
            key = "ajax" if row["is_ajax"] else "regular"
            distribution[key] = row["count"]
        return distribution

    # ------------------------------------------------------------------
    # Session-related raw queries
    # ------------------------------------------------------------------

    def get_session_data(
        self, start: datetime, end: datetime
    ) -> QuerySet:
        """
        Return a queryset with the fields needed for session analysis.

        Fields: ``session_key``, ``user_id``, ``ip_address``, ``timestamp``,
        ``path``.

        The session aggregation module is responsible for grouping this
        data into logical sessions.
        """
        return (
            self.for_date_range(start, end)
            .only(
                "session_key",
                "user_id",
                "ip_address",
                "timestamp",
                "path",
            )
            .order_by("ip_address", "timestamp")
        )

    # ------------------------------------------------------------------
    # Realtime helpers
    # ------------------------------------------------------------------

    def get_recent_queryset(self, since: datetime) -> QuerySet:
        """Return all records with ``timestamp >= since``."""
        return self._model.objects.filter(timestamp__gte=since)

    def count_recent_visits(self, since: datetime) -> int:
        """Return the number of requests since *since*."""
        return self.get_recent_queryset(since).count()

    def count_recent_unique_ips(self, since: datetime) -> int:
        """Return the number of distinct IPs since *since*."""
        return (
            self.get_recent_queryset(since)
            .values("ip_address")
            .distinct()
            .count()
        )

    def get_recent_avg_response_time(self, since: datetime) -> Optional[float]:
        """Return the average response time (ms) since *since*, or None."""
        result = (
            self.get_recent_queryset(since)
            .filter(response_time_ms__isnull=False)
            .aggregate(avg=Avg("response_time_ms"))
        )
        return result.get("avg")

    # ------------------------------------------------------------------
    # Bulk insert
    # ------------------------------------------------------------------

    def create_activity(self, **kwargs: Any) -> SiteActivity:
        """
        Create and return a single :class:`SiteActivity` record.

        Parameters
        ----------
        **kwargs:
            Field values passed directly to ``SiteActivity.objects.create``.
        """
        return self._model.objects.create(**kwargs)
