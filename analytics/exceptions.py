"""
Custom exceptions for the analytics application.
"""


class RequestAnalyticsError(Exception):
    """Base exception for all analytics errors."""


class GeoIPError(RequestAnalyticsError):
    """Raised when a GeoIP lookup fails in a non-recoverable way."""


class GeoIPUnavailableError(GeoIPError):
    """Raised when the GeoIP database file is not available or not configured."""


class TrackingError(RequestAnalyticsError):
    """Raised when an activity tracking operation fails."""


class RepositoryError(RequestAnalyticsError):
    """Raised when a repository-layer database operation fails."""


class CacheServiceError(RequestAnalyticsError):
    """Raised when a cache backend operation fails in a non-recoverable way."""


class AnalyticsServiceError(RequestAnalyticsError):
    """Raised when an analytics computation fails."""


class ConfigurationError(RequestAnalyticsError):
    """Raised when required application settings are missing or invalid."""
