"""
Application-wide constants for analytics.

These values are fixed and not configurable. For configurable defaults,
see analytics.settings.defaults.
"""

# HTTP method labels
HTTP_METHOD_GET = "GET"
HTTP_METHOD_POST = "POST"
HTTP_METHOD_PUT = "PUT"
HTTP_METHOD_PATCH = "PATCH"
HTTP_METHOD_DELETE = "DELETE"
HTTP_METHOD_HEAD = "HEAD"
HTTP_METHOD_OPTIONS = "OPTIONS"

# Device type classifications
DEVICE_DESKTOP = "desktop"
DEVICE_MOBILE = "mobile"
DEVICE_TABLET = "tablet"
DEVICE_BOT = "bot"
DEVICE_UNKNOWN = "unknown"

DEVICE_TYPES = (
    (DEVICE_DESKTOP, "Desktop"),
    (DEVICE_MOBILE, "Mobile"),
    (DEVICE_TABLET, "Tablet"),
    (DEVICE_BOT, "Bot"),
    (DEVICE_UNKNOWN, "Unknown"),
)

# HTTP status code families
STATUS_1XX = "1xx"
STATUS_2XX = "2xx"
STATUS_3XX = "3xx"
STATUS_4XX = "4xx"
STATUS_5XX = "5xx"

# Header names
HEADER_X_FORWARDED_FOR = "HTTP_X_FORWARDED_FOR"
HEADER_X_REAL_IP = "HTTP_X_REAL_IP"
HEADER_X_REQUESTED_WITH = "HTTP_X_REQUESTED_WITH"
HEADER_REFERER = "HTTP_REFERER"
HEADER_USER_AGENT = "HTTP_USER_AGENT"
HEADER_HOST = "HTTP_HOST"

# AJAX identifier
AJAX_HEADER_VALUE = "XMLHttpRequest"

# Fallback values
UNKNOWN_VALUE = "unknown"
LOCALHOST_IP = "127.0.0.1"

# Cache key component separators
CACHE_KEY_SEP = ":"

# Analytics type identifiers used in cache keys
ANALYTICS_TYPE_OVERVIEW = "overview"
ANALYTICS_TYPE_TRAFFIC = "traffic"
ANALYTICS_TYPE_BEHAVIOR = "behavior"
ANALYTICS_TYPE_PERFORMANCE = "performance"
ANALYTICS_TYPE_REALTIME = "realtime"
ANALYTICS_TYPE_SUMMARY = "summary"
ANALYTICS_TYPE_GEOIP = "geoip"

# Top-N limits for analytics queries
TOP_PAGES_LIMIT = 10
TOP_REFERRERS_LIMIT = 5
TOP_BROWSERS_LIMIT = 5
TOP_OS_LIMIT = 5
TOP_SLOWEST_ENDPOINTS_LIMIT = 10
TOP_PATH_PERFORMANCE_LIMIT = 20

# Time window constants (in minutes)
REALTIME_WINDOW_MINUTES = 5

# Percentile target for performance calculations
P95_PERCENTILE = 0.95
