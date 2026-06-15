"""
Visitor-level aggregation helpers for analytics.

Computes new vs returning visitor counts from repository data.
These helpers are reusable across multiple analytics services.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from analytics.typing import ActivityRepositoryProtocol


def compute_visitor_novelty(
    repository: ActivityRepositoryProtocol,
    start: datetime,
    end: datetime,
) -> Dict[str, int]:
    """
    Classify visitors in the date range as new or returning.

    A visitor is *new* when their IP address first appeared during the
    analysis window.  A visitor is *returning* when their IP appeared
    before *start*.

    Parameters
    ----------
    repository:
        Repository instance to query for first-seen dates.
    start:
        Start of the analysis window (inclusive, timezone-aware).
    end:
        End of the analysis window (inclusive, timezone-aware).

    Returns
    -------
    dict
        ``{'new': int, 'returning': int}``
    """
    # Fetch first-seen datetime for every IP across all time
    first_seen_qs = repository.get_ip_first_seen_dates(start, end)

    new_count = 0
    returning_count = 0

    for row in first_seen_qs.values("ip_address", "first_seen"):
        first_seen = row["first_seen"]
        if first_seen is None:
            continue
        if start <= first_seen <= end:
            new_count += 1
        else:
            returning_count += 1

    return {"new": new_count, "returning": returning_count}


def compute_visitor_type_distribution(
    repository: ActivityRepositoryProtocol,
    start: datetime,
    end: datetime,
) -> Dict[str, int]:
    """
    Return the authenticated vs anonymous visit split for the date range.

    Parameters
    ----------
    repository:
        Repository instance.
    start:
        Range start (timezone-aware).
    end:
        Range end (timezone-aware).

    Returns
    -------
    dict
        ``{'authenticated': int, 'anonymous': int}``
    """
    return {
        "authenticated": repository.count_authenticated_visits(start, end),
        "anonymous": repository.count_anonymous_visits(start, end),
    }
