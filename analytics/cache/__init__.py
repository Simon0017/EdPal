"""
Cache package for analytics.

Exports the analytics cache service and cache key utilities.
"""

from analytics.cache.analytics_cache_service import AnalyticsCacheService
from analytics.cache.cache_keys import (
    behavior_key,
    geoip_key,
    overview_key,
    performance_key,
    realtime_key,
    summary_key,
    traffic_key,
)

__all__ = [
    "AnalyticsCacheService",
    "overview_key",
    "traffic_key",
    "behavior_key",
    "performance_key",
    "realtime_key",
    "summary_key",
    "geoip_key",
]
