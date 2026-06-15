"""
Geography aggregation helpers for analytics.

Provides geographic distribution utilities consumed by the traffic and
overview analytics services.
"""

from __future__ import annotations

from typing import Dict, List

from analytics.typing import AggregationResult, ActivityRepositoryProtocol


def compute_geographic_distribution(
    repository: ActivityRepositoryProtocol,
    start,
    end,
) -> AggregationResult:
    """
    Return visit counts grouped by country code, with percentage share.

    Rows are ordered by count descending.  Rows with an empty
    ``country_code`` are excluded by the repository.

    Parameters
    ----------
    repository:
        Repository instance.
    start:
        Range start (timezone-aware datetime).
    end:
        Range end (timezone-aware datetime).

    Returns
    -------
    list of dict
        Each dict has ``country_code``, ``count``, and ``percentage`` keys.
    """
    distribution = repository.get_country_distribution(start, end)
    total = sum(row.get("count", 0) for row in distribution)

    if total == 0:
        return distribution

    return [
        {
            **row,
            "percentage": round((row.get("count", 0) / total) * 100, 2),
        }
        for row in distribution
    ]
