"""
Shared type aliases and protocols for analytics.

Centralises all custom types to avoid duplication and keep
service signatures consistent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from django.db.models import QuerySet

# ---------------------------------------------------------------------------
# Primitive aliases
# ---------------------------------------------------------------------------

IpAddress = str
UserAgentString = str
UrlPath = str
CountryCode = str
CityName = str
SessionKey = str
CacheKey = str

# A generic JSON-serialisable mapping returned by ORM .values() or annotations
AggregationRow = Dict[str, Any]
AggregationResult = List[AggregationRow]

# Date range used across services and repositories
DateRange = Tuple[datetime, datetime]


# ---------------------------------------------------------------------------
# Protocol interfaces — enables dependency injection and testability
# ---------------------------------------------------------------------------


@runtime_checkable
class ActivityRepositoryProtocol(Protocol):
    """Protocol that all activity repository implementations must satisfy."""

    def get_queryset(self) -> QuerySet:
        """Return the base (unfiltered) queryset for SiteActivity records."""
        ...

    def filter_by_date_range(
        self, queryset: QuerySet, start: datetime, end: datetime
    ) -> QuerySet:
        """Return queryset filtered to the inclusive date range [start, end]."""
        ...


@runtime_checkable
class GeoIPServiceProtocol(Protocol):
    """Protocol that GeoIP service implementations must satisfy."""

    def get_country(self, ip_address: IpAddress) -> Optional[str]:
        """Return the ISO country code for the given IP, or None on failure."""
        ...

    def get_city(self, ip_address: IpAddress) -> Optional[str]:
        """Return the city name for the given IP, or None on failure."""
        ...

    def get_location(
        self, ip_address: IpAddress
    ) -> Dict[str, Optional[str]]:
        """Return a dict with 'country_code' and 'city' keys."""
        ...


@runtime_checkable
class CacheServiceProtocol(Protocol):
    """Protocol that the analytics cache service must satisfy."""

    def get(self, key: CacheKey) -> Optional[Any]:
        """Retrieve a cached value by key, or return None on miss/error."""
        ...

    def set(self, key: CacheKey, value: Any, timeout: Optional[int] = None) -> None:
        """Store a value in the cache with an optional TTL in seconds."""
        ...

    def delete(self, key: CacheKey) -> None:
        """Remove a cached entry by key."""
        ...

    def get_or_set(
        self,
        key: CacheKey,
        callable_: Any,
        timeout: Optional[int] = None,
    ) -> Any:
        """Return cached value if present; otherwise call callable_ and cache result."""
        ...
