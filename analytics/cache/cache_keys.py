"""
Centralised cache key generation for analytics.

All cache keys are constructed through this module to ensure:
* No key collisions between analytics types.
* Deterministic, reproducible keys given the same inputs.
* Easy invalidation by type or date range.
* Support for cache versioning.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from analytics.constants import CACHE_KEY_SEP
from analytics.settings.defaults import get_cache_key_prefix

# Cache version — increment to invalidate all keys without flushing backend
CACHE_VERSION: int = 1


def _build_key(*parts: str) -> str:
    """
    Join *parts* with the configured separator and prepend the application
    prefix and cache version.

    The resulting key format is::

        <prefix>:v<version>:<part1>:<part2>:…

    Parameters
    ----------
    *parts:
        String segments to include in the key.

    Returns
    -------
    str
        The assembled cache key.
    """
    prefix = get_cache_key_prefix()
    version = f"v{CACHE_VERSION}"
    return CACHE_KEY_SEP.join([prefix, version, *parts])


def _date_segment(dt: datetime) -> str:
    """
    Return a compact, filesystem-safe representation of a datetime for
    use as a cache key segment.

    Parameters
    ----------
    dt:
        A timezone-aware datetime.

    Returns
    -------
    str
        ISO-format date truncated to the second (colons replaced).
    """
    return dt.strftime("%Y%m%dT%H%M%S")


def _hash_range(start: datetime, end: datetime) -> str:
    """
    Return a short deterministic hash of the date range.

    Using a hash avoids extremely long cache keys when the datetime
    precision is high.

    Parameters
    ----------
    start:
        Range start (timezone-aware).
    end:
        Range end (timezone-aware).

    Returns
    -------
    str
        An 8-character hex digest uniquely representing the range.
    """
    raw = f"{_date_segment(start)}-{_date_segment(end)}"
    return hashlib.sha1(raw.encode(), usedforsecurity=False).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Analytics cache keys
# ---------------------------------------------------------------------------


def overview_key(start: datetime, end: datetime) -> str:
    """Cache key for :class:`~analytics.services.analytics.overview_service.OverviewAnalyticsService`."""
    return _build_key("overview", _hash_range(start, end))


def traffic_key(start: datetime, end: datetime) -> str:
    """Cache key for :class:`~analytics.services.analytics.traffic_service.TrafficAnalyticsService`."""
    return _build_key("traffic", _hash_range(start, end))


def behavior_key(start: datetime, end: datetime) -> str:
    """Cache key for :class:`~analytics.services.analytics.behavior_service.BehaviorAnalyticsService`."""
    return _build_key("behavior", _hash_range(start, end))


def performance_key(start: datetime, end: datetime) -> str:
    """Cache key for :class:`~analytics.services.analytics.performance_service.PerformanceAnalyticsService`."""
    return _build_key("performance", _hash_range(start, end))


def realtime_key() -> str:
    """
    Cache key for realtime analytics.

    Realtime analytics do not accept a date range; the window is always
    the last N minutes from now.  The key therefore contains no range
    component — the TTL governs freshness.
    """
    return _build_key("realtime")


def summary_key() -> str:
    """
    Cache key for summary analytics.

    The summary covers today and the current week relative to now, so
    no date range parameter is needed.
    """
    return _build_key("summary")


# ---------------------------------------------------------------------------
# GeoIP cache key
# ---------------------------------------------------------------------------


def geoip_key(ip_address: str) -> str:
    """
    Cache key for a GeoIP lookup result for *ip_address*.

    Parameters
    ----------
    ip_address:
        The IP address being looked up.

    Returns
    -------
    str
        A cache key that will not collide with analytics keys.
    """
    # Hash the IP to avoid embedding PII directly in cache key names
    ip_hash = hashlib.sha1(
        ip_address.encode(), usedforsecurity=False
    ).hexdigest()[:12]
    return _build_key("geoip", ip_hash)
