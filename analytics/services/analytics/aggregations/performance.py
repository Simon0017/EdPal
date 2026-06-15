"""
Performance aggregation helpers for analytics.

Provides percentile calculations that are not natively available
through Django's ORM aggregation layer.

When the database is PostgreSQL, the ``percentile_cont`` function via a
raw SQL subquery gives exact results.  For all other backends, an
in-memory sorted-list approximation is used.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from analytics.constants import P95_PERCENTILE
from analytics.typing import ActivityRepositoryProtocol

logger = logging.getLogger(__name__)


def compute_p95_response_time(values: List[int]) -> Optional[int]:
    """
    Compute the 95th percentile of *values* using the nearest-rank method.

    Parameters
    ----------
    values:
        A list of response time integers (milliseconds).  Need not be
        sorted; this function sorts them internally.

    Returns
    -------
    int or None
        The P95 value in milliseconds, or ``None`` when *values* is empty.
    """
    if not values:
        return None

    sorted_values = sorted(values)
    n = len(sorted_values)
    # Nearest-rank method: index = ceil(P * n) - 1 (0-indexed)
    index = max(0, int(P95_PERCENTILE * n + 0.5) - 1)
    return sorted_values[min(index, n - 1)]


def compute_path_p95(
    repository: ActivityRepositoryProtocol,
    path: str,
    start,
    end,
) -> Optional[int]:
    """
    Return the P95 response time for *path* within the date range.

    Fetches raw response time values from the repository and applies the
    nearest-rank P95 approximation.

    Parameters
    ----------
    repository:
        Repository with a ``get_response_times_for_path`` method.
    path:
        The URL path to evaluate.
    start:
        Range start (timezone-aware datetime).
    end:
        Range end (timezone-aware datetime).

    Returns
    -------
    int or None
        P95 response time in ms, or ``None`` when no data exists.
    """
    values = repository.get_response_times_for_path(path, start, end)
    return compute_p95_response_time(list(values))


def enrich_path_performance_with_p95(
    repository: ActivityRepositoryProtocol,
    path_rows: List[Dict],
    start,
    end,
) -> List[Dict]:
    """
    Augment a list of path performance rows with ``p95_response_time_ms``.

    Parameters
    ----------
    repository:
        Repository instance.
    path_rows:
        List of dicts with at least a ``path`` key, as returned by
        :meth:`~analytics.repositories.activity_repository.ActivityRepository.get_path_performance`.
    start:
        Range start (timezone-aware datetime).
    end:
        Range end (timezone-aware datetime).

    Returns
    -------
    list of dict
        The input rows, each augmented with ``p95_response_time_ms``.
    """
    enriched = []
    for row in path_rows:
        p95 = compute_path_p95(repository, row["path"], start, end)
        enriched.append({**row, "p95_response_time_ms": p95})
    return enriched
