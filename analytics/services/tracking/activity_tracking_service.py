"""
Activity tracking service for analytics.

Responsible for assembling a complete :class:`SiteActivity` record from
the parsed request data and persisting it via the repository layer.

This service has no analytics responsibilities.  It does not compute
aggregations, percentiles, or session metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from django.http import HttpRequest, HttpResponse

from analytics.exceptions import TrackingError
from analytics.repositories.activity_repository import ActivityRepository
from analytics.services.geo.geoip_service import GeoIPService
from analytics.services.tracking.request_parser import RequestParser
from analytics.services.tracking.user_agent_parser import UserAgentParser
from analytics.typing import ActivityRepositoryProtocol, GeoIPServiceProtocol

logger = logging.getLogger(__name__)

# Sentinel value stored in request.META to record when the middleware
# started processing so that response time can be computed.
_START_TIME_META_KEY = "_ra_start_time"


class ActivityTrackingService:
    """
    Orchestrates request parsing and activity persistence.

    Middleware delegates all tracking decisions to this service.  The
    service knows *how* to build an activity record but not *when* to
    skip one (that is the middleware's responsibility).

    Parameters
    ----------
    repository:
        Repository for persisting activities.  Defaults to
        :class:`~analytics.repositories.activity_repository.ActivityRepository`.
    geoip_service:
        GeoIP resolver.  Defaults to
        :class:`~analytics.services.geo.geoip_service.GeoIPService`.
    request_parser:
        Raw request field extractor.  Defaults to
        :class:`~analytics.services.tracking.request_parser.RequestParser`.
    ua_parser:
        User-agent parser.  Defaults to
        :class:`~analytics.services.tracking.user_agent_parser.UserAgentParser`.
    """

    def __init__(
        self,
        repository: Optional[ActivityRepositoryProtocol] = None,
        geoip_service: Optional[GeoIPServiceProtocol] = None,
        request_parser: Optional[RequestParser] = None,
        ua_parser: Optional[UserAgentParser] = None,
    ) -> None:
        self._repository: ActivityRepositoryProtocol = (
            repository or ActivityRepository()
        )
        self._geoip: GeoIPServiceProtocol = geoip_service or GeoIPService()
        self._request_parser: RequestParser = request_parser or RequestParser()
        self._ua_parser: UserAgentParser = ua_parser or UserAgentParser()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def mark_request_start(self, request: HttpRequest) -> None:
        """
        Record the current monotonic time on *request.META* so that
        :meth:`track` can compute elapsed response time.

        This must be called as early as possible in the middleware chain.

        Parameters
        ----------
        request:
            The incoming Django HTTP request.
        """
        request.META[_START_TIME_META_KEY] = time.monotonic()

    def track(self, request: HttpRequest, response: HttpResponse) -> None:
        """
        Build and persist a :class:`~analytics.models.SiteActivity`
        record for the completed request/response cycle.

        All exceptions are caught and logged; tracking failures must
        never affect the caller's response.

        Parameters
        ----------
        request:
            The Django HTTP request (after response is generated).
        response:
            The Django HTTP response.
        """
        try:
            self._persist(request, response)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Activity tracking failed for path=%s: %s",
                getattr(request, "path_info", "unknown"),
                exc,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_response_time_ms(self, request: HttpRequest) -> Optional[int]:
        """
        Return elapsed response time in milliseconds using the start time
        stored by :meth:`mark_request_start`.

        Parameters
        ----------
        request:
            The Django HTTP request.

        Returns
        -------
        int or None
            Elapsed milliseconds, or ``None`` when no start time is recorded.
        """
        start: Optional[float] = request.META.get(_START_TIME_META_KEY)
        if start is None:
            return None
        elapsed_seconds = time.monotonic() - start
        return max(0, int(elapsed_seconds * 1000))

    def _persist(self, request: HttpRequest, response: HttpResponse) -> None:
        """
        Assemble and save the activity record.

        Parameters
        ----------
        request:
            The Django HTTP request.
        response:
            The Django HTTP response.

        Raises
        ------
        TrackingError
            When the repository raises an unexpected exception.
        """
        parser = self._request_parser

        ip_address = parser.get_client_ip(request)
        raw_ua = parser.get_user_agent(request)
        ua_data = self._ua_parser.parse(raw_ua)
        geo_data = self._geoip.get_location(ip_address)
        response_time_ms = self._compute_response_time_ms(request)

        try:
            self._repository.create_activity(
                user_id=parser.get_user_id(request),
                session_key=parser.get_session_key(request),
                ip_address=ip_address,
                path=parser.get_path(request),
                query_string=parser.get_query_string(request),
                method=parser.get_method(request),
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                user_agent=raw_ua,
                browser_family=ua_data.get("browser_family", ""),
                browser_version=ua_data.get("browser_version", ""),
                os_family=ua_data.get("os_family", ""),
                os_version=ua_data.get("os_version", ""),
                device_type=ua_data.get("device_type", ""),
                is_ajax=parser.is_ajax(request),
                is_secure=parser.is_secure(request),
                referer=parser.get_referer(request),
                country_code=geo_data.get("country_code") or "",
                city=geo_data.get("city") or "",
            )
        except Exception as exc:  # noqa: BLE001
            raise TrackingError(
                f"Failed to persist activity record: {exc}"
            ) from exc
