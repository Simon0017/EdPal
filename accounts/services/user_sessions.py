from django.contrib.sessions.models import Session
from django.utils import timezone

from analytics.models import SiteActivity


def _build_device_name(activity: SiteActivity) -> str:
    """
    Builds a human readable device name.
    """

    browser = activity.browser_family.strip() or "Unknown Browser"
    os_name = activity.os_family.strip() or "Unknown OS"

    device = f"{browser} on {os_name}"

    if activity.device_type and activity.device_type.lower() != "desktop":
        device += f" ({activity.device_type.title()})"

    # Fallback if parsing failed
    if browser == "Unknown Browser" and os_name == "Unknown OS":
        if activity.user_agent:
            device = activity.user_agent[:60]
        else:
            device = "Unknown Device"

    return device


def get_active_sessions_for_user(user, current_session_key) -> list[dict]:
    """
    Returns all active Django sessions for a user enriched with the latest
    SiteActivity information for each session.

    Output format intentionally matches window.DATA.
    """

    now = timezone.now()

    # ------------------------------------------------------------------
    # Active Django sessions
    # ------------------------------------------------------------------

    active_sessions = Session.objects.filter(
        expire_date__gt=now
    )

    expiry_map = {
        session.session_key: session.expire_date
        for session in active_sessions
    }

    active_keys = set(expiry_map.keys())

    if not active_keys:
        return []

    # ------------------------------------------------------------------
    # Get all activity for active sessions ordered newest first.
    # The first occurrence of a session_key is therefore its latest request.
    # ------------------------------------------------------------------

    activities = (
        SiteActivity.objects.filter(
            user=user,
            session_key__in=active_keys,
        )
        .exclude(session_key__isnull=True)
        .exclude(session_key="")
        .order_by("-timestamp")
    )

    latest_per_session = {}

    for activity in activities:
        if activity.session_key not in latest_per_session:
            latest_per_session[activity.session_key] = activity

    # ------------------------------------------------------------------
    # Build response
    # ------------------------------------------------------------------

    sessions_list = []

    for session_key, activity in latest_per_session.items():

        expire_date = expiry_map.get(session_key)

        sessions_list.append({
            "id": session_key,
            "device": _build_device_name(activity),
            "current": session_key == current_session_key,
            "expires": expire_date.isoformat() if expire_date else None,
        })

    # Show current session first, then newest activity.
    sessions_list.sort(
        key=lambda item: (
            not item["current"],
            -latest_per_session[item["id"]].timestamp.timestamp(),
        )
    )

    return sessions_list