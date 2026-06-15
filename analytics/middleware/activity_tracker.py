"""
Activity tracker middleware for analytics.

Intercepts every HTTP request/response cycle and delegates tracking to
:class:`~analytics.services.tracking.activity_tracking_service.ActivityTrackingService`.

Design constraints
------------------
* No analytics calculations here.
* Only tracking responsibilities.
* Compatible with both ASGI (async) and WSGI (sync) deployments.
* Non-blocking: tracking is fire-and-forget inside the sync path.  For
  async deployments Django runs the synchronous call in a thread executor
  automatically when ``async_capable`` is ``False`` — a fully async path
  would require ``SyncToAsync`` wrappers around the ORM which adds
  complexity without benefit for a write-heavy fire-and-forget pattern.
  The current design keeps the ORM layer synchronous and predictable.
* Error isolation: tracking failures must never affect response delivery.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from analytics.services.tracking.activity_tracking_service import (
    ActivityTrackingService,
)
from analytics.settings.defaults import get_excluded_paths

logger = logging.getLogger(__name__)


class ActivityTrackerMiddleware(MiddlewareMixin):
    """
    Django middleware that records each incoming request as a
    :class:`~analytics.models.SiteActivity`.

    The middleware:
    * Skips paths matching the configured exclusion list.
    * Records the request start time before passing control downstream.
    * Delegates all field extraction and persistence to
      :class:`~analytics.services.tracking.activity_tracking_service.ActivityTrackingService`.
    * Isolates all tracking errors from the normal request/response flow.

    Configuration
    -------------
    ``analytics_EXCLUDED_PATHS`` (list of str):
        URL path prefixes to skip.  Defaults are ``/admin/``, ``/static/``,
        ``/media/``, ``/favicon.ico``.

    Add the middleware to ``MIDDLEWARE`` **before** any session or
    authentication middleware to ensure session keys and user objects are
    populated before tracking:

    .. code-block:: python

        MIDDLEWARE = [
            "analytics.middleware.activity_tracker.ActivityTrackerMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            ...
        ]

    Parameters
    ----------
    get_response:
        The next middleware or view callable.
    tracking_service:
        Optional injectable tracking service (used in tests).
    """

    def __init__(
        self,
        get_response: Callable,
        tracking_service: Optional[ActivityTrackingService] = None,
    ) -> None:
        super().__init__(get_response)
        self._tracking_service: ActivityTrackingService = (
            tracking_service or ActivityTrackingService()
        )
        self._excluded_paths: List[str] = get_excluded_paths()

    # ------------------------------------------------------------------
    # Path exclusion
    # ------------------------------------------------------------------

    def _should_skip(self, path: str) -> bool:
        """
        Return ``True`` when *path* matches one of the configured
        exclusion prefixes.

        Parameters
        ----------
        path:
            The request path (``request.path_info``).
        """
        return any(path.startswith(prefix) for prefix in self._excluded_paths)

    # ------------------------------------------------------------------
    # MiddlewareMixin hooks
    # ------------------------------------------------------------------

    def process_request(self, request: HttpRequest) -> None:
        """
        Record the request start time on ``request.META``.

        This hook is called *before* the view so the response time
        measurement includes the full view execution duration.

        Parameters
        ----------
        request:
            The incoming Django HTTP request.
        """
        if self._should_skip(request.path_info):
            return
        try:
            self._tracking_service.mark_request_start(request)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to mark request start for path=%s: %s",
                request.path_info,
                exc,
                exc_info=True,
            )

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        """
        Delegate activity tracking after the response is generated.

        Parameters
        ----------
        request:
            The processed Django HTTP request.
        response:
            The generated Django HTTP response.

        Returns
        -------
        HttpResponse
            The unmodified *response* object.
        """
        if self._should_skip(request.path_info):
            return response

        try:
            self._tracking_service.track(request, response)
        except Exception as exc:  # noqa: BLE001
            # Last-resort safety net; the tracking service already catches
            # and logs its own exceptions.
            logger.error(
                "Unhandled exception in ActivityTrackerMiddleware for path=%s: %s",
                request.path_info,
                exc,
                exc_info=True,
            )

        return response
