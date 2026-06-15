"""
Request parsing utilities for the tracking service.

Extracts raw field values from Django ``HttpRequest`` objects without
any business logic or analytics calculations.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.http import HttpRequest

from analytics.constants import (
    AJAX_HEADER_VALUE,
    HEADER_REFERER,
    HEADER_USER_AGENT,
    HEADER_X_FORWARDED_FOR,
    HEADER_X_REAL_IP,
    HEADER_X_REQUESTED_WITH,
    LOCALHOST_IP,
    UNKNOWN_VALUE,
)
from analytics.typing import IpAddress, UrlPath, UserAgentString

logger = logging.getLogger(__name__)


class RequestParser:
    """
    Stateless helper that extracts normalised field values from an
    :class:`django.http.HttpRequest`.

    All methods are pure functions and have no side effects.
    """

    def get_client_ip(self, request: HttpRequest) -> IpAddress:
        """
        Extract the real client IP address from the request.

        Respects ``X-Forwarded-For`` and ``X-Real-IP`` headers (populated
        by reverse proxies) in that order before falling back to
        ``REMOTE_ADDR``.

        The leftmost IP in ``X-Forwarded-For`` is the original client.

        Parameters
        ----------
        request:
            The Django HTTP request.

        Returns
        -------
        str
            The best-guess client IP address.
        """
        x_forwarded_for = request.META.get(HEADER_X_FORWARDED_FOR)
        if x_forwarded_for:
            # Take the first (leftmost) address, strip whitespace.
            ip = x_forwarded_for.split(",")[0].strip()
            if ip:
                return ip

        x_real_ip = request.META.get(HEADER_X_REAL_IP)
        if x_real_ip:
            return x_real_ip.strip()

        return request.META.get("REMOTE_ADDR", LOCALHOST_IP)

    def get_path(self, request: HttpRequest) -> UrlPath:
        """
        Return the request path without query string.

        Parameters
        ----------
        request:
            The Django HTTP request.
        """
        return request.path_info

    def get_query_string(self, request: HttpRequest) -> str:
        """
        Return the raw query string (everything after ``?``).

        Parameters
        ----------
        request:
            The Django HTTP request.
        """
        return request.META.get("QUERY_STRING", "")

    def get_method(self, request: HttpRequest) -> str:
        """
        Return the HTTP method in uppercase.

        Parameters
        ----------
        request:
            The Django HTTP request.
        """
        return (request.method or "GET").upper()

    def get_user_agent(self, request: HttpRequest) -> UserAgentString:
        """
        Return the raw ``User-Agent`` header value.

        Parameters
        ----------
        request:
            The Django HTTP request.
        """
        return request.META.get(HEADER_USER_AGENT, "")

    def get_referer(self, request: HttpRequest) -> str:
        """
        Return the ``Referer`` header value.

        Parameters
        ----------
        request:
            The Django HTTP request.
        """
        return request.META.get(HEADER_REFERER, "")

    def is_ajax(self, request: HttpRequest) -> bool:
        """
        Return ``True`` when the request carries the XMLHttpRequest header.

        Parameters
        ----------
        request:
            The Django HTTP request.
        """
        return (
            request.META.get(HEADER_X_REQUESTED_WITH, "") == AJAX_HEADER_VALUE
        )

    def is_secure(self, request: HttpRequest) -> bool:
        """
        Return ``True`` when the request was served over HTTPS.

        Parameters
        ----------
        request:
            The Django HTTP request.
        """
        return request.is_secure()

    def get_session_key(self, request: HttpRequest) -> Optional[str]:
        """
        Return the session key if a session is available.

        Parameters
        ----------
        request:
            The Django HTTP request.

        Returns
        -------
        str or None
            The session key string, or ``None`` when no session exists or
            the session is empty (to avoid creating unnecessary sessions).
        """
        try:
            session = getattr(request, "session", None)
            if session is None:
                return None
            # Avoid creating a session just for tracking.
            if not session.session_key:
                return None
            return session.session_key
        except Exception:  # noqa: BLE001
            return None

    def get_user_id(self, request: HttpRequest) -> Optional[int]:
        """
        Return the authenticated user's PK, or ``None`` for anonymous users.

        Parameters
        ----------
        request:
            The Django HTTP request.
        """
        user = getattr(request, "user", None)
        if user is None:
            return None
        try:
            if user.is_authenticated:
                return user.pk
        except Exception:  # noqa: BLE001
            pass
        return None
