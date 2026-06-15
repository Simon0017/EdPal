"""
Traffic aggregation helpers for analytics.

Shared utilities for computing traffic-related metrics from repository data.
"""

from __future__ import annotations

from typing import Dict, List

from analytics.typing import AggregationResult


def compute_total_from_distribution(distribution: AggregationResult) -> int:
    """
    Sum the ``count`` field across all rows of a distribution result.

    Parameters
    ----------
    distribution:
        A list of dicts each containing a ``count`` key.

    Returns
    -------
    int
        The sum of all ``count`` values.
    """
    return sum(row.get("count", 0) for row in distribution)


def normalise_distribution_percentages(
    distribution: AggregationResult,
    total: int,
) -> List[Dict]:
    """
    Augment each row of a distribution with a ``percentage`` field.

    Parameters
    ----------
    distribution:
        A list of dicts each containing a ``count`` key.
    total:
        The denominator for percentage calculation.

    Returns
    -------
    list of dict
        Input rows enriched with ``percentage`` (0.0–100.0) and rounded
        to two decimal places.
    """
    if total == 0:
        return [{**row, "percentage": 0.0} for row in distribution]

    return [
        {**row, "percentage": round((row.get("count", 0) / total) * 100, 2)}
        for row in distribution
    ]
