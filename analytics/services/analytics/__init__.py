"""
Analytics services package for analytics.

Each service is responsible for one analytics domain and returns a
strongly typed DTO.  Services must not be instantiated with hard-coded
dependencies in production — use the default constructors which resolve
singletons via the repository and cache layers.
"""

from analytics.services.analytics.behavior_service import (
    BehaviorAnalyticsService,
)
from analytics.services.analytics.overview_service import (
    OverviewAnalyticsService,
)
from analytics.services.analytics.performance_service import (
    PerformanceAnalyticsService,
)
from analytics.services.analytics.realtime_service import (
    RealtimeAnalyticsService,
)
from analytics.services.analytics.summary_service import (
    SummaryAnalyticsService,
)
from analytics.services.analytics.traffic_service import (
    TrafficAnalyticsService,
)

__all__ = [
    "OverviewAnalyticsService",
    "TrafficAnalyticsService",
    "BehaviorAnalyticsService",
    "PerformanceAnalyticsService",
    "RealtimeAnalyticsService",
    "SummaryAnalyticsService",
]
