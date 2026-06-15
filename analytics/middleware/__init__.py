"""
Middleware package for analytics.

Add to Django's MIDDLEWARE setting (before session/auth middleware):

    MIDDLEWARE = [
        "analytics.middleware.activity_tracker.ActivityTrackerMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        ...
    ]
"""

from analytics.middleware.activity_tracker import ActivityTrackerMiddleware

__all__ = ["ActivityTrackerMiddleware"]
