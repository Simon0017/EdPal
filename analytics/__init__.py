"""
analytics — Django application for request tracking and analytics.

Add to INSTALLED_APPS:

    INSTALLED_APPS = [
        ...
        "analytics",
    ]

Add the middleware (before session/auth middleware for accurate session tracking):

    MIDDLEWARE = [
        "analytics.middleware.activity_tracker.ActivityTrackerMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        ...
    ]
"""

default_app_config = "analytics.apps.RequestAnalyticsConfig"
