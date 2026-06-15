"""
Session aggregation helpers for analytics.

Session grouping logic is centralised here and must not be duplicated in
individual analytics services.

Session definition
------------------
A session is a sequence of requests from the same identity (session key,
authenticated user, or IP address fallback) where consecutive requests
are separated by no more than ``SESSION_TIMEOUT_MINUTES`` minutes.

Identity resolution priority:
1. ``session_key`` — most accurate; provided by Django's session middleware.
2. ``user_id`` — available for authenticated users even without sessions.
3. ``ip_address`` — fallback for anonymous, session-less requests.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Iterator, List, Optional, Tuple

from analytics.settings.defaults import get_session_timeout_minutes
from analytics.typing import ActivityRepositoryProtocol

logger = logging.getLogger(__name__)

# Type alias for a single activity row used in session grouping
_ActivityRow = Dict


def _get_session_identity(row: _ActivityRow) -> str:
    """
    Return the session identity key for a repository row.

    Parameters
    ----------
    row:
        A dict with at least ``session_key``, ``user_id``, and
        ``ip_address`` keys.

    Returns
    -------
    str
        A string key that groups requests into sessions.
    """
    session_key: Optional[str] = row.get("session_key")
    if session_key:
        return f"sk:{session_key}"

    user_id = row.get("user_id")
    if user_id:
        return f"uid:{user_id}"

    ip: str = row.get("ip_address", "unknown")
    return f"ip:{ip}"


def compute_session_metrics(
    repository: ActivityRepositoryProtocol,
    start: datetime,
    end: datetime,
) -> Dict[str, float]:
    """
    Compute session-level metrics for the given date range.

    Returns
    -------
    dict
        Keys:
        * ``average_session_duration_seconds`` — mean session length in seconds.
        * ``average_page_views_per_session`` — mean number of requests per session.
        * ``average_unique_paths_per_session`` — mean number of unique paths per session.
        * ``total_sessions`` — total number of sessions identified.
    """
    timeout_minutes = get_session_timeout_minutes()
    timeout_delta = timedelta(minutes=timeout_minutes)

    raw_qs = repository.get_session_data(start, end)

    sessions = list(_build_sessions(raw_qs, timeout_delta))

    if not sessions:
        return {
            "average_session_duration_seconds": 0.0,
            "average_page_views_per_session": 0.0,
            "average_unique_paths_per_session": 0.0,
            "total_sessions": 0,
        }

    total_duration_seconds = sum(s["duration_seconds"] for s in sessions)
    total_page_views = sum(s["page_views"] for s in sessions)
    total_unique_paths = sum(s["unique_paths"] for s in sessions)
    count = len(sessions)

    return {
        "average_session_duration_seconds": total_duration_seconds / count,
        "average_page_views_per_session": total_page_views / count,
        "average_unique_paths_per_session": total_unique_paths / count,
        "total_sessions": count,
    }


def _build_sessions(
    queryset,
    timeout_delta: timedelta,
) -> Iterator[Dict]:
    """
    Group a time-ordered queryset of activity rows into logical sessions.

    Yields one dict per session with ``duration_seconds``, ``page_views``,
    and ``unique_paths`` keys.

    Parameters
    ----------
    queryset:
        An iterable of dicts (from ``.values()``) containing:
        ``session_key``, ``user_id``, ``ip_address``, ``timestamp``, ``path``.
    timeout_delta:
        Maximum gap between consecutive requests in the same session.
    """
    # Accumulate rows per identity, then segment by timeout
    by_identity: Dict[str, List[_ActivityRow]] = {}

    for row in queryset.values(
        "session_key", "user_id", "ip_address", "timestamp", "path"
    ):
        identity = _get_session_identity(row)
        by_identity.setdefault(identity, []).append(row)

    for identity, rows in by_identity.items():
        # Sort by timestamp within each identity bucket
        rows.sort(key=lambda r: r["timestamp"])
        yield from _segment_into_sessions(rows, timeout_delta)


def _segment_into_sessions(
    rows: List[_ActivityRow],
    timeout_delta: timedelta,
) -> Iterator[Dict]:
    """
    Split a sorted list of activity rows (all belonging to one identity)
    into individual sessions using the inactivity timeout rule.

    Yields session summary dicts.
    """
    if not rows:
        return

    session_start: datetime = rows[0]["timestamp"]
    session_last: datetime = rows[0]["timestamp"]
    session_paths: List[str] = [rows[0]["path"]]

    for row in rows[1:]:
        current_ts: datetime = row["timestamp"]
        gap = current_ts - session_last

        if gap > timeout_delta:
            # Emit the completed session
            yield _summarise_session(session_start, session_last, session_paths)
            # Start a new session
            session_start = current_ts
            session_paths = []

        session_last = current_ts
        session_paths.append(row["path"])

    # Emit the final session
    yield _summarise_session(session_start, session_last, session_paths)


def _summarise_session(
    start: datetime,
    end: datetime,
    paths: List[str],
) -> Dict:
    """
    Produce a summary dict for a single session.

    Parameters
    ----------
    start:
        Timestamp of the first request in the session.
    end:
        Timestamp of the last request in the session.
    paths:
        Ordered list of requested paths in the session.
    """
    duration = (end - start).total_seconds()
    return {
        "duration_seconds": max(0.0, duration),
        "page_views": len(paths),
        "unique_paths": len(set(paths)),
    }
