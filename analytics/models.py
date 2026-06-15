"""
SiteActivity model — the core tracking record for analytics.

Design notes
------------
* Uses a UUID primary key to avoid exposing sequential IDs and to support
  future sharding or distributed inserts.
* All char fields use ``db_index=False`` by default; indexes are declared
  explicitly below as composite or partial indexes for query efficiency.
* ``timestamp`` is the partition key candidate for PostgreSQL declarative
  partitioning (RANGE on timestamp).  No Django-level partitioning code is
  added here because partition management is a DBA/infrastructure concern;
  the model is designed to be partition-ready.
* ``response_time_ms`` is stored as a positive integer (milliseconds) to
  keep aggregation cheap and avoid floating-point precision issues.
* Nullable foreign key to AUTH_USER_MODEL avoids hard coupling to a specific
  user model while still enabling JOIN-based user analytics.
* All nullable string fields use ``null=False, blank=True, default=""``
  following Django conventions for text fields, unless the absence of a value
  carries semantic meaning (e.g. ``session_key``).
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class SiteActivity(models.Model):
    """
    Records a single HTTP request passing through the analytics middleware.

    Each row represents one request/response cycle with enriched metadata
    about the visitor, device, geography, and performance.
    """

    # ------------------------------------------------------------------
    # Primary key
    # ------------------------------------------------------------------

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="UUID primary key; avoids exposing sequential IDs.",
    )

    # ------------------------------------------------------------------
    # Temporal
    # ------------------------------------------------------------------

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="UTC timestamp of the request.  Partition key candidate.",
    )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_activities",
        db_index=True,
        help_text="Authenticated user, or NULL for anonymous requests.",
    )

    session_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Django session key.  NULL when session middleware is absent.",
    )

    ip_address = models.GenericIPAddressField(
        protocol="both",
        unpack_ipv4=True,
        db_index=True,
        help_text="Client IP address, normalised by the tracking service.",
    )

    # ------------------------------------------------------------------
    # Request
    # ------------------------------------------------------------------

    path = models.CharField(
        max_length=2048,
        help_text="Request path (without query string).",
    )

    query_string = models.TextField(
        blank=True,
        default="",
        help_text="Raw query string, stored for future analysis.",
    )

    method = models.CharField(
        max_length=10,
        help_text="HTTP method in uppercase (GET, POST, …).",
    )

    status_code = models.PositiveSmallIntegerField(
        help_text="HTTP response status code.",
    )

    response_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="End-to-end response time in milliseconds.",
    )

    # ------------------------------------------------------------------
    # User-agent parsed fields
    # ------------------------------------------------------------------

    user_agent = models.TextField(
        blank=True,
        default="",
        help_text="Raw User-Agent header value.",
    )

    browser_family = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Parsed browser family name (e.g. 'Chrome', 'Firefox').",
    )

    browser_version = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Parsed browser version string.",
    )

    os_family = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Parsed operating system family name.",
    )

    os_version = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Parsed OS version string.",
    )

    device_type = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Normalised device type: desktop, mobile, tablet, bot, unknown.",
    )

    # ------------------------------------------------------------------
    # Request flags
    # ------------------------------------------------------------------

    is_ajax = models.BooleanField(
        default=False,
        help_text="True when X-Requested-With: XMLHttpRequest is present.",
    )

    is_secure = models.BooleanField(
        default=False,
        help_text="True when the request was served over HTTPS.",
    )

    # ------------------------------------------------------------------
    # Traffic source
    # ------------------------------------------------------------------

    referer = models.URLField(
        max_length=2048,
        blank=True,
        default="",
        help_text="HTTP Referer header value.",
    )

    # ------------------------------------------------------------------
    # Geolocation
    # ------------------------------------------------------------------

    country_code = models.CharField(
        max_length=8,
        blank=True,
        default="",
        help_text="ISO 3166-1 alpha-2 country code resolved from IP.",
    )

    city = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="City name resolved from IP.",
    )

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------

    class Meta:
        app_label = "analytics"
        verbose_name = "Site Activity"
        verbose_name_plural = "Site Activities"

        # The default ordering avoids accidental full-table scans in
        # admin or shell queries; most queries will supply explicit ordering.
        ordering = ["-timestamp"]

        indexes = [
            # High-cardinality timestamp range scans (most common filter)
            models.Index(fields=["timestamp"], name="ra_activity_ts_idx"),
            # User-specific analytics
            models.Index(fields=["user", "timestamp"], name="ra_activity_user_ts_idx"),
            # Session-based analytics
            models.Index(
                fields=["session_key", "timestamp"],
                name="ra_activity_session_ts_idx",
            ),
            # IP-based analytics and rate-limiting
            models.Index(
                fields=["ip_address", "timestamp"],
                name="ra_activity_ip_ts_idx",
            ),
            # Path performance queries
            models.Index(
                fields=["path", "timestamp"],
                name="ra_activity_path_ts_idx",
            ),
            # Status code distribution queries
            models.Index(
                fields=["status_code", "timestamp"],
                name="ra_activity_status_ts_idx",
            ),
            # Geographic distribution
            models.Index(
                fields=["country_code", "timestamp"],
                name="ra_activity_country_ts_idx",
            ),
            # Device distribution
            models.Index(
                fields=["device_type", "timestamp"],
                name="ra_activity_device_ts_idx",
            ),
            # Authenticated vs anonymous split
            models.Index(
                fields=["user", "ip_address", "timestamp"],
                name="ra_activity_user_ip_ts_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(status_code__gte=100, status_code__lte=599),
                name="ra_activity_valid_status_code",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(response_time_ms__isnull=True)
                    | models.Q(response_time_ms__gte=0)
                ),
                name="ra_activity_non_negative_response_time",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"SiteActivity({self.method} {self.path} "
            f"{self.status_code} @ {self.timestamp.isoformat()})"
        )
